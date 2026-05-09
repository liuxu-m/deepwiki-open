export function shouldWaitForBackgroundTask(tasks, repo) {
  return (tasks || []).some((task) =>
    task.owner === repo.owner &&
    task.repo === repo.repo &&
    task.repo_type === repo.type &&
    ['queued', 'running', 'pause_requested', 'paused'].includes(task.status)
  )
}
