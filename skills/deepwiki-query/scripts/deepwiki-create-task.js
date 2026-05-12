#!/usr/bin/env node
const { createTask } = require('./lib/http');

async function main() {
  const repoUrl = process.argv[2];
  const language = process.argv[3] || 'en';
  const provider = process.argv[4] || 'google';
  const model = process.argv[5] || 'MiniMax-M2.7';

  if (!repoUrl) {
    console.error('用法: node skills/deepwiki-query/scripts/deepwiki-create-task.js <repo_url> [language] [provider] [model]');
    console.error('示例: node skills/deepwiki-query/scripts/deepwiki-create-task.js https://github.com/owner/repo zh');
    console.error('示例: node skills/deepwiki-query/scripts/deepwiki-create-task.js owner/repo en google MiniMax-M2.7');
    process.exit(1);
  }

  console.error(`正在为 ${repoUrl} 创建 Wiki 生成任务...`);
  console.error(`  语言: ${language}  提供商: ${provider}  模型: ${model}`);

  const result = await createTask(repoUrl, { language, provider, model });

  console.error('任务创建成功!');
  process.stdout.write(JSON.stringify(result, null, 2));
}

main().catch((err) => {
  console.error(`任务创建失败: ${err.message}`);
  process.exit(1);
});
