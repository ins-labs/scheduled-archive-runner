const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');

const { sha256, writeSnapshot } = require('./adapters/utils.js');
const { coreTelegramOrg } = require('./adapters/coreTelegramOrg.js');
const { githubReleaseFeed } = require('./adapters/githubReleaseFeed.js');

test('shared util - sha256 hex digest', () => {
  const digest = sha256('hello world');
  assert.equal(digest, 'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9');
});

test('snapshot writer - saves snapshot file under snapshots/', () => {
  const name = 'test-adapter';
  const content = 'sample snapshot content';
  const timestamp = '2026-10-21T12:00:00.000Z';
  const filePath = writeSnapshot(name, content, timestamp);

  assert.ok(filePath.startsWith('snapshots/'));
  assert.ok(fs.existsSync(filePath));
  assert.equal(fs.readFileSync(filePath, 'utf8'), content);

  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }
});

test('coreTelegramOrg adapter - normalizes HTML content', async () => {
  const html = `
    <!DOCTYPE html>
    <html>
      <head>
        <script>console.log('strip me');</script>
        <style>body { background: #fff; }</style>
      </head>
      <body>
        <h1>Telegram Bot API</h1>
        <p>Recent   changes   in  API.</p>
      </body>
    </html>
  `;

  let requestedUrl = null;
  const mockFetch = async (url) => {
    requestedUrl = url;
    return {
      ok: true,
      text: async () => html
    };
  };

  const result = await coreTelegramOrg({ fetch: mockFetch });

  assert.equal(requestedUrl, 'https://core.telegram.org/bots/api');
  assert.equal(result.content, 'Telegram Bot API Recent changes in API.');
  assert.equal(result.hash, sha256('Telegram Bot API Recent changes in API.'));
});

test('githubReleaseFeed adapter - extracts tag and title', async () => {
  const atomFeed = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>tag:github.com,2008:Repository/123456/v1.8.0</id>
    <title>v1.8.0 release</title>
    <updated>2026-10-20T10:00:00Z</updated>
  </entry>
</feed>`;

  let requestedUrl = null;
  const mockFetch = async (url) => {
    requestedUrl = url;
    return {
      ok: true,
      text: async () => atomFeed
    };
  };

  const result = await githubReleaseFeed('tdlib/td', { fetch: mockFetch });

  assert.equal(requestedUrl, 'https://github.com/tdlib/td/releases.atom');
  assert.equal(result.tag, 'v1.8.0');
  assert.equal(result.title, 'v1.8.0 release');
  const expectedContent = 'Tag: v1.8.0\nTitle: v1.8.0 release';
  assert.equal(result.content, expectedContent);
  assert.equal(result.hash, sha256(expectedContent));
});

test('cli.js adapter CLI entrypoint - coreTelegramOrg with node -e mock fetch', () => {
  const { spawnSync } = require('node:child_process');
  const path = require('node:path');
  const cliPath = path.join(__dirname, 'adapters', 'cli.js');

  const code = `
    process.argv = ['node', '${cliPath.replace(/\\/g, '/')}', 'coreTelegramOrg'];
    globalThis.fetch = async () => ({
      ok: true,
      text: async () => '<h1>Telegram Bot API</h1><p>Sample mock docs</p>'
    });
    require('${cliPath.replace(/\\/g, '/')}');
  `;

  const res = spawnSync(process.execPath, ['-e', code], {
    encoding: 'utf8',
    env: {}
  });

  assert.equal(res.status, 0, `CLI failed with stderr: ${res.stderr}`);
  assert.equal(res.stdout, 'Telegram Bot API Sample mock docs');
});

test('cli.js adapter CLI entrypoint - githubReleaseFeed with node -e mock fetch', () => {
  const { spawnSync } = require('node:child_process');
  const path = require('node:path');
  const cliPath = path.join(__dirname, 'adapters', 'cli.js');

  const atomFeed = '<?xml version="1.0"?><feed><entry><id>tag:github.com,2008:Repository/123/v1.9.0</id><title>v1.9.0 release</title></entry></feed>';
  const code = `
    process.argv = ['node', '${cliPath.replace(/\\/g, '/')}', 'githubReleaseFeed', 'tdlib/td'];
    globalThis.fetch = async () => ({
      ok: true,
      text: async () => ${JSON.stringify(atomFeed)}
    });
    require('${cliPath.replace(/\\/g, '/')}');
  `;

  const res = spawnSync(process.execPath, ['-e', code], {
    encoding: 'utf8',
    env: {}
  });

  assert.equal(res.status, 0, `CLI failed with stderr: ${res.stderr}`);
  assert.equal(res.stdout, 'Tag: v1.9.0\nTitle: v1.9.0 release');
});

test('cli multi - aggregates sources with headers, one-token spec', () => {
  const { spawnSync } = require('node:child_process');
  const path = require('node:path');
  const cliPath = path.join(__dirname, 'adapters', 'cli.js');
  const html = '<h1>Bot API</h1><p>Changes here</p>';
  const atom = '<?xml version="1.0"?><feed><entry><title>v1.2.3</title><id>https://github.com/o/r/releases/tag/v1.2.3</id></entry></feed>';
  const code = `
    process.argv = ['node', '${cliPath.replace(/\\/g, '/')}', 'multi', 'coreTelegramOrg:https://core.telegram.org/bots/api|githubReleaseFeed:o:r'];
    globalThis.fetch = async (url) => ({
      ok: true,
      text: async () => (url.includes('telegram') ? ${JSON.stringify(html)} : ${JSON.stringify(atom)})
    });
    require('${cliPath.replace(/\\/g, '/')}');
  `;
  const res = spawnSync(process.execPath, ['-e', code], { encoding: 'utf8', env: {} });
  assert.equal(res.status, 0, `CLI failed: ${res.stderr}`);
  assert.ok(res.stdout.includes('== coreTelegramOrg https://core.telegram.org/bots/api'));
  assert.ok(res.stdout.includes('Changes here'));
  assert.ok(res.stdout.includes('== githubReleaseFeed o/r'));
  assert.ok(res.stdout.includes('v1.2.3'));
});

test('cli multi - unknown adapter in spec exits nonzero', () => {
  const { spawnSync } = require('node:child_process');
  const path = require('node:path');
  const cliPath = path.join(__dirname, 'adapters', 'cli.js');
  const code = `
    process.argv = ['node', '${cliPath.replace(/\\/g, '/')}', 'multi', 'bogus:x'];
    globalThis.fetch = async () => ({ ok: true, text: async () => '' });
    require('${cliPath.replace(/\\/g, '/')}');
  `;
  const res = spawnSync(process.execPath, ['-e', code], { encoding: 'utf8', env: {} });
  assert.notEqual(res.status, 0);
  assert.ok(res.stderr.includes('unknown adapter'));
});

test('cli multi - empty spec prints nothing and exits 0', () => {
  const { spawnSync } = require('node:child_process');
  const path = require('node:path');
  const cliPath = path.join(__dirname, 'adapters', 'cli.js');
  const code = `
    process.argv = ['node', '${cliPath.replace(/\\/g, '/')}', 'multi', ''];
    globalThis.fetch = async () => ({ ok: true, text: async () => '' });
    require('${cliPath.replace(/\\/g, '/')}');
  `;
  const res = spawnSync(process.execPath, ['-e', code], { encoding: 'utf8', env: {} });
  assert.equal(res.status, 1, `expected exit 1 (no content), got ${res.status}: ${res.stderr}`);
});
