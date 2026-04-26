import { strict as assert } from 'node:assert'
import { buildStructureRequestBody } from '../../src/utils/wikiRequestBodies.js'

const request = buildStructureRequestBody(
  'https://github.com/livekit/agents',
  'github',
  'livekit',
  'agents',
  'README.md',
  '# README',
  true,
)

assert.equal(request.wiki_task, 'structure')
assert.equal(request.wiki_file_tree, 'README.md')
assert.equal(request.wiki_readme, '# README')
assert.equal(request.wiki_is_comprehensive, true)
assert.equal(request.messages[0].content, 'Generate wiki structure for livekit/agents')
