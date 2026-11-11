'use strict';
// Downloaded data only until checksum verification, selected native execution only.
const fs = require('node:fs');
const crypto = require('node:crypto');
async function main() {
  const response = await fetch('https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2404-8.0.34.tgz', { signal: AbortSignal.timeout(90000) });
  if (!response.ok) throw new Error('fixture binary download failed');
  const bytes = Buffer.from(await response.arrayBuffer());
  if (crypto.createHash('sha256').update(bytes).digest('hex') !== '3e55cdcf7013fbc805d29d8195230df4b23c7688733ee15ad58ac6bc2a416611') throw new Error('fixture binary checksum mismatch');
  fs.writeFileSync(process.env.FIXTURE_ARCHIVE, bytes, { mode: 0o600 });
  console.log('PASS fixture archive vendor SHA256');
}
main().catch(e => { console.error(e.name, e.message); process.exitCode = 1; });
