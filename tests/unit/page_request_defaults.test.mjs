import { strict as assert } from 'node:assert'

function withProviderDefaults(requestBody, provider, model) {
  return {
    ...requestBody,
    provider: provider || 'google',
    model: model || 'gemini-2.0-flash',
  }
}

{
  const result = withProviderDefaults({ repo_url: 'https://github.com/livekit/agents' }, '', '')
  assert.equal(result.provider, 'google')
  assert.equal(result.model, 'gemini-2.0-flash')
}
