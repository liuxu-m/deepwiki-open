"""
SQLite-based task queue for Wiki generation.
Single source of truth for task state.
"""
import sqlite3
import uuid
import time
import os
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


def get_db_path() -> Path:
    root = Path(os.environ.get("ADALFLOW_ROOT", Path.home() / ".adalflow"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "wiki_tasks.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',
    task_type TEXT NOT NULL DEFAULT 'generate',
    owner TEXT,
    repo TEXT,
    repo_type TEXT,
    repo_url TEXT,
    token TEXT,
    local_path TEXT,
    language TEXT DEFAULT 'en',
    is_comprehensive INTEGER DEFAULT 1,
    provider TEXT,
    model TEXT,
    excluded_dirs TEXT,
    excluded_files TEXT,
    included_dirs TEXT,
    included_files TEXT,
    created_at INTEGER NOT NULL,
    started_at INTEGER,
    completed_at INTEGER,
    updated_at INTEGER NOT NULL,
    current_step TEXT DEFAULT 'queued',
    total_pages INTEGER DEFAULT 0,
    completed_pages INTEGER DEFAULT 0,
    current_page_title TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    worker_id TEXT,
    worker_heartbeat INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
"""


@contextmanager
def get_conn():
    """线程安全的数据库连接（每次调用新建连接）"""
    conn = sqlite3.connect(get_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "task_type" not in columns:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN task_type TEXT NOT NULL DEFAULT 'generate'"
            )


def find_unfinished_repo_task(
    owner: str,
    repo: str,
    repo_type: str,
    language: str,
) -> Optional[dict]:
    """查找同仓库同语言下未完成的任务"""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM tasks
            WHERE owner = ?
              AND repo = ?
              AND repo_type = ?
              AND language = ?
              AND status IN ('queued', 'running', 'pause_requested', 'paused')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (owner, repo, repo_type, language),
        ).fetchone()
        return dict(row) if row else None


def create_task(
    owner: str,
    repo: str,
    repo_type: str,
    repo_url: str,
    language: str = "en",
    is_comprehensive: bool = True,
    provider: str = "google",
    model: str = "MiniMax-M2.7",
    token: Optional[str] = None,
    local_path: Optional[str] = None,
    excluded_dirs: Optional[str] = None,
    excluded_files: Optional[str] = None,
    included_dirs: Optional[str] = None,
    included_files: Optional[str] = None,
    task_type: str = "generate",
) -> dict:
    """创建新任务，返回任务字典"""
    existing = find_unfinished_repo_task(owner, repo, repo_type, language)
    if existing:
        return existing

    task_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO tasks (
                id, status, task_type, owner, repo, repo_type, repo_url, token, local_path,
                language, is_comprehensive, provider, model,
                excluded_dirs, excluded_files, included_dirs, included_files,
                created_at, updated_at, current_step
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                task_id, "queued", task_type, owner, repo, repo_type, repo_url, token, local_path,
                language, 1 if is_comprehensive else 0, provider, model,
                excluded_dirs, excluded_files, included_dirs, included_files,
                now, now, "queued",
            ),
        )
    return get_task(task_id)


def get_task(task_id: str) -> Optional[dict]:
    """获取单个任务"""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def list_tasks(limit: int = 50) -> list[dict]:
    """列出所有任务（按创建时间倒序）"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_next_queued_task() -> Optional[dict]:
    """取最早的 queued 任务（FCFS 调度）"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_paused_task() -> Optional[dict]:
    """取最早的 paused 任务（优先恢复暂停的任务）"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE status = 'paused' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def update_task_status(
    task_id: str,
    status: str,
    current_step: Optional[str] = None,
    error_message: Optional[str] = None,
    total_pages: Optional[int] = None,
    completed_pages: Optional[int] = None,
    current_page_title: Optional[str] = None,
    worker_id: Optional[str] = None,
) -> None:
    """更新任务状态（部分更新）"""
    now = int(time.time() * 1000)
    fields = ["status = ?", "updated_at = ?", "worker_heartbeat = ?"]
    values = [status, now, now]

    if current_step is not None:
        fields.append("current_step = ?")
        values.append(current_step)
    if error_message is not None:
        fields.append("error_message = ?")
        values.append(error_message)
    if total_pages is not None:
        fields.append("total_pages = ?")
        values.append(total_pages)
    if completed_pages is not None:
        fields.append("completed_pages = ?")
        values.append(completed_pages)
    if current_page_title is not None:
        fields.append("current_page_title = ?")
        values.append(current_page_title)
    if worker_id is not None:
        fields.append("worker_id = ?")
        values.append(worker_id)

    # 自动设置时间戳
    if status == "running":
        fields.append("started_at = COALESCE(started_at, ?)")
        values.append(now)
    elif status in ("completed", "failed", "cancelled"):
        fields.append("completed_at = ?")
        values.append(now)

    values.append(task_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values
        )


def increment_retry(task_id: str, error_message: str) -> int:
    """重试计数 +1，返回新的 retry_count"""
    with get_conn() as conn:
        conn.execute(
            """UPDATE tasks SET
                retry_count = retry_count + 1,
                error_message = ?,
                updated_at = ?
            WHERE id = ?""",
            (error_message, int(time.time() * 1000), task_id),
        )
        row = conn.execute(
            "SELECT retry_count FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return row["retry_count"]


def cancel_task(task_id: str) -> bool:
    """取消任务（仅 queued/paused 可取消）"""
    now = int(time.time() * 1000)
    with get_conn() as conn:
        result = conn.execute(
            """UPDATE tasks SET status = 'cancelled', updated_at = ?, completed_at = ?
               WHERE id = ? AND status IN ('queued', 'paused')""",
            (now, now, task_id),
        )
        return result.rowcount > 0


def delete_task(task_id: str) -> bool:
    """物理删除任务（任意状态均可）"""
    with get_conn() as conn:
        result = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return result.rowcount > 0


def request_pause(task_id: str) -> bool:
    """请求暂停（将 running 任务标记为 pause_requested，Worker 检测后暂停）"""
    now = int(time.time() * 1000)
    with get_conn() as conn:
        result = conn.execute(
            """UPDATE tasks SET status = 'pause_requested', updated_at = ?
               WHERE id = ? AND status = 'running'""",
            (now, task_id),
        )
        return result.rowcount > 0


def resume_task(task_id: str) -> bool:
    """将 paused 任务恢复为 queued"""
    now = int(time.time() * 1000)
    with get_conn() as conn:
        result = conn.execute(
            """UPDATE tasks SET status = 'queued', updated_at = ?, error_message = NULL
               WHERE id = ? AND status = 'paused'""",
            (now, task_id),
        )
        return result.rowcount > 0


def release_stale_locks(timeout_seconds: int = 60) -> int:
    """释放超时的 Worker 锁（防止崩溃后死锁）"""
    threshold = int(time.time() * 1000) - timeout_seconds * 1000
    with get_conn() as conn:
        result = conn.execute(
            """UPDATE tasks SET
                status = 'queued',
                worker_id = NULL,
                updated_at = ?
               WHERE status = 'running'
                 AND worker_heartbeat < ?""",
            (int(time.time() * 1000), threshold),
        )
        return result.rowcount


def is_pause_requested(task_id: str) -> bool:
    """Worker 轮询此函数检查是否需要暂停"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return row is not None and row["status"] == "pause_requested"


def format_task_response(task: dict) -> dict:
    """将数据库行转换为 API 响应格式"""
    total = task.get("total_pages") or 0
    completed = task.get("completed_pages") or 0
    progress = int(completed / total * 100) if total > 0 else 0
    return {
        "id": task["id"],
        "task_type": task.get("task_type", "generate"),
        "status": task["status"],
        "owner": task.get("owner"),
        "repo": task.get("repo"),
        "repo_type": task.get("repo_type"),
        "language": task.get("language"),
        "provider": task.get("provider"),
        "model": task.get("model"),
        "current_step": task.get("current_step"),
        "total_pages": total,
        "completed_pages": completed,
        "current_page_title": task.get("current_page_title"),
        "progress": progress,
        "error_message": task.get("error_message"),
        "retry_count": task.get("retry_count", 0),
        "created_at": task.get("created_at"),
        "started_at": task.get("started_at"),
        "completed_at": task.get("completed_at"),
    }
