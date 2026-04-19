#!/usr/bin/env node
const { getWikiCache } = require('./lib/http');
const { renderWikiStructure } = require('./lib/render');

async function main() {
  const repoUrl = process.argv[2];
  const language = process.argv[3] || 'en';
  if (!repoUrl) {
    console.error('Usage: deepwiki <repo_url> [language]');
    process.exit(1);
  }

  const cache = await getWikiCache(repoUrl, language);
  if (!cache || !cache.wiki_structure) {
    console.error('Wiki not generated yet. Generate it via DeepWiki Web UI first.');
    process.exit(2);
  }

  process.stdout.write(renderWikiStructure(cache.wiki_structure));
}

main().catch((error) => {
  console.error(`DeepWiki query failed: ${error.message}`);
  process.exit(1);
});
