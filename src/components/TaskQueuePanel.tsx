'use client'

import { useState } from 'react'
import { useTaskQueue, TaskInfo, TaskStatus } from '@/contexts/TaskQueueContext'
import {
  FaSpinner, FaPause, FaPlay, FaTimes, FaChevronUp, FaChevronDown,
  FaCheck, FaExclamationCircle, FaClock, FaBan, FaList
} from 'react-icons/fa'

// ── 状态图标 ──────────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: TaskStatus }) {
  switch (status) {
    case 'running':
      return <FaSpinner className="animate-spin text-blue-500" size={14} />
    case 'pause_requested':
      return <FaPause className="text-yellow-500" size={14} />
    case 'paused':
      return <FaPause className="text-yellow-500" size={14} />
    case 'queued':
      return <FaClock className="text-gray-400" size={14} />
    case 'completed':
      return <FaCheck className="text-green-500" size={14} />
    case 'failed':
      return <FaExclamationCircle className="text-red-500" size={14} />
    case 'cancelled':
      return <FaBan className="text-gray-400" size={14} />
    default:
      return <FaClock className="text-gray-400" size={14} />
  }
}

const STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  fetching: '拉取仓库...',
  structure: '分析结构...',
  generating: '生成内容...',
  saving: '保存缓存...',
  done: '已完成',
}

// ── 单条任务卡片 ──────────────────────────────────────────────────────────────

function TaskCard({ task }: { task: TaskInfo }) {
  const { pauseTask, resumeTask, cancelTask, deleteTask } = useTaskQueue()

  const repoLabel = task.owner && task.repo
    ? `${task.repo_type || 'github'} / ${task.owner} / ${task.repo}`
    : task.repo || '未知仓库'

  const stepLabel = STATUS_LABELS[task.current_step ?? 'queued'] ?? (task.current_step ?? '')

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 mb-2 bg-white/80 dark:bg-gray-800/80 hover:bg-white dark:hover:bg-gray-800 transition-colors">
      {/* 标题行 */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <StatusIcon status={task.status} />
          <span className="font-medium text-sm text-gray-800 dark:text-gray-200 truncate">
            {task.repo || '未知仓库'}
          </span>
        </div>
        <div className="flex gap-1 shrink-0">
          {task.status === 'running' && (
            <button
              onClick={() => pauseTask(task.id)}
              className="text-xs px-2 py-0.5 rounded bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300 hover:bg-yellow-200 dark:hover:bg-yellow-800 transition-colors"
              title="暂停"
            >
              <FaPause size={10} />
            </button>
          )}
          {(task.status === 'paused' || task.status === 'pause_requested') && (
            <button
              onClick={() => resumeTask(task.id)}
              className="text-xs px-2 py-0.5 rounded bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-800 transition-colors flex items-center gap-1"
              title="恢复"
            >
              <FaPlay size={10} /> 恢复
            </button>
          )}
          {['queued', 'paused', 'failed'].includes(task.status) && (
            <button
              onClick={() => cancelTask(task.id)}
              className="text-xs w-6 h-6 flex items-center justify-center rounded bg-red-100 dark:bg-red-900 text-red-600 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-800 transition-colors"
              title="取消"
            >
              <FaTimes size={10} />
            </button>
          )}
          {['completed', 'failed', 'cancelled'].includes(task.status) && (
            <button
              onClick={() => deleteTask(task.id)}
              className="text-xs w-6 h-6 flex items-center justify-center rounded bg-gray-100 dark:bg-gray-700 text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              title="删除"
            >
              <FaTimes size={10} />
            </button>
          )}
        </div>
      </div>

      {/* 仓库信息 */}
      <div className="text-xs text-gray-500 dark:text-gray-400 truncate mb-1.5">
        {repoLabel}
      </div>

      {/* 完成状态文字 */}
      {task.status === 'completed' && (
        <div className="text-xs text-green-600 dark:text-green-400 font-medium mb-1">
          ✓ 已完成{typeof task.total_pages === 'number' && task.total_pages > 0 ? ` · ${task.total_pages} 页` : ''}
        </div>
      )}

      {/* 进度条 */}
      {['running', 'pause_requested', 'paused', 'completed'].includes(task.status) && task.total_pages > 0 && (
        <div className="mb-1">
          <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-0.5">
            <span className="truncate">{stepLabel}{task.current_page_title ? `: ${task.current_page_title}` : ''}</span>
            <span className="shrink-0 ml-1">{task.progress}% · {task.completed_pages}/{task.total_pages} 页</span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
            <div
              className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${task.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* 状态文字 */}
      {task.status === 'queued' && task.total_pages === 0 && (
        <div className="text-xs text-gray-400">等待生成...</div>
      )}
      {task.status === 'failed' && task.error_message && (
        <div className="text-xs text-red-500 mt-1 line-clamp-2" title={task.error_message}>
          ⚠️ {task.error_message}
        </div>
      )}
      {task.status === 'failed' && (
        <div className="text-xs text-gray-400 mt-0.5">
          已重试 {task.retry_count} 次
        </div>
      )}
    </div>
  )
}

// ── 主悬浮框 ──────────────────────────────────────────────────────────────────

const VISIBLE_STATUSES: TaskStatus[] = ['queued', 'running', 'pause_requested', 'paused', 'completed', 'failed', 'cancelled']

export default function TaskQueuePanel() {
  const { tasks } = useTaskQueue()
  const [minimized, setMinimized] = useState(false)
  const [hidden, setHidden] = useState(false)

  const visibleTasks = tasks.filter(t => VISIBLE_STATUSES.includes(t.status))
  const activeCount = tasks.filter(t =>
    ['queued', 'running', 'pause_requested'].includes(t.status)
  ).length

  // 无任务时隐藏
  if (visibleTasks.length === 0) return null

  // 隐藏时显示小图标
  if (hidden) {
    return (
      <button
        onClick={() => setHidden(false)}
        className="fixed bottom-4 left-4 z-50 w-10 h-10 rounded-full bg-blue-500 text-white flex items-center justify-center shadow-lg hover:bg-blue-600 transition-colors"
        title="显示任务队列"
      >
        {activeCount > 0 ? (
          <span className="text-sm font-bold">{activeCount}</span>
        ) : (
          <FaList size={16} />
        )}
      </button>
    )
  }

  return (
    <div className="fixed bottom-4 left-4 z-50 w-80 shadow-xl rounded-xl overflow-hidden backdrop-blur-sm bg-white/90 dark:bg-gray-900/90 border border-gray-200 dark:border-gray-700">
      {/* 面板标题 */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <FaList className="text-gray-500 dark:text-gray-400" size={14} />
          <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Wiki 生成队列
          </span>
          {activeCount > 0 && (
            <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-full">
              {activeCount} 进行中
            </span>
          )}
        </div>
        <div className="flex gap-1 items-center">
          <button
            onClick={() => setMinimized(!minimized)}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 px-1"
            title={minimized ? '展开' : '最小化'}
          >
            {minimized ? <FaChevronUp size={12} /> : <FaChevronDown size={12} />}
          </button>
          <button
            onClick={() => setHidden(true)}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 px-1"
            title="隐藏"
          >
            <FaTimes size={14} />
          </button>
        </div>
      </div>

      {/* 任务列表 */}
      {!minimized && (
        <div className="max-h-96 overflow-y-auto p-2">
          {visibleTasks.map(task => (
            <TaskCard key={task.id} task={task} />
          ))}
        </div>
      )}
    </div>
  )
}
