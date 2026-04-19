#!/usr/bin/env node
const { getWikiCache } = require('./lib/http');
const { renderWikiPage } = require('./lib/render');

async function main() {
  const repoUrl = process.argv[2];
  const pageId = process.argv[3];
  const language = process.argv[4] || 'en';
  if (!repoUrl || !pageId) {
    console.error('Usage: deepwiki-page <repo_url> <page_id> [language]');
    process.exit(1);
  }

  const cache = await getWikiCache(repoUrl, language);
  const pages = cache?.generated_pages || {};
  if (!pages[pageId]) {
    console.error(`Page not found: ${pageId}`);
    process.exit(2);
  }

  process.stdout.write(renderWikiPage(pages[pageId]));
}

main().catch((error) => {
  console.error(`DeepWiki page query failed: ${error.message}`);
  process.exit(1);
});
