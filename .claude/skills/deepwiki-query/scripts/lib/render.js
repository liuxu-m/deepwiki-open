function renderProjectSummary(project) {
  return `- ${project.name} (${project.language})\n  - summary: ${project.summary || 'N/A'}\n  - note: ${project.note || 'N/A'}`;
}

function renderWikiStructure(wikiStructure) {
  const pages = (wikiStructure.pages || []).slice(0, 10).map((page) => {
    const files = (page.filePaths || []).slice(0, 5).join(', ') || 'N/A';
    return `- ${page.title} [${page.id}]\n  - importance: ${page.importance}\n  - files: ${files}`;
  }).join('\n');

  const sections = (wikiStructure.sections || []).map((section) => `- ${section.title} [${section.id}]`).join('\n') || '- N/A';

  return [
    `# ${wikiStructure.title}`,
    '',
    wikiStructure.description || '',
    '',
    '## Sections',
    sections,
    '',
    '## Top Pages',
    pages || '- N/A',
  ].join('\n');
}

function renderWikiPage(page) {
  const files = (page.filePaths || []).join(', ') || 'N/A';
  const related = (page.relatedPages || []).join(', ') || 'N/A';
  return [
    `# ${page.title}`,
    '',
    `- id: ${page.id}`,
    `- importance: ${page.importance}`,
    `- filePaths: ${files}`,
    `- relatedPages: ${related}`,
    '',
    page.content || '',
  ].join('\n');
}

module.exports = {
  renderProjectSummary,
  renderWikiStructure,
  renderWikiPage,
};
