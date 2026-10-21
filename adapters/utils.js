const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

function sha256(content) {
  return crypto.createHash('sha256').update(content || '', 'utf8').digest('hex');
}

function writeSnapshot(name, content, timestamp = new Date().toISOString()) {
  const sanitizeTimestamp = typeof timestamp === 'string'
    ? timestamp.replace(/[:.]/g, '-')
    : (timestamp instanceof Date ? timestamp.toISOString() : String(timestamp)).replace(/[:.]/g, '-');
  const sanitizedName = String(name).replace(/[/\\?%*:|"<>]/g, '_');
  const filename = `${sanitizedName}_${sanitizeTimestamp}.txt`;
  const dirPath = path.join(process.cwd(), 'snapshots');
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
  const filePath = path.join('snapshots', filename);
  fs.writeFileSync(filePath, content, 'utf8');
  return filePath;
}

module.exports = {
  sha256,
  writeSnapshot,
};
