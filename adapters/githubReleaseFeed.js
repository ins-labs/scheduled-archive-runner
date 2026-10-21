const { sha256 } = require('./utils.js');

function parseReleaseFeed(xml) {
  if (!xml) {
    return { tag: '', title: '' };
  }

  const entryMatch = xml.match(/<entry[\s\S]*?<\/entry>/);
  if (!entryMatch) {
    return { tag: '', title: '' };
  }

  const entry = entryMatch[0];

  let title = '';
  const titleMatch = entry.match(/<title[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?<\/title>/);
  if (titleMatch) {
    title = titleMatch[1].trim();
  }

  let tag = '';
  const idMatch = entry.match(/<id>[^<]*\/([^<]+)<\/id>/);
  if (idMatch) {
    tag = idMatch[1].trim();
  } else {
    const linkMatch = entry.match(/href="[^"]*\/tag\/([^"]+)"/);
    if (linkMatch) {
      tag = linkMatch[1].trim();
    } else {
      tag = title;
    }
  }

  return { tag, title };
}

async function githubReleaseFeed(repoOrOwner, repoOrOptions, maybeOptions) {
  let owner = '';
  let repo = '';
  let options = {};

  if (typeof repoOrOwner === 'string' && repoOrOwner.includes('/')) {
    const parts = repoOrOwner.split('/');
    owner = parts[0];
    repo = parts[1];
    options = repoOrOptions || {};
  } else if (typeof repoOrOwner === 'string' && typeof repoOrOptions === 'string') {
    owner = repoOrOwner;
    repo = repoOrOptions;
    options = maybeOptions || {};
  } else if (typeof repoOrOwner === 'string') {
    owner = repoOrOwner;
    options = repoOrOptions || {};
  }

  const fetchFn = options.fetch || globalThis.fetch;
  const url = options.feedUrl || options.url || `https://github.com/${owner}/${repo}/releases.atom`;

  const response = await fetchFn(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status} ${response.statusText || ''}`);
  }

  const xml = await response.text();
  const { tag, title } = parseReleaseFeed(xml);

  const content = `Tag: ${tag}\nTitle: ${title}`;
  const hash = sha256(content);

  return {
    tag,
    title,
    content,
    hash
  };
}

module.exports = {
  githubReleaseFeed,
  parseReleaseFeed
};
