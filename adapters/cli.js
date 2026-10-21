'use strict';

const { coreTelegramOrg } = require('./coreTelegramOrg.js');
const { githubReleaseFeed } = require('./githubReleaseFeed.js');

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
