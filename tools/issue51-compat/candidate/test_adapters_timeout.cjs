const assert = require('node:assert/strict');
const test = require('node:test');

const { coreTelegramOrg } = require('./adapters/coreTelegramOrg.js');
const { githubReleaseFeed } = require('./adapters/githubReleaseFeed.js');

test('coreTelegramOrg - passes default AbortSignal to fetch', async () => {
  let passedOpts = null;
  const mockFetch = async (url, opts) => {
    passedOpts = opts;
    return {
      ok: true,
      text: async () => '<html><body>test</body></html>'
    };
  };

  await coreTelegramOrg({ fetch: mockFetch });

  assert.ok(passedOpts, 'options object passed to fetch');
  assert.ok(passedOpts.signal instanceof AbortSignal, 'signal is an instance of AbortSignal');
  assert.equal(passedOpts.signal.aborted, false, 'signal is not aborted at call time');
});

test('coreTelegramOrg - respects user-supplied signal option', async () => {
  let passedOpts = null;
  const mockFetch = async (url, opts) => {
    passedOpts = opts;
    return {
      ok: true,
      text: async () => '<html><body>test</body></html>'
    };
  };

  const customSignal = AbortSignal.timeout(5000);
  await coreTelegramOrg({ fetch: mockFetch, signal: customSignal });

  assert.equal(passedOpts.signal, customSignal);
});

test('coreTelegramOrg - hanging stub fetch respects signal timeout and rejects with TimeoutError', async () => {
  const mockFetch = (url, opts) => {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {}, 1000);
      if (opts.signal.aborted) {
        clearTimeout(timer);
        return reject(opts.signal.reason);
      }
      opts.signal.addEventListener('abort', () => {
        clearTimeout(timer);
        reject(opts.signal.reason);
      });
    });
  };

  const shortTimeoutSignal = AbortSignal.timeout(10);
  await assert.rejects(
    async () => {
      await coreTelegramOrg({ fetch: mockFetch, signal: shortTimeoutSignal });
    },
    (err) => {
      return err.name === 'TimeoutError';
    }
  );
});

test('githubReleaseFeed - passes default AbortSignal to fetch', async () => {
  let passedOpts = null;
  const mockFetch = async (url, opts) => {
    passedOpts = opts;
    return {
      ok: true,
      text: async () => '<feed><entry><title>v1.0</title><id>/v1.0</id></entry></feed>'
    };
  };

  await githubReleaseFeed('owner/repo', { fetch: mockFetch });

  assert.ok(passedOpts, 'options object passed to fetch');
  assert.ok(passedOpts.signal instanceof AbortSignal, 'signal is an instance of AbortSignal');
  assert.equal(passedOpts.signal.aborted, false, 'signal is not aborted at call time');
});

test('githubReleaseFeed - respects user-supplied signal option', async () => {
  let passedOpts = null;
  const mockFetch = async (url, opts) => {
    passedOpts = opts;
    return {
      ok: true,
      text: async () => '<feed><entry><title>v1.0</title><id>/v1.0</id></entry></feed>'
    };
  };

  const customSignal = AbortSignal.timeout(5000);
  await githubReleaseFeed('owner/repo', { fetch: mockFetch, signal: customSignal });

  assert.equal(passedOpts.signal, customSignal);
});

test('githubReleaseFeed - hanging stub fetch respects signal timeout and rejects with TimeoutError', async () => {
  const mockFetch = (url, opts) => {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {}, 1000);
      if (opts.signal.aborted) {
        clearTimeout(timer);
        return reject(opts.signal.reason);
      }
      opts.signal.addEventListener('abort', () => {
        clearTimeout(timer);
        reject(opts.signal.reason);
      });
    });
  };

  const shortTimeoutSignal = AbortSignal.timeout(10);
  await assert.rejects(
    async () => {
      await githubReleaseFeed('owner/repo', { fetch: mockFetch, signal: shortTimeoutSignal });
    },
    (err) => {
      return err.name === 'TimeoutError';
    }
  );
});
