const { sha256 } = require('./utils.js');

function normalizeHtml(html) {
  if (!html) return '';

  let text = html
    .replace(/<script\b[^<]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style\b[^<]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, ' ')
    .trim();

  return text;
}

async function coreTelegramOrg(options = {}) {
  const fetchFn = options.fetch || globalThis.fetch;
  const url = options.url || 'https://core.telegram.org/bots/api';

  const response = await fetchFn(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status} ${response.statusText || ''}`);
  }

  const rawHtml = await response.text();
  const content = normalizeHtml(rawHtml);
  const hash = sha256(content);

  return {
    content,
    hash
  };
}

module.exports = {
  coreTelegramOrg,
  normalizeHtml
};
