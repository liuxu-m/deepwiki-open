const test = require('node:test');
const assert = require('node:assert/strict');
const { createTask } = require('../skills/deepwiki-query/scripts/lib/http');

test('createTask defaults provider and model to minimax settings', async () => {
  const originalFetch = global.fetch;
  let captured;

  global.fetch = async (_url, options) => {
    captured = JSON.parse(options.body);
    return {
      ok: true,
      json: async () => ({ ok: true }),
    };
  };

  try {
    await createTask('anthropics/claude-code', { language: 'zh' });
  } finally {
    global.fetch = originalFetch;
  }

  assert.equal(captured.provider, 'minimax');
  assert.equal(captured.model, 'MiniMax-M2.7');
  assert.equal(captured.repo_url, 'https://github.com/anthropics/claude-code');
});
