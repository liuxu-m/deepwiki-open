export const chooseDefaultModelConfig = (env = process.env) => {
  if (env.OPENAI_API_KEY) {
    return { provider: 'openai', model: 'gpt-4.1-mini' }
  }
  if (env.MINIMAX_API_KEY) {
    return { provider: 'minimax', model: 'MiniMax-M2.7' }
  }
  if (env.OPENROUTER_API_KEY) {
    return { provider: 'openrouter', model: 'openai/gpt-4.1-mini' }
  }
  if (env.GOOGLE_API_KEY) {
    return { provider: 'google', model: 'gemini-2.0-flash' }
  }
  return { provider: 'google', model: 'gemini-2.0-flash' }
}
