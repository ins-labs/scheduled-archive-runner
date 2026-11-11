'use strict';

const fs = require('node:fs');

async function run() {
  const probeUrl = process.env.SLOT_2_PROBE_URL;
  if (!probeUrl || probeUrl.trim() === '') {
    console.log('Slot 2 probe not configured');
    return;
  }

  try {
    const response = await fetch(probeUrl, {
      method: 'GET',
      headers: {}
    });

    const statusCode = response.status;
    const arrayBuffer = await response.arrayBuffer();
    const byteCount = arrayBuffer.byteLength;

    console.log(`Slot 2 probe completed with status ${statusCode} and byte count ${byteCount}`);

    if (process.env.GITHUB_OUTPUT) {
      fs.appendFileSync(process.env.GITHUB_OUTPUT, `status_code=${statusCode}\nbyte_count=${byteCount}\n`);
    }

    if (process.env.GITHUB_STEP_SUMMARY) {
      fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `Status: ${statusCode}\nBytes: ${byteCount}\n`);
    }
  } catch (err) {
    console.log('Slot 2 probe failed');
    process.exitCode = 1;
  }
}

if (require.main === module) {
  run().catch(() => {
    process.exitCode = 1;
  });
}

module.exports = { run };
