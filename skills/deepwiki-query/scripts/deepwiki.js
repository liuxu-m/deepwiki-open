#!/usr/bin/env node
const { getWikiCache } = require('./lib/http');
const { renderWikiStructure } = require('./lib/render');

async function main() {
  const repoUrl = process.argv[2];
  const language = process.argv[3] || 'en';
  if (!repoUrl) {
    console.error('用法: node skills/deepwiki-query/scripts/deepwiki.js <repo_url> [language]');
    console.error('示例: node skills/deepwiki-query/scripts/deepwiki.js https://github.com/owner/repo zh');
    process.exit(1);
  }

  console.error(`正在查询 ${repoUrl} (语言: ${language}) ...`);
  const cache = await getWikiCache(repoUrl, language);
  if (!cache || !cache.wiki_structure) {
    console.error('该仓库的 Wiki 尚未生成，请先在 DeepWiki Web UI 中生成。');
    process.exit(2);
  }

  process.stdout.write(renderWikiStructure(cache.wiki_structure));
}

main().catch((err) => {
  console.error(`查询失败: ${err.message}`);
  process.exit(1);
});
