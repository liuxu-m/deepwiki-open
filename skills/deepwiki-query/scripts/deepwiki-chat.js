#!/usr/bin/env node
const { getWikiCache } = require('./lib/http');

async function main() {
  const repoUrl = process.argv[2];
  const language = process.argv[3] || 'en';
  if (!repoUrl) {
    console.error('Usage: deepwiki-chat <repo_url> [language]');
    process.exit(1);
  }

  const cache = await getWikiCache(repoUrl, language);
  const wiki = cache?.wiki_structure;
  if (!wiki) {
    console.error('Wiki not generated yet. Generate it via DeepWiki Web UI first.');
    process.exit(2);
  }

  const pageIds = (wiki.pages || []).slice(0, 10).map((page) => `- ${page.title} (${page.id})`).join('\n') || '- N/A';
  const sectionTitles = (wiki.sections || []).map((section) => `- ${section.title}`).join('\n') || '- N/A';

  process.stdout.write([
    `# ${wiki.title}`,
    '',
    wiki.description || '',
    '',
    '## Sections',
    sectionTitles,
    '',
    '## Suggested Pages',
    pageIds,
    '',
    'You can now continue by asking about a section, a page title, or a specific page_id.',
  ].join('\n'));
}

main().catch((error) => {
  console.error(`DeepWiki chat bootstrap failed: ${error.message}`);
  process.exit(1);
});
