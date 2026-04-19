#!/usr/bin/env node
const { listProcessedProjects } = require('./lib/http');
const { renderProjectSummary } = require('./lib/render');

async function main() {
  const language = process.argv[2] || 'en';
  const projects = await listProcessedProjects();
  const items = Array.isArray(projects) ? projects : projects?.projects || [];

  process.stdout.write([
    '# Processed Projects',
    '',
    `- language: ${language}`,
    `- count: ${items.length}`,
    '',
    items.length ? items.map(renderProjectSummary).join('\n') : '- N/A',
  ].join('\n'));
}

main().catch((error) => {
  console.error(`DeepWiki project list failed: ${error.message}`);
  process.exit(1);
});
