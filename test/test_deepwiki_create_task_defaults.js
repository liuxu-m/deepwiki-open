const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const projectRoot = path.resolve(__dirname, '..');
const scriptPath = path.join(projectRoot, 'skills', 'deepwiki-query', 'scripts', 'deepwiki-create-task.js');

test('deepwiki-create-task defaults provider to minimax', () => {
  const result = spawnSync(process.execPath, [scriptPath, 'anthropics/claude-code', 'zh'], {
    cwd: projectRoot,
    encoding: 'utf8',
  });

  assert.match(result.stderr, /提供商: minimax/);
  assert.match(result.stderr, /模型: MiniMax-M2\.7/);
});
