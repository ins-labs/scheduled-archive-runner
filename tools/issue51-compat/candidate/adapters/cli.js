'use strict';

const { coreTelegramOrg } = require('./coreTelegramOrg.js');
const { githubReleaseFeed } = require('./githubReleaseFeed.js');

// multi: one-token spec, sources stay in the slot config secret.
// Usage: node cli.js multi "coreTelegramOrg:<url>|githubReleaseFeed:<owner>:<repo>|..."
// Prints each source's normalized content, one line header per source.
async function multi(spec, fetchFn) {
  const out = [];
  for (const entry of spec.split('|')) {
    if (!entry) continue;
    const parts = entry.split(':');
    if (parts[0] === 'coreTelegramOrg') {
      const url = entry.slice('coreTelegramOrg:'.length);
      const r = await coreTelegramOrg(fetchFn ? { url, fetch: fetchFn } : { url });
      out.push('== coreTelegramOrg ' + url + '\n' + r.content);
    } else if (parts[0] === 'githubReleaseFeed') {
      const r = await githubReleaseFeed(parts[1], parts[2], fetchFn ? { fetch: fetchFn } : {});
      out.push('== githubReleaseFeed ' + parts[1] + '/' + (parts[2] || '') + '\n' + r.content);
    } else {
      throw new Error('multi: unknown adapter in spec: ' + parts[0]);
    }
  }
  return { content: out.join('\n') };
}

async function main() {
  const args = process.argv.slice(2);
  const adapterName = args[0];

  if (!adapterName) {
    console.error('Usage: node cli.js <adapterName> [args...]');
    process.exit(1);
  }

  let result;
  if (adapterName === 'coreTelegramOrg') {
    const url = args[1];
    result = await coreTelegramOrg(url ? { url } : {});
  } else if (adapterName === 'githubReleaseFeed') {
    const repoOrOwner = args[1];
    const repo = args[2];
    if (repo) {
      result = await githubReleaseFeed(repoOrOwner, repo);
    } else {
      result = await githubReleaseFeed(repoOrOwner);
    }
  } else if (adapterName === 'multi') {
    result = await multi(args[1] || '');
  } else {
    console.error(`Unknown adapter: ${adapterName}`);
    process.exit(1);
  }

  if (result && result.content) {
    process.stdout.write(result.content);
  } else {
    console.error('Adapter produced no content');
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
