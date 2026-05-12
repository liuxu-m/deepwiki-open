#!/usr/bin/env node
const { getWikiCache } = require('./lib/http');

async function main() {
  const repoUrl = process.argv[2];
  const language = process.argv[3] || 'en';
  if (!repoUrl) {
    console.error('用法: node skills/deepwiki-query/scripts/deepwiki-chat.js <repo_url> [language]');
    console.error('示例: node skills/deepwiki-query/scripts/deepwiki-chat.js https://github.com/owner/repo zh');
    process.exit(1);
  }

  console.error(`正在查询 ${repoUrl} (语言: ${language}) ...`);
  const cache = await getWikiCache(repoUrl, language);
  const wiki = cache?.wiki_structure;
  if (!wiki) {
    console.error('该仓库的 Wiki 尚未生成，请先在 DeepWiki Web UI 中生成。');
    process.exit(2);
  }

  const pageIds = (wiki.pages || []).slice(0, 10).map((p) => `- ${p.title} (\`${p.id}\`)`).join('\n') || '- 无';
  const sectionTitles = (wiki.sections || []).map((s) => `- ${s.title}`).join('\n') || '- 无';

  process.stdout.write([
    `# ${wiki.title}`,
    '',
    wiki.description || '',
    '',
    '## 章节',
    sectionTitles,
    '',
    '## 推荐页面 (前10个)',
    pageIds,
    '',
    '你可以继续询问某个章节、页面标题或指定 page_id。',
  ].join('\n'));
}

main().catch((err) => {
  console.error(`查询失败: ${err.message}`);
  process.exit(1);
});
