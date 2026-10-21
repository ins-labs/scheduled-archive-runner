'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');

const probePath = path.join(__dirname, 'probe2.cjs');

async function runProbeScript(envVars, fetchImpl) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'probe-test-'));
  const githubOutput = path.join(tmpDir, 'github_output');
  const githubSummary = path.join(tmpDir, 'github_summary');
  fs.writeFileSync(githubOutput, '');
  fs.writeFileSync(githubSummary, '');

  let logs = [];
  let fetchCalledWith = null;

  const mockFetch = async (url, options) => {
    fetchCalledWith = { url, options };
    if (fetchImpl) return fetchImpl(url, options);
    return {
      status: 200,
      arrayBuffer: async () => new TextEncoder().encode('test response payload').buffer
    };
  };

  const env = {
    ...process.env,
    ...envVars,
    GITHUB_OUTPUT: githubOutput,
    GITHUB_STEP_SUMMARY: githubSummary
  };

  const customConsole = {
    log: (...args) => logs.push(args.join(' ')),
    error: (...args) => logs.push(args.join(' ')),
    warn: (...args) => logs.push(args.join(' '))
  };

  const context = {
    process: {
      env,
      exitCode: 0,
      exit: (code) => { process.exitCode = code; }
    },
    console: customConsole,
    fetch: fetchImpl ? mockFetch : global.fetch,
    Buffer,
    URL,
    fs,
    require,
    __filename: probePath,
    __dirname: __dirname
  };

  const scriptContent = fs.readFileSync(probePath, 'utf8');
  await vm.runInNewContext(scriptContent, context);

  const outputContent = fs.readFileSync(githubOutput, 'utf8');
  const summaryContent = fs.readFileSync(githubSummary, 'utf8');

  fs.rmSync(tmpDir, { recursive: true, force: true });

  return {
    exitCode: context.process.exitCode || 0,
    logs,
    outputContent,
    summaryContent,
    fetchCalledWith
  };
}

(async () => {
  // Test Case 1: SLOT_2_PROBE_URL is unset/empty
  {
    let fetchCalled = false;
    const res = await runProbeScript({ SLOT_2_PROBE_URL: '' }, () => {
      fetchCalled = true;
    });
    assert.equal(res.exitCode, 0, 'Unset secret must exit 0');
    assert.equal(fetchCalled, false, 'Unset secret must not call fetch');
    assert.ok(
      res.logs.some(l => l.includes('not configured')) || res.summaryContent.includes('not configured'),
      'Unset secret must output generic not configured note'
    );
  }

  // Test Case 2: SLOT_2_PROBE_URL is set
  {
    const secretUrl = 'https://secret-domain.invalid/private/page?token=secret123';
    const secretBody = 'Top Secret Content Byte Stream'; // 30 bytes
    let fetchCalled = false;

    const res = await runProbeScript({ SLOT_2_PROBE_URL: secretUrl }, async (url, opts) => {
      fetchCalled = true;
      return {
        status: 200,
        arrayBuffer: async () => new TextEncoder().encode(secretBody).buffer
      };
    });

    assert.equal(res.exitCode, 0, 'Configured probe must exit 0');
    assert.equal(fetchCalled, true, 'Configured probe must call fetch');

    const allOutputs = [...res.logs, res.outputContent, res.summaryContent].join('\n');

    // Must contain status code 200 and byte count 30
    assert.ok(allOutputs.includes('200'), 'Must include HTTP status 200');
    assert.ok(allOutputs.includes('30'), 'Must include byte count 30');

    // Privacy invariants check: must NOT leak URL, secret path, secret content, or headers
    assert.ok(!allOutputs.includes('secret-domain'), 'Privacy violation: leaked domain');
    assert.ok(!allOutputs.includes('private/page'), 'Privacy violation: leaked path');
    assert.ok(!allOutputs.includes('secret123'), 'Privacy violation: leaked token');
    assert.ok(!allOutputs.includes('Top Secret Content'), 'Privacy violation: leaked response body');

    // Output formatting check
    assert.ok(res.outputContent.includes('status_code=200'), 'GITHUB_OUTPUT must contain status_code=200');
    assert.ok(res.outputContent.includes('byte_count=30'), 'GITHUB_OUTPUT must contain byte_count=30');
  }

  console.log('Slot 2 probe unit tests passed');
})().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
