'use strict';
const fs = require('node:fs');

(async () => {
  const url = process.env.SLOT_2_PROBE_URL ? process.env.SLOT_2_PROBE_URL.trim() : '';

  if (!url) {
    const note = 'Slot 2 probe not configured\n';
    console.log(note.trim());
    if (process.env.GITHUB_STEP_SUMMARY) {
      try {
        fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, note, 'utf8');
      } catch {}
    }
    return;
  }

  try {
    const response = await fetch(url);
    const statusCode = response.status;
    const arrayBuffer = await response.arrayBuffer();
    const byteCount = arrayBuffer.byteLength;

    console.log(`Probe completed with status ${statusCode} and ${byteCount} bytes.`);

    if (process.env.GITHUB_OUTPUT) {
      try {
        fs.appendFileSync(process.env.GITHUB_OUTPUT, `status_code=${statusCode}\nbyte_count=${byteCount}\n`, 'utf8');
      } catch {}
    }

    if (process.env.GITHUB_STEP_SUMMARY) {
      try {
        fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, `### Slot 2 Feasibility Probe\n- Status Code: ${statusCode}\n- Response Bytes: ${byteCount}\n`, 'utf8');
      } catch {}
    }
  } catch {
    console.error('Probe failed to complete.');
    process.exitCode = 1;
  }
})();
