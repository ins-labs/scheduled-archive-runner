'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

async function runTests() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'probe-test-'));
  const outputFile = path.join(tmpDir, 'github_output');
  const summaryFile = path.join(tmpDir, 'github_summary');

  const originalFetch = globalThis.fetch;
  const originalEnv = { ...process.env };
  const originalStdoutWrite = process.stdout.write;
  const originalExitCode = process.exitCode;

  try {
    // Test Case 1: Unset / empty SLOT_2_PROBE_URL
    {
      delete process.env.SLOT_2_PROBE_URL;
      process.env.GITHUB_OUTPUT = outputFile;
      process.env.GITHUB_STEP_SUMMARY = summaryFile;
      fs.writeFileSync(outputFile, '');
      fs.writeFileSync(summaryFile, '');

      let stdoutText = '';
      process.stdout.write = (chunk) => {
        stdoutText += chunk.toString();
        return true;
      };

      let fetchCalled = false;
      globalThis.fetch = async () => {
        fetchCalled = true;
        throw new Error('Fetch should not be called when URL is unset');
      };

      delete require.cache[require.resolve('./slot2_probe.cjs')];
      const probe = require('./slot2_probe.cjs');
      if (typeof probe.run === 'function') {
        await probe.run();
      }

      assert.equal(fetchCalled, false, 'Fetch must not be called when URL is unset');
      assert.ok(stdoutText.toLowerCase().includes('not configured'), 'Must log generic not configured note');
      assert.equal(fs.readFileSync(outputFile, 'utf8'), '', 'GITHUB_OUTPUT should be empty when not configured');
      assert.equal(fs.readFileSync(summaryFile, 'utf8'), '', 'GITHUB_STEP_SUMMARY should be empty when not configured');
      assert.equal(process.exitCode || 0, 0, 'Exit code must be 0');
    }

    // Test Case 2: Configured SLOT_2_PROBE_URL
    {
      const testSecretUrl = 'https://secret-domain.invalid/confidential-page-path?token=secret123';
      const responseBody = Buffer.from('Sensitive page body content string');
      process.env.SLOT_2_PROBE_URL = testSecretUrl;
      process.env.GITHUB_OUTPUT = outputFile;
      process.env.GITHUB_STEP_SUMMARY = summaryFile;
      fs.writeFileSync(outputFile, '');
      fs.writeFileSync(summaryFile, '');

      let stdoutText = '';
      process.stdout.write = (chunk) => {
        stdoutText += chunk.toString();
        return true;
      };

      let fetchUrl = null;
      let fetchOpts = null;
      globalThis.fetch = async (url, opts) => {
        fetchUrl = url;
        fetchOpts = opts;
        return {
          status: 200,
          arrayBuffer: async () => responseBody.buffer.slice(responseBody.byteOffset, responseBody.byteOffset + responseBody.byteLength)
        };
      };

      delete require.cache[require.resolve('./slot2_probe.cjs')];
      const probe = require('./slot2_probe.cjs');
      if (typeof probe.run === 'function') {
        await probe.run();
      }

      assert.equal(fetchUrl, testSecretUrl);
      if (fetchOpts && fetchOpts.headers) {
        const headers = new Headers(fetchOpts.headers);
        assert.equal(headers.has('cookie'), false, 'Must not send cookies');
        assert.equal(headers.has('authorization'), false, 'Must not send authorization');
      }

      const outputContent = fs.readFileSync(outputFile, 'utf8');
      const summaryContent = fs.readFileSync(summaryFile, 'utf8');

      assert.ok(outputContent.includes('status_code=200'), 'GITHUB_OUTPUT must contain status_code=200');
      assert.ok(outputContent.includes(`byte_count=${responseBody.length}`), `GITHUB_OUTPUT must contain byte_count=${responseBody.length}`);
      assert.ok(summaryContent.includes('200'), 'GITHUB_STEP_SUMMARY must contain status code');
      assert.ok(summaryContent.includes(String(responseBody.length)), 'GITHUB_STEP_SUMMARY must contain byte count');

      const combinedLogs = stdoutText + outputContent + summaryContent;

      assert.equal(combinedLogs.includes('secret-domain'), false, 'Privacy violation: domain leaked in logs/summary/output');
      assert.equal(combinedLogs.includes('confidential-page-path'), false, 'Privacy violation: path leaked in logs/summary/output');
      assert.equal(combinedLogs.includes('token=secret123'), false, 'Privacy violation: URL token leaked in logs/summary/output');
      assert.equal(combinedLogs.includes('Sensitive page body content'), false, 'Privacy violation: page content leaked in logs/summary/output');
      assert.equal(combinedLogs.includes('https://'), false, 'Privacy violation: URL scheme leaked in logs/summary/output');

      assert.equal(process.exitCode || 0, 0, 'Exit code must be 0');
    }

    console.log('Slot 2 probe tests passed');
  } finally {
    globalThis.fetch = originalFetch;
    process.env = originalEnv;
    process.stdout.write = originalStdoutWrite;
    process.exitCode = originalExitCode;
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

runTests().catch((err) => {
  console.error('Slot 2 probe test failed:', err);
  process.exit(1);
});
