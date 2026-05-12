#!/usr/bin/env node
const { listProcessedProjects } = require('./lib/http');
const { renderProjectSummary } = require('./lib/render');

async function main() {
  const language = process.argv[2] || 'en';

  console.error('正在查询已处理的项目列表...');
  const projects = await listProcessedProjects();
  const items = Array.isArray(projects) ? projects : projects?.projects || [];

  process.stdout.write([
    '# 已处理项目',
    '',
    `- 语言过滤: ${language}`,
    `- 项目数量: ${items.length}`,
    '',
    items.length ? items.map(renderProjectSummary).join('\n') : '- 暂无已处理项目',
  ].join('\n'));
}

main().catch((err) => {
  console.error(`查询失败: ${err.message}`);
  process.exit(1);
});
