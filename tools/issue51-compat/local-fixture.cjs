'use strict';
// SOURCE ONLY. Executes only in a separately selected isolated native qualification.
const assert = require('node:assert/strict');
const path = require('node:path');
const { createRequire } = require('node:module');
const req = createRequire(path.resolve('candidate/package.json'));
const { MongoClient } = req('mongodb');
const { MongoMemoryServer } = req('mongodb-memory-server');
const fs = require('node:fs');
assert.equal(req('mongodb/package.json').version, '7.8.0');
assert.equal(req('mongodb-memory-server/package.json').version, '10.2.3');
const coreRequire = createRequire(req.resolve('mongodb-memory-server-core'));
assert.equal(coreRequire('mongodb/package.json').version, '6.22.0');
async function main() {
  let server, client;
  try {
    server = await MongoMemoryServer.create({
      binary: { version: '8.0.34', systemBinary: process.env.FIXTURE_MONGOD },
      instance: { ip: '127.0.0.1', dbPath: process.env.FIXTURE_DATA_DIR }
    });
    const uri = server.getUri();
    assert.ok(uri.startsWith('mongodb://127.0.0.1:'));
    client = new MongoClient(uri, { serverSelectionTimeoutMS: 5000 });
    await client.connect();
    const db = client.db('issue51_fixture');
    const c = db.collection('records');
    await c.insertMany([{ recordId: 1, value: 'alpha' }, { recordId: 2, value: 'beta' }]);
    await c.createIndex({ recordId: 1 });
    assert.equal(await c.countDocuments(), 2);
    assert.equal((await c.findOne({ recordId: 2 })).value, 'beta');
    assert.ok((await db.listCollections().toArray()).some(x => x.name === 'records'));
    assert.ok((await c.indexes()).some(x => x.key.recordId === 1));
    assert.equal((await db.admin().command({ buildInfo: 1 })).version, '8.0.34');
    console.log('PASS direct local MongoDB fixture count/read/index/version');
  } finally {
    try {
      if (client) await client.close();
    } finally {
      if (server) await server.stop();
    }
  }
}
main().catch(e => { console.error(e.name, e.message); process.exitCode = 1; });
