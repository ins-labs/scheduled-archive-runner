'use strict';
// Controlled resolver boundary, not a real SRV/TLS integration test.
const assert = require('node:assert/strict');
const dns = require('node:dns');
const net = require('node:net');
const tls = require('node:tls');
const path = require('node:path');
const { createRequire } = require('node:module');
const originalResolve = dns.promises.resolve;
const originalNet = net.createConnection, originalTls = tls.connect;
let target, sockets = 0, srvCalls = 0;
// Reject any attempted socket rather than allowing an external connection.
net.createConnection = tls.connect = function () { sockets++; throw new Error('fixture blocked socket'); };
dns.promises.resolve = async (name, type) => {
  if (type === 'TXT') return [];
  assert.equal(type, 'SRV');
  assert.equal(name, '_mongodb._tcp.cluster.example.test');
  srvCalls++;
  return [{ name: target, port: 27017, priority: 0, weight: 0 }];
};
const req = createRequire(path.resolve('candidate/package.json'));
const { MongoClient, MongoAPIError } = req('mongodb');
async function main() {
  try {
    for (target of ['outside.invalid', 'host.evil-example.test']) {
      let client = new MongoClient('mongodb+srv://cluster.example.test/fixture', { serverSelectionTimeoutMS: 1000 });
      try {
        await assert.rejects(client.connect(), e => e instanceof MongoAPIError);
        assert.equal(sockets, 0);
      } finally { await client.close(); }
    }
    assert.equal(srvCalls, 2);
    console.log('PASS default SRV outside-domain and suffix-label rejection before socket');
  } finally {
    dns.promises.resolve = originalResolve;
    net.createConnection = originalNet;
    tls.connect = originalTls;
  }
}
main().catch(e => { console.error(e.name, e.message); process.exitCode = 1; });
