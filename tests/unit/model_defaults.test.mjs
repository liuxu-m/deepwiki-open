import { strict as assert } from 'node:assert'
import { chooseDefaultModelConfig } from '../../src/utils/modelDefaults.js'

const openaiDefault = chooseDefaultModelConfig({
  OPENAI_API_KEY: 'x',
  GOOGLE_API_KEY: '',
  MINIMAX_API_KEY: '',
  OPENROUTER_API_KEY: '',
})
assert.equal(openaiDefault.provider, 'openai')

const googleDefault = chooseDefaultModelConfig({
  OPENAI_API_KEY: '',
  GOOGLE_API_KEY: 'x',
  MINIMAX_API_KEY: '',
  OPENROUTER_API_KEY: '',
})
assert.equal(googleDefault.provider, 'google')
