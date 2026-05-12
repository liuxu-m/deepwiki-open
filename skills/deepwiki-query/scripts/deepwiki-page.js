#!/usr/bin/env node
const { getWikiCache } = require('./lib/http');
const { renderWikiPage } = require('./lib/render');

async function main() {
  const repoUrl = process.argv[2];
  const pageId = process.argv[3];
  const language = process.argv[4] || 'en';
  if (!repoUrl || !pageId) {
    console.error('用法: node skills/deepwiki-query/scripts/deepwiki-page.js <repo_url> <page_id> [language]');
    console.error('示例: node skills/deepwiki-query/scripts/deepwiki-page.js https://github.com/owner/repo architecture-overview zh');
    process.exit(1);
  }

  console.error(`正在查询 ${repoUrl} -> ${pageId} (语言: ${language}) ...`);
  const cache = await getWikiCache(repoUrl, language);
  const pages = cache?.generated_pages || {};
  if (!pages[pageId]) {
    console.error(`页面不存在: ${pageId}`);
    console.error(`可用页面: ${Object.keys(pages).join(', ') || '无'}`);
    process.exit(2);
  }

  process.stdout.write(renderWikiPage(pages[pageId]));
}

main().catch((err) => {
  console.error(`查询失败: ${err.message}`);
  process.exit(1);
});
