import { strict as assert } from 'node:assert'
import { shouldWaitForBackgroundTask } from '../../src/utils/backgroundTaskGate.js'

{
  const tasks = [
    {
      id: 'task-1',
      owner: 'AsyncFuncAI',
      repo: 'deepwiki-open',
      repo_type: 'github',
      status: 'running',
    },
  ]

  const repo = {
    owner: 'AsyncFuncAI',
    repo: 'deepwiki-open',
    type: 'github',
  }

  assert.equal(shouldWaitForBackgroundTask(tasks, repo), true)
}

{
  const tasks = [
    {
      id: 'task-1',
      owner: 'other',
      repo: 'repo',
      repo_type: 'github',
      status: 'running',
    },
  ]

  const repo = {
    owner: 'AsyncFuncAI',
    repo: 'deepwiki-open',
    type: 'github',
  }

  assert.equal(shouldWaitForBackgroundTask(tasks, repo), false)
}
