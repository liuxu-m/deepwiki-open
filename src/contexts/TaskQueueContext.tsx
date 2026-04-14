'use client'

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

// ── 类型定义 ──────────────────────────────────────────────────────────────────

export type TaskStatus =
  | 'queued'
  | 'running'
  | 'pause_requested'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface TaskInfo {
  id: string
  status: TaskStatus
  owner: string | null
  repo: string | null
  repo_type: string | null
  language: string | null
  provider: string | null
  model: string | null
  current_step: string | null
  total_pages: number
  completed_pages: number
  current_page_title: string | null
  progress: number
  error_message: string | null
  retry_count: number
  created_at: number
  started_at: number | null
  completed_at: number | null
}

export interface TaskSubmission {
  owner: string
  repo: string
  repo_type: string
  repo_url: string
  language?: string
  is_comprehensive?: boolean
  provider?: string
  model?: string
  token?: string | null
  local_path?: string | null
  excluded_dirs?: string | null
  excluded_files?: string | null
  included_dirs?: string | null
  included_files?: string | null
}

interface TaskQueueContextValue {
  tasks: TaskInfo[]
  submitTask: (data: TaskSubmission) => Promise<TaskInfo>
  pauseTask: (taskId: string) => Promise<void>
  resumeTask: (taskId: string) => Promise<void>
  cancelTask: (taskId: string) => Promise<void>
  refreshTasks: () => Promise<void>
  isLoading: boolean
}

// ── Context ──────────────────────────────────────────────────────────────────

const TaskQueueContext = createContext<TaskQueueContextValue | null>(null)

const POLL_INTERVAL = 3000  // ms：有活跃任务时 3s 轮询
const IDLE_INTERVAL = 15000  // ms：无活跃任务时 15s 轮询

function isActiveTask(task: TaskInfo): boolean {
  return ['queued', 'running', 'pause_requested'].includes(task.status)
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function TaskQueueProvider({ children }: { children: React.ReactNode }) {
  const [tasks, setTasks] = useState<TaskInfo[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refreshTasks = useCallback(async () => {
    try {
      const res = await fetch('/api/tasks', { cache: 'no-store' })
      if (!res.ok) return
      const data: TaskInfo[] = await res.json()
      setTasks(data)
    } catch (e) {
      console.error('[TaskQueue] Failed to refresh tasks:', e)
    }
  }, [])

  // 自适应轮询：有活跃任务时快，否则慢
  useEffect(() => {
    const hasActive = tasks.some(isActiveTask)
    const interval = hasActive ? POLL_INTERVAL : IDLE_INTERVAL

    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = setInterval(refreshTasks, interval)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [tasks, refreshTasks])

  // 初始加载
  useEffect(() => {
    refreshTasks()
  }, [refreshTasks])

  const submitTask = useCallback(async (data: TaskSubmission): Promise<TaskInfo> => {
    setIsLoading(true)
    try {
      const res = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to submit task')
      }
      const task: TaskInfo = await res.json()
      setTasks(prev => [task, ...prev])
      return task
    } finally {
      setIsLoading(false)
    }
  }, [])

  const pauseTask = useCallback(async (taskId: string) => {
    await fetch(`/api/tasks/${taskId}/pause`, { method: 'POST' })
    await refreshTasks()
  }, [refreshTasks])

  const resumeTask = useCallback(async (taskId: string) => {
    await fetch(`/api/tasks/${taskId}/resume`, { method: 'POST' })
    await refreshTasks()
  }, [refreshTasks])

  const cancelTask = useCallback(async (taskId: string) => {
    await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' })
    await refreshTasks()
  }, [refreshTasks])

  return (
    <TaskQueueContext.Provider
      value={{ tasks, submitTask, pauseTask, resumeTask, cancelTask, refreshTasks, isLoading }}
    >
      {children}
    </TaskQueueContext.Provider>
  )
}

export function useTaskQueue() {
  const ctx = useContext(TaskQueueContext)
  if (!ctx) throw new Error('useTaskQueue must be used inside TaskQueueProvider')
  return ctx
}
