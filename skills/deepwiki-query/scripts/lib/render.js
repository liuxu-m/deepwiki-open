function renderWikiStructure(wiki) {
  if (!wiki) return 'Wiki 数据为空。';
  const lines = [`# ${wiki.title || '未命名项目'}`, ''];
  if (wiki.description) lines.push(wiki.description, '');

  const pages = wiki.pages || [];
  if (pages.length) {
    lines.push(`## Pages (${pages.length})`, '');
    for (const p of pages) {
      const imp = p.importance ? ` *[${p.importance}]*` : '';
      lines.push(`- **${p.title}** (\`${p.id}\`)${imp}`);
    }
    lines.push('');
  }

  const sections = wiki.sections || [];
  if (sections.length) {
    lines.push('## Sections', '');
    for (const s of sections) {
      lines.push(`- **${s.title}** (\`${s.id}\`)`);
      if (s.pages) for (const pid of s.pages) lines.push(`  - ${pid}`);
      if (s.subsections) for (const sid of s.subsections) lines.push(`  - > ${sid}`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

function renderWikiPage(page) {
  if (!page) return '页面数据为空。';
  const lines = [
    `# ${page.title || '未命名页面'}`,
    '',
    `- ID: \`${page.id || 'N/A'}\``,
    `- Importance: ${page.importance || 'N/A'}`,
    `- Related Pages: ${(page.relatedPages || []).join(', ') || 'N/A'}`,
    `- File Paths: ${(page.filePaths || []).join(', ') || 'N/A'}`,
    '',
    '---',
    '',
    page.content || '*暂无内容*',
    '',
  ];
  return lines.join('\n');
}

function renderProjectSummary(p) {
  const summary = p.summary ? ` — ${p.summary}` : '';
  const note = p.note ? ` 📝${p.note}` : '';
  return `- **${p.name}** [${p.language}]${summary}${note}`;
}

module.exports = { renderWikiStructure, renderWikiPage, renderProjectSummary };
