# Wiki 后台任务队列实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 Wiki 生成添加后台任务队列，让用户提交任务后可以关闭页面，任务继续在后台运行，再次打开页面可恢复进度，并有悬浮框显示实时进度。

**Architecture:** 单 Worker 线程顺序处理任务（避免 LLM 并发限制），SQLite 存储任务状态，文件系统存储 Wiki 内容。前端轮询 `/api/tasks` 获取进度，TaskQueuePanel 悬浮框显示任务列表。LLM 调用加超时 + 指数退避重试机制。

**Tech Stack:** Python FastAPI + SQLite (sqlite3 标准库) + threading + Next.js 15 + React Context API

---

## 背景知识

### 当前 Wiki 生成流程（同步，必须保持 WebSocket 连接）

```
前端 [owner]/[repo]/page.tsx
  → 1. fetchRepositoryStructure()   调用 GET /local_repo/structure 或 GitHub API
  → 2. determineWikiStructure()     调用 POST /chat/completions/stream（HTTP SSE）
  → 3. 逐页 generatePageContent()  调用 WebSocket /ws/chat
  → 4. POST /api/wiki_cache        保存缓存
```

关键：步骤 2 和 3 都通过 `simple_chat.chat_completions_stream()` 或 `websocket_wiki.handle_websocket_chat()` 调用 LLM。这两个函数内部有完整的 provider 分支逻辑。

### 为什么单 Worker？

LLM API（Google、OpenAI 等）有并发限制，多个任务同时调用会触发 429 错误。单 Worker 串行处理，每次只有一个任务在调用 LLM，彻底避免并发问题。

### LLM 调用失败类型

- **超时**：LLM 响应慢，需设置超时（建议 120 秒/页面）
- **速率限制**：429 错误，需指数退避重试
- **网络错误**：短暂失败，重试可恢复
- **内容错误**：LLM 返回空内容或格式错误，重试可能恢复

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `api/task_queue.py` | 新建 | SQLite 操作 + 任务 CRUD |
| `api/task_worker.py` | 新建 | 后台 Worker 线程 + 重试逻辑 |
| `api/api.py` | 修改 | 注册任务队列 API 端点 |
| `api/main.py` | 修改 | 启动时初始化 Worker |
| `src/contexts/TaskQueueContext.tsx` | 新建 | 前端任务状态管理 |
| `src/components/TaskQueuePanel.tsx` | 新建 | 悬浮框组件 |
| `src/app/layout.tsx` | 修改 | 包裹 TaskQueueProvider |
| `src/app/api/tasks/route.ts` | 新建 | Next.js API 代理（GET/POST） |
| `src/app/api/tasks/[task_id]/route.ts` | 新建 | Next.js API 代理（GET/DELETE） |
| `src/app/api/tasks/[task_id]/pause/route.ts` | 新建 | 暂停代理 |
| `src/app/api/tasks/[task_id]/resume/route.ts` | 新建 | 恢复代理 |

---

## Task 1: SQLite 任务队列核心模块

**Files:**
- Create: `api/task_queue.py`

### Step 1: 创建文件并写入完整实现

```python
# api/task_queue.py
"""
SQLite-based task queue for Wiki generation.
Single source of truth for task state.
"""
import sqlite3
import uuid
import time
import json
import os
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

# 数据库路径
def get_db_path() -> Path:
    root = Path(os.environ.get("ADALFLOW_ROOT", Path.home() / ".adalflow"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "wiki_tasks.db"

# ── Schema ──────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',
    -- 状态枚举: queued | running | paused | completed | failed | cancelled

    -- 仓库信息
    owner TEXT,
    repo TEXT,
    repo_type TEXT,
    repo_url TEXT,
    token TEXT,
    local_path TEXT,

    -- 生成参数
    language TEXT DEFAULT 'en',
    is_comprehensive INTEGER DEFAULT 1,
    provider TEXT,
    model TEXT,
    excluded_dirs TEXT,
    excluded_files TEXT,
    included_dirs TEXT,
    included_files TEXT,

    -- 时间戳（毫秒）
    created_at INTEGER NOT NULL,
    started_at INTEGER,
    completed_at INTEGER,
    updated_at INTEGER NOT NULL,

    -- 进度
    current_step TEXT DEFAULT 'queued',
    -- 步骤枚举: queued | fetching | structure | generating | saving | done
    total_pages INTEGER DEFAULT 0,
    completed_pages INTEGER DEFAULT 0,
    current_page_title TEXT,

    -- 重试
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Worker 锁（防止崩溃后死锁）
    worker_id TEXT,
    worker_heartbeat INTEGER
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
"""

# ── DB 连接 ──────────────────────────────────────────────────────────────────

@contextmanager
def get_conn():
    """线程安全的数据库连接（每次调用新建连接）"""
    conn = sqlite3.connect(get_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 并发读写
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

# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_task(
    owner: str,
    repo: str,
    repo_type: str,
    repo_url: str,
    language: str = "en",
    is_comprehensive: bool = True,
    provider: str = "google",
    model: str = "gemini-2.0-flash",
    token: Optional[str] = None,
    local_path: Optional[str] = None,
    excluded_dirs: Optional[str] = None,
    excluded_files: Optional[str] = None,
    included_dirs: Optional[str] = None,
    included_files: Optional[str] = None,
) -> dict:
    """创建新任务，返回任务字典"""
    task_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO tasks (
                id, status, owner, repo, repo_type, repo_url, token, local_path,
                language, is_comprehensive, provider, model,
                excluded_dirs, excluded_files, included_dirs, included_files,
                created_at, updated_at, current_step
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                task_id, "queued", owner, repo, repo_type, repo_url, token, local_path,
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
```

### Step 2: 验证模块可导入

```bash
cd c:/code/agent_stu/deepwiki-open
python -c "from api.task_queue import init_db, create_task, get_task; init_db(); print('OK')"
```

期望输出：`OK`

### Step 3: Commit

```bash
git add api/task_queue.py
git commit -m "feat(task-queue): add SQLite task queue core module"
```

---

## Task 2: 后台 Worker 线程（含超时+重试）

**Files:**
- Create: `api/task_worker.py`

### Step 1: 创建 Worker 文件

Worker 的核心职责：
1. 每 5 秒扫描队列，取一个任务处理
2. 把现有 `websocket_wiki.py` 的生成逻辑（fetch → structure → pages → save）搬到这里以函数形式复用
3. 每次调用 LLM 加 120 秒超时，失败后指数退避重试（最多 3 次）
4. 检查 `pause_requested` 信号，保存进度后暂停

```python
# api/task_worker.py
"""
Single background worker thread for Wiki generation tasks.
One task at a time → no LLM concurrency issues.

Retry policy: up to max_retries times with exponential backoff.
  - Attempt 1 fail → wait 10s → retry
  - Attempt 2 fail → wait 30s → retry
  - Attempt 3 fail → wait 60s → mark failed

Timeout: LLM calls are wrapped with asyncio.wait_for(timeout=120).
"""
import asyncio
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from api.task_queue import (
    cancel_task,
    get_next_queued_task,
    get_paused_task,
    get_task,
    increment_retry,
    init_db,
    is_pause_requested,
    release_stale_locks,
    update_task_status,
)

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────────────────────────

POLL_INTERVAL = 5           # 秒：队列轮询间隔
LLM_TIMEOUT = 120           # 秒：单次 LLM 调用超时
RETRY_DELAYS = [10, 30, 60] # 秒：各次重试等待时间
HEARTBEAT_INTERVAL = 10     # 秒：Worker 心跳更新间隔
LOCK_TIMEOUT = 60           # 秒：Worker 锁超时（防止死锁）

# ── Worker 状态（全局单例）────────────────────────────────────────────────────

_worker_thread: Optional[threading.Thread] = None
_worker_id: str = str(uuid.uuid4())[:8]
_stop_event = threading.Event()

# ── 文件系统工具 ──────────────────────────────────────────────────────────────

def get_task_dir(task_id: str) -> Path:
    root = Path(os.environ.get("ADALFLOW_ROOT", Path.home() / ".adalflow"))
    task_dir = root / "wikicache" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir

def save_checkpoint(task_id: str, data: dict) -> None:
    """保存断点续传数据"""
    path = get_task_dir(task_id) / "checkpoint.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def load_checkpoint(task_id: str) -> Optional[dict]:
    """加载断点续传数据"""
    path = get_task_dir(task_id) / "checkpoint.json"
    if path.exists():
        return json.loads(path.read_text())
    return None

def save_wiki_output(task_id: str, wiki_data: dict) -> Path:
    """保存最终 Wiki 输出（兼容现有缓存格式）"""
    task_dir = get_task_dir(task_id)
    output_path = task_dir / "wiki_output.json"
    output_path.write_text(json.dumps(wiki_data, ensure_ascii=False, indent=2))
    return output_path

# ── LLM 调用（带超时）────────────────────────────────────────────────────────

async def call_llm_with_timeout(
    messages: list,
    provider: str,
    model: str,
    system_prompt: str,
    timeout: float = LLM_TIMEOUT,
) -> str:
    """
    调用 LLM，返回完整文本。超时抛出 asyncio.TimeoutError。

    复用 simple_chat 中的 provider 分支逻辑，但以非流式方式收集完整响应。
    """
    from api.config import get_model_config

    async def _call() -> str:
        full_text = ""
        # 根据 provider 选择客户端（复用 simple_chat.py 的逻辑）
        if provider == "google":
            import google.generativeai as genai
            model_config = get_model_config(provider, model).get("model_kwargs", {})
            gen_model = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=model_config.get("temperature", 0.7),
                ),
            )
            response = await asyncio.to_thread(
                gen_model.generate_content,
                [{"role": m["role"].replace("assistant", "model"), "parts": [m["content"]]}
                 for m in messages],
                stream=False,
            )
            full_text = response.text or ""

        elif provider in ("openai", "openrouter", "minimax", "azure"):
            from adalflow.components.model_client import OpenAIClient
            from adalflow.core.types import ModelType
            client = OpenAIClient()
            if provider == "openrouter":
                from api.openrouter_client import OpenRouterClient
                client = OpenRouterClient()
            elif provider == "azure":
                from api.azureai_client import AzureAIClient
                client = AzureAIClient()
            elif provider == "minimax":
                import openai as oai
                base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
                api_key = os.environ.get("MINIMAX_API_KEY", "")
                oai_client = oai.AsyncOpenAI(api_key=api_key, base_url=base_url)
                response = await oai_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system_prompt}] + messages,
                )
                return response.choices[0].message.content or ""

            model_config = get_model_config(provider, model).get("model_kwargs", {})
            api_kwargs = client.convert_inputs_to_api_kwargs(
                input=[{"role": "system", "content": system_prompt}] + messages,
                model_kwargs={**model_config, "stream": False},
                model_type=ModelType.LLM,
            )
            response = await client.acall(api_kwargs=api_kwargs, model_type=ModelType.LLM)
            full_text = client.parse_chat_completion(response) or ""

        elif provider == "ollama":
            import ollama as ollama_lib
            response = await asyncio.to_thread(
                ollama_lib.chat,
                model=model,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                stream=False,
            )
            full_text = response.message.content or ""

        elif provider == "bedrock":
            from api.bedrock_client import BedrockClient
            from adalflow.core.types import ModelType
            client = BedrockClient()
            model_config = get_model_config(provider, model).get("model_kwargs", {})
            api_kwargs = client.convert_inputs_to_api_kwargs(
                input=[{"role": "system", "content": system_prompt}] + messages,
                model_kwargs={**model_config, "stream": False},
                model_type=ModelType.LLM,
            )
            response = await client.acall(api_kwargs=api_kwargs, model_type=ModelType.LLM)
            full_text = client.extract_response_text(response) or ""

        elif provider == "dashscope":
            from api.dashscope_client import DashscopeClient
            from adalflow.core.types import ModelType
            client = DashscopeClient()
            model_config = get_model_config(provider, model).get("model_kwargs", {})
            api_kwargs = client.convert_inputs_to_api_kwargs(
                input=[{"role": "system", "content": system_prompt}] + messages,
                model_kwargs={**model_config, "stream": False},
                model_type=ModelType.LLM,
            )
            response = await client.acall(api_kwargs=api_kwargs, model_type=ModelType.LLM)
            full_text = client.parse_chat_completion(response) or ""

        return full_text

    return await asyncio.wait_for(_call(), timeout=timeout)

# ── 重试包装 ──────────────────────────────────────────────────────────────────

async def call_llm_with_retry(
    task_id: str,
    messages: list,
    provider: str,
    model: str,
    system_prompt: str,
    step_name: str,
    max_retries: int = 3,
) -> str:
    """
    带重试的 LLM 调用。
    - 超时 / 网络错误 / 空响应 → 重试
    - 超过 max_retries → 抛出异常，外层标记任务失败
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = await call_llm_with_timeout(
                messages, provider, model, system_prompt, timeout=LLM_TIMEOUT
            )
            if not result or not result.strip():
                raise ValueError(f"LLM returned empty response on step '{step_name}'")
            return result
        except asyncio.TimeoutError:
            last_error = f"[{step_name}] LLM timeout after {LLM_TIMEOUT}s (attempt {attempt+1})"
            logger.warning(last_error)
        except Exception as e:
            last_error = f"[{step_name}] LLM error: {type(e).__name__}: {e} (attempt {attempt+1})"
            logger.warning(last_error)

        if attempt < max_retries:
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            logger.info(f"Retrying in {delay}s... (attempt {attempt+1}/{max_retries})")
            # 增加任务级别重试计数
            increment_retry(task_id, last_error)
            await asyncio.sleep(delay)

    raise RuntimeError(last_error or f"LLM failed after {max_retries} retries")

# ── 核心 Wiki 生成逻辑 ────────────────────────────────────────────────────────

async def run_task(task: dict) -> None:
    """
    执行单个 Wiki 生成任务。
    
    阶段：
      1. fetching   - 获取仓库文件结构 + 准备 RAG
      2. structure  - 调用 LLM 确定 Wiki 结构
      3. generating - 逐页调用 LLM 生成内容（支持断点续传）
      4. saving     - 保存到缓存文件系统
    
    每页生成前检查 pause_requested 信号，支持随时暂停。
    """
    task_id = task["id"]
    provider = task.get("provider", "google")
    model = task.get("model", "gemini-2.0-flash")
    language = task.get("language", "en")
    is_comprehensive = bool(task.get("is_comprehensive", 1))

    # 导入复用现有逻辑
    from api.prompts import (
        SYSTEM_PROMPT,
        WIKI_STRUCTURE_PROMPT,
        PAGE_CONTENT_PROMPT,
    )
    from api.rag import RAG
    from api.data_pipeline import DatabaseManager

    # ── 阶段 1: fetching ──────────────────────────────────────────────────────
    update_task_status(task_id, "running", current_step="fetching",
                       worker_id=_worker_id)
    logger.info(f"[{task_id}] Step 1/4: fetching repository structure")

    rag = RAG(provider=provider, model=model)
    extra_kwargs = {}
    for field in ("excluded_dirs", "excluded_files", "included_dirs", "included_files"):
        if task.get(field):
            extra_kwargs[field] = task[field]

    await asyncio.to_thread(
        rag.prepare_retriever,
        repo_url=task.get("repo_url") or "",
        repo_type=task.get("repo_type", "github"),
        owner=task.get("owner", ""),
        repo=task.get("repo", ""),
        token=task.get("token"),
        local_path=task.get("local_path"),
        **extra_kwargs,
    )
    repo_files = rag.db_manager.file_list if hasattr(rag, "db_manager") else []

    # ── 阶段 2: structure ─────────────────────────────────────────────────────
    update_task_status(task_id, "running", current_step="structure")
    logger.info(f"[{task_id}] Step 2/4: determining wiki structure")

    structure_prompt = WIKI_STRUCTURE_PROMPT.format(
        language=language,
        comprehensive="comprehensive" if is_comprehensive else "focused",
        repo_files="\n".join(repo_files[:200]),  # 避免超出 context
    )
    structure_text = await call_llm_with_retry(
        task_id=task_id,
        messages=[{"role": "user", "content": structure_prompt}],
        provider=provider,
        model=model,
        system_prompt=SYSTEM_PROMPT,
        step_name="wiki_structure",
    )

    # 解析 wiki 结构（复用前端 XML 解析逻辑，但在后端实现）
    pages = _parse_wiki_structure(structure_text)
    total_pages = len(pages)
    update_task_status(task_id, "running", total_pages=total_pages, completed_pages=0)

    # ── 阶段 3: generating（带断点续传）───────────────────────────────────────
    update_task_status(task_id, "running", current_step="generating")
    logger.info(f"[{task_id}] Step 3/4: generating {total_pages} pages")

    checkpoint = load_checkpoint(task_id) or {}
    completed_page_ids = set(checkpoint.get("completed_page_ids", []))
    generated_pages = checkpoint.get("generated_pages", {})

    for idx, page in enumerate(pages):
        page_id = page.get("id", f"page_{idx}")

        # 断点续传：跳过已生成的页面
        if page_id in completed_page_ids:
            logger.info(f"[{task_id}] Skipping page {page_id} (already done)")
            continue

        # 暂停检查：每页开始前检查
        if is_pause_requested(task_id):
            logger.info(f"[{task_id}] Pause requested, saving checkpoint at page {idx}")
            save_checkpoint(task_id, {
                "completed_page_ids": list(completed_page_ids),
                "generated_pages": generated_pages,
                "pages": pages,
                "structure_text": structure_text,
            })
            update_task_status(
                task_id, "paused",
                current_step="generating",
                completed_pages=len(completed_page_ids),
            )
            return  # 退出，Worker 下次恢复

        update_task_status(
            task_id, "running",
            current_page_title=page.get("title", ""),
            completed_pages=len(completed_page_ids),
        )

        page_prompt = PAGE_CONTENT_PROMPT.format(
            language=language,
            page_title=page.get("title", ""),
            page_description=page.get("description", ""),
            repo_context="\n".join(
                await asyncio.to_thread(rag.call, page.get("title", ""))
            ),
        )
        page_content = await call_llm_with_retry(
            task_id=task_id,
            messages=[{"role": "user", "content": page_prompt}],
            provider=provider,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            step_name=f"page:{page.get('title', page_id)}",
        )

        generated_pages[page_id] = {**page, "content": page_content}
        completed_page_ids.add(page_id)

        # 每页完成后保存断点（防止中途崩溃）
        save_checkpoint(task_id, {
            "completed_page_ids": list(completed_page_ids),
            "generated_pages": generated_pages,
            "pages": pages,
            "structure_text": structure_text,
        })
        logger.info(f"[{task_id}] Page {len(completed_page_ids)}/{total_pages}: {page.get('title')}")

    # ── 阶段 4: saving ────────────────────────────────────────────────────────
    update_task_status(task_id, "running", current_step="saving",
                       completed_pages=total_pages)
    logger.info(f"[{task_id}] Step 4/4: saving wiki output")

    wiki_output = {
        "task_id": task_id,
        "owner": task.get("owner"),
        "repo": task.get("repo"),
        "repo_type": task.get("repo_type"),
        "language": language,
        "pages": list(generated_pages.values()),
        "structure_text": structure_text,
    }
    save_wiki_output(task_id, wiki_output)

    update_task_status(
        task_id, "completed",
        current_step="done",
        completed_pages=total_pages,
        total_pages=total_pages,
    )
    logger.info(f"[{task_id}] Task completed successfully")

def _parse_wiki_structure(structure_text: str) -> list[dict]:
    """
    解析 LLM 返回的 Wiki 结构文本。
    LLM 返回 XML 格式，解析为页面列表。
    示例格式：
    <wiki>
      <section id="overview" title="Overview">...</section>
    </wiki>
    """
    import re
    pages = []
    # 匹配 <section> 标签
    pattern = re.compile(
        r'<section[^>]*\bid=["\']([^"\']+)["\'][^>]*\btitle=["\']([^"\']+)["\'][^>]*>(.*?)</section>',
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(structure_text):
        pages.append({
            "id": m.group(1),
            "title": m.group(2),
            "description": m.group(3).strip()[:500],
        })
    if not pages:
        # 降级：按行解析（LLM 偶尔不返回 XML）
        for i, line in enumerate(structure_text.splitlines()):
            line = line.strip().lstrip("•-*123456789. ")
            if len(line) > 3:
                pages.append({"id": f"page_{i}", "title": line, "description": ""})
    return pages

# ── Worker 主循环 ─────────────────────────────────────────────────────────────

def _worker_loop() -> None:
    """Worker 主循环（在独立线程中运行）"""
    logger.info(f"Worker {_worker_id} started")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while not _stop_event.is_set():
        try:
            # 1. 释放超时锁（防止崩溃死锁）
            released = release_stale_locks(LOCK_TIMEOUT)
            if released:
                logger.warning(f"Released {released} stale task lock(s)")

            # 2. 优先恢复 paused 任务，其次取 queued 任务
            task = get_paused_task() or get_next_queued_task()

            if task is None:
                _stop_event.wait(POLL_INTERVAL)
                continue

            task_id = task["id"]
            logger.info(f"Worker {_worker_id} picked up task {task_id}")

            # 3. 运行任务
            try:
                loop.run_until_complete(run_task(task))
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}", exc_info=True)
                update_task_status(
                    task_id, "failed",
                    error_message=str(e)[:1000],
                )

        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            _stop_event.wait(POLL_INTERVAL)

    loop.close()
    logger.info(f"Worker {_worker_id} stopped")

# ── 公开 API ──────────────────────────────────────────────────────────────────

def start_worker() -> None:
    """启动后台 Worker 线程（应在 FastAPI startup 时调用）"""
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        logger.info("Worker already running")
        return
    init_db()
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=_worker_loop,
        name="wiki-task-worker",
        daemon=True,  # 主进程退出时自动终止
    )
    _worker_thread.start()
    logger.info("Wiki task worker started")

def stop_worker() -> None:
    """停止 Worker 线程（可选，FastAPI shutdown 时调用）"""
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=10)
    logger.info("Wiki task worker stopped")

def worker_status() -> dict:
    """返回 Worker 运行状态"""
    return {
        "worker_id": _worker_id,
        "running": _worker_thread is not None and _worker_thread.is_alive(),
    }
```

### Step 2: 验证 Worker 可导入

```bash
cd c:/code/agent_stu/deepwiki-open
python -c "from api.task_worker import start_worker, worker_status; print('OK')"
```

期望输出：`OK`

### Step 3: Commit

```bash
git add api/task_worker.py
git commit -m "feat(task-worker): add background worker with retry and timeout"
```

---

## Task 3: 在 api.py 注册任务队列端点

**Files:**
- Modify: `api/api.py`（在文件末尾添加，约第 708 行后）

### Step 1: 在 api.py 末尾添加路由

在 `api.py` 末尾（现有端点之后）添加以下代码：

```python
# ── 任务队列 API ──────────────────────────────────────────────────────────────

from api.task_queue import (
    create_task as db_create_task,
    list_tasks,
    get_task,
    cancel_task,
    request_pause,
    resume_task,
    format_task_response,
)
from api.task_worker import worker_status

class TaskCreateRequest(BaseModel):
    owner: str
    repo: str
    repo_type: str = "github"
    repo_url: str
    language: str = "en"
    is_comprehensive: bool = True
    provider: str = "google"
    model: str = "gemini-2.0-flash"
    token: Optional[str] = None
    local_path: Optional[str] = None
    excluded_dirs: Optional[str] = None
    excluded_files: Optional[str] = None
    included_dirs: Optional[str] = None
    included_files: Optional[str] = None

@app.get("/api/tasks")
async def api_list_tasks():
    """列出所有任务（最近 50 条）"""
    tasks = list_tasks(limit=50)
    return [format_task_response(t) for t in tasks]

@app.post("/api/tasks", status_code=201)
async def api_create_task(req: TaskCreateRequest):
    """提交新的 Wiki 生成任务"""
    task = db_create_task(
        owner=req.owner,
        repo=req.repo,
        repo_type=req.repo_type,
        repo_url=req.repo_url,
        language=req.language,
        is_comprehensive=req.is_comprehensive,
        provider=req.provider,
        model=req.model,
        token=req.token,
        local_path=req.local_path,
        excluded_dirs=req.excluded_dirs,
        excluded_files=req.excluded_files,
        included_dirs=req.included_dirs,
        included_files=req.included_files,
    )
    return format_task_response(task)

@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str):
    """获取单个任务详情"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return format_task_response(task)

@app.delete("/api/tasks/{task_id}")
async def api_cancel_task(task_id: str):
    """取消任务（仅 queued/paused 可取消）"""
    success = cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled (must be queued or paused)")
    return {"message": "Task cancelled"}

@app.post("/api/tasks/{task_id}/pause")
async def api_pause_task(task_id: str):
    """请求暂停正在运行的任务"""
    success = request_pause(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Task is not running")
    return {"message": "Pause requested"}

@app.post("/api/tasks/{task_id}/resume")
async def api_resume_task(task_id: str):
    """恢复暂停的任务"""
    success = resume_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Task is not paused")
    return {"message": "Task resumed"}

@app.get("/api/tasks/{task_id}/progress")
async def api_task_progress(task_id: str):
    """轻量级进度端点（前端轮询用）"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    total = task.get("total_pages") or 0
    completed = task.get("completed_pages") or 0
    return {
        "id": task_id,
        "status": task["status"],
        "current_step": task.get("current_step"),
        "total_pages": total,
        "completed_pages": completed,
        "progress": int(completed / total * 100) if total > 0 else 0,
        "current_page_title": task.get("current_page_title"),
        "error_message": task.get("error_message"),
    }

@app.get("/api/worker/status")
async def api_worker_status():
    """Worker 运行状态（调试用）"""
    return worker_status()
```

### Step 2: 验证 api.py 可启动

```bash
cd c:/code/agent_stu/deepwiki-open
python -c "from api.api import app; print('OK')"
```

期望输出：`OK`

### Step 3: Commit

```bash
git add api/api.py
git commit -m "feat(api): add task queue REST endpoints"
```

---

## Task 4: 在 main.py 启动时初始化 Worker

**Files:**
- Modify: `api/main.py`

### Step 1: 在 main.py 的 app 启动事件中添加 Worker 初始化

找到 `api/main.py` 中 uvicorn 启动相关的代码。需要在 FastAPI app 的 `startup` 事件中启动 Worker。

在 `api/main.py` 中，找到 `from api.api import app` 或类似导入行，在其后添加：

```python
from api.task_worker import start_worker, stop_worker

@app.on_event("startup")
async def startup_event():
    """FastAPI 启动时初始化 Worker"""
    start_worker()

@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI 关闭时停止 Worker"""
    stop_worker()
```

**注意**：`main.py` 当前用 `uvicorn.run("api.api:app", ...)` 启动，startup/shutdown 事件需要定义在 `api/api.py` 中的 `app` 对象上。

**正确做法**：在 `api/api.py` 中（`app = FastAPI(...)` 之后）添加：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # 启动
    from api.task_worker import start_worker
    start_worker()
    yield
    # 关闭
    from api.task_worker import stop_worker
    stop_worker()

# 修改 app 初始化为：
# app = FastAPI(lifespan=lifespan)
```

**实际修改**：
1. 在 `api/api.py` 顶部的 `app = FastAPI(...)` 处，将 app 定义替换为带 lifespan 的版本
2. 现有代码约第 30-35 行：`app = FastAPI(title="DeepWiki API", ...)`

将其改为：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _lifespan(app):
    from api.task_worker import start_worker, stop_worker
    start_worker()
    yield
    stop_worker()

app = FastAPI(title="DeepWiki API", lifespan=_lifespan)
```

### Step 2: 验证 Worker 随服务器启动

```bash
cd c:/code/agent_stu/deepwiki-open
python -c "
import asyncio
from api.api import app
from api.task_worker import worker_status
import time
# 模拟 lifespan 启动
from api.task_worker import start_worker
start_worker()
time.sleep(1)
status = worker_status()
print('Worker running:', status['running'])
"
```

期望输出：`Worker running: True`

### Step 3: Commit

```bash
git add api/api.py api/main.py
git commit -m "feat(api): start task worker on FastAPI lifespan startup"
```

---

## Task 5: Next.js API 代理路由

**Files:**
- Create: `src/app/api/tasks/route.ts`
- Create: `src/app/api/tasks/[task_id]/route.ts`
- Create: `src/app/api/tasks/[task_id]/pause/route.ts`
- Create: `src/app/api/tasks/[task_id]/resume/route.ts`

### Step 1: 创建主路由文件

参考现有代理路由（如 `src/app/api/wiki/projects/route.ts`）的模式，使用相同的环境变量 `PYTHON_BACKEND_HOST`。

```typescript
// src/app/api/tasks/route.ts
import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.PYTHON_BACKEND_HOST || 'http://localhost:8001'

export async function GET() {
  const res = await fetch(`${BACKEND}/api/tasks`, { cache: 'no-store' })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const res = await fetch(`${BACKEND}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
```

```typescript
// src/app/api/tasks/[task_id]/route.ts
import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.PYTHON_BACKEND_HOST || 'http://localhost:8001'

export async function GET(
  _req: NextRequest,
  { params }: { params: { task_id: string } }
) {
  const res = await fetch(`${BACKEND}/api/tasks/${params.task_id}`, { cache: 'no-store' })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: { task_id: string } }
) {
  const res = await fetch(`${BACKEND}/api/tasks/${params.task_id}`, { method: 'DELETE' })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
```

```typescript
// src/app/api/tasks/[task_id]/pause/route.ts
import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.PYTHON_BACKEND_HOST || 'http://localhost:8001'

export async function POST(
  _req: NextRequest,
  { params }: { params: { task_id: string } }
) {
  const res = await fetch(`${BACKEND}/api/tasks/${params.task_id}/pause`, { method: 'POST' })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
```

```typescript
// src/app/api/tasks/[task_id]/resume/route.ts
import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.PYTHON_BACKEND_HOST || 'http://localhost:8001'

export async function POST(
  _req: NextRequest,
  { params }: { params: { task_id: string } }
) {
  const res = await fetch(`${BACKEND}/api/tasks/${params.task_id}/resume`, { method: 'POST' })
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
```

### Step 2: 验证路由文件存在

```bash
ls src/app/api/tasks/
ls src/app/api/tasks/[task_id]/
```

期望看到对应文件。

### Step 3: Commit

```bash
git add src/app/api/tasks/
git commit -m "feat(frontend): add Next.js API proxy routes for task queue"
```

---

## Task 6: 前端 TaskQueueContext（状态管理）

**Files:**
- Create: `src/contexts/TaskQueueContext.tsx`

### Step 1: 创建 Context 文件

```typescript
// src/contexts/TaskQueueContext.tsx
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

const POLL_INTERVAL = 3000 // ms：轮询间隔（有活跃任务时）
const IDLE_INTERVAL = 15000 // ms：无活跃任务时的轮询间隔

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
      console.error('Failed to refresh tasks:', e)
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
```

### Step 2: Commit

```bash
git add src/contexts/TaskQueueContext.tsx
git commit -m "feat(frontend): add TaskQueueContext with adaptive polling"
```

---

## Task 7: TaskQueuePanel 悬浮框组件

**Files:**
- Create: `src/components/TaskQueuePanel.tsx`

### Step 1: 创建悬浮框组件

```tsx
// src/components/TaskQueuePanel.tsx
'use client'

import { useCallback, useState } from 'react'
import { TaskInfo, TaskStatus, useTaskQueue } from '@/contexts/TaskQueueContext'

// ── 状态图标 ──────────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: TaskStatus }) {
  switch (status) {
    case 'running':
      return <span className="animate-spin inline-block">🔄</span>
    case 'pause_requested':
      return <span>⏸</span>
    case 'paused':
      return <span>⏸</span>
    case 'queued':
      return <span>⏳</span>
    case 'completed':
      return <span>✅</span>
    case 'failed':
      return <span>❌</span>
    case 'cancelled':
      return <span>🚫</span>
  }
}

// ── 单条任务卡片 ──────────────────────────────────────────────────────────────

function TaskCard({ task }: { task: TaskInfo }) {
  const { pauseTask, resumeTask, cancelTask } = useTaskQueue()

  const repoLabel = task.owner && task.repo
    ? `${task.repo_type || 'github'} / ${task.owner} / ${task.repo}`
    : task.repo || 'Unknown'

  const stepLabel: Record<string, string> = {
    queued: '排队中',
    fetching: '拉取仓库...',
    structure: '分析结构...',
    generating: task.current_page_title ? `生成: ${task.current_page_title}` : '生成内容...',
    saving: '保存缓存...',
    done: '已完成',
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 mb-2 bg-white/80 dark:bg-gray-800/80">
      {/* 标题行 */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <StatusIcon status={task.status} />
          <span className="font-medium text-sm truncate">
            {task.repo || 'Unknown Repo'}
          </span>
        </div>
        <div className="flex gap-1 shrink-0">
          {task.status === 'running' && (
            <button
              onClick={() => pauseTask(task.id)}
              className="text-xs px-2 py-0.5 rounded bg-yellow-100 dark:bg-yellow-900 hover:bg-yellow-200 dark:hover:bg-yellow-800"
              title="暂停"
            >
              暂停
            </button>
          )}
          {task.status === 'paused' && (
            <button
              onClick={() => resumeTask(task.id)}
              className="text-xs px-2 py-0.5 rounded bg-green-100 dark:bg-green-900 hover:bg-green-200 dark:hover:bg-green-800"
              title="恢复"
            >
              恢复
            </button>
          )}
          {['queued', 'paused'].includes(task.status) && (
            <button
              onClick={() => cancelTask(task.id)}
              className="text-xs px-2 py-0.5 rounded bg-red-100 dark:bg-red-900 hover:bg-red-200 dark:hover:bg-red-800"
              title="取消"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* 仓库信息 */}
      <div className="text-xs text-gray-500 dark:text-gray-400 truncate mb-1.5">
        {repoLabel}
      </div>

      {/* 进度条（运行中或已完成才显示） */}
      {['running', 'pause_requested', 'paused', 'completed'].includes(task.status) && task.total_pages > 0 && (
        <div className="mb-1">
          <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-0.5">
            <span>{stepLabel[task.current_step || 'queued'] || task.current_step}</span>
            <span>{task.progress}% · 第 {task.completed_pages}/{task.total_pages} 页</span>
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
      {task.status === 'queued' && (
        <div className="text-xs text-gray-400">排队中，等待生成...</div>
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

const VISIBLE_STATUSES: TaskStatus[] = ['queued', 'running', 'pause_requested', 'paused', 'failed']

export default function TaskQueuePanel() {
  const { tasks } = useTaskQueue()
  const [minimized, setMinimized] = useState(false)
  const [hidden, setHidden] = useState(false)

  // 只展示活跃 + 失败的任务
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
          <span className="text-sm">📋</span>
        )}
      </button>
    )
  }

  return (
    <div className="fixed bottom-4 left-4 z-50 w-80 shadow-xl rounded-xl overflow-hidden backdrop-blur-sm bg-white/90 dark:bg-gray-900/90 border border-gray-200 dark:border-gray-700">
      {/* 面板标题 */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Wiki 生成队列
          </span>
          {activeCount > 0 && (
            <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-full">
              {activeCount} 进行中
            </span>
          )}
        </div>
        <div className="flex gap-1">
          <button
            onClick={() => setMinimized(!minimized)}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 px-1"
            title={minimized ? '展开' : '最小化'}
          >
            {minimized ? '▲' : '▼'}
          </button>
          <button
            onClick={() => setHidden(true)}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 px-1"
            title="隐藏"
          >
            ×
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
```

### Step 2: Commit

```bash
git add src/components/TaskQueuePanel.tsx
git commit -m "feat(frontend): add TaskQueuePanel floating progress widget"
```

---

## Task 8: 挂载 Provider 和 Panel 到 layout.tsx

**Files:**
- Modify: `src/app/layout.tsx`

### Step 1: 修改 layout.tsx

在 `src/app/layout.tsx` 中：
1. 导入 `TaskQueueProvider` 和 `TaskQueuePanel`
2. 用 `TaskQueueProvider` 包裹 `{children}`
3. 在 `{children}` 之后添加 `<TaskQueuePanel />`

```tsx
// 在现有 import 之后添加：
import { TaskQueueProvider } from '@/contexts/TaskQueueContext'
import TaskQueuePanel from '@/components/TaskQueuePanel'

// 在 RootLayout 的 return 中：
// 将 {children} 改为：
<TaskQueueProvider>
  {children}
  <TaskQueuePanel />
</TaskQueueProvider>
```

**注意**：`layout.tsx` 是 Server Component，`TaskQueueProvider` 是 Client Component（有 `'use client'`），这种嵌套是合法的。

### Step 2: 验证 TypeScript 编译

```bash
cd c:/code/agent_stu/deepwiki-open
npx tsc --noEmit
```

期望：无错误或只有现有项目中已有的错误。

### Step 3: Commit

```bash
git add src/app/layout.tsx
git commit -m "feat(frontend): mount TaskQueueProvider and Panel in root layout"
```

---

## Task 9: 检查 prompts.py 中的 prompt 常量是否存在

**Files:**
- Read: `api/prompts.py`

### Step 1: 验证 prompts.py 中有所需常量

Worker 中引用了 `SYSTEM_PROMPT`、`WIKI_STRUCTURE_PROMPT`、`PAGE_CONTENT_PROMPT`。
需要确认这些常量在 `api/prompts.py` 中存在，或者了解实际的常量名。

```bash
grep -n "^[A-Z_]*PROMPT\|^SYSTEM" api/prompts.py | head -20
```

如果常量名不匹配，需要修改 `api/task_worker.py` 中的 import 语句。

具体步骤：
1. 阅读 `api/prompts.py` 全文
2. 确认 wiki 结构生成和页面内容生成的 prompt 函数/常量名
3. 修改 `api/task_worker.py` 中对应的 import 和调用

**注意**：`websocket_wiki.py` 中的 wiki 生成逻辑与此 Worker 高度相关，需要仔细对照 `websocket_wiki.py` 中的 prompt 构建方式，确保 Worker 使用相同的 prompt 格式。

```bash
# 查看 websocket_wiki.py 中的 prompt 构建片段
grep -n "PROMPT\|system_prompt\|structure_prompt\|page_prompt" api/websocket_wiki.py | head -30
```

### Step 2: 根据实际情况修复 task_worker.py 的 import

如果 `prompts.py` 使用不同的接口（例如函数而不是字符串常量），需要相应调整 `task_worker.py` 中的 `run_task()` 函数。

### Step 3: Commit（如有修改）

```bash
git add api/task_worker.py
git commit -m "fix(task-worker): align prompt imports with actual prompts.py API"
```

---

## Task 10: 端到端集成验证

### Step 1: 启动后端，验证 API 可用

```bash
cd c:/code/agent_stu/deepwiki-open
python -m api.main &
sleep 3

# 测试创建任务
curl -X POST http://localhost:8001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"owner":"test","repo":"test","repo_type":"github","repo_url":"https://github.com/test/test","provider":"google","model":"gemini-2.0-flash"}'

# 测试列出任务
curl http://localhost:8001/api/tasks

# 测试 Worker 状态
curl http://localhost:8001/api/worker/status
```

期望：
- POST 返回 201，包含 `id` 和 `status: "queued"`
- GET 返回包含新任务的数组
- Worker status 返回 `{"worker_id": "...", "running": true}`

### Step 2: 启动前端，验证面板显示

```bash
cd c:/code/agent_stu/deepwiki-open
npm run dev
```

打开 http://localhost:3000，检查：
- 任务面板不显示（无任务时）
- 手动通过 API 创建任务后，面板在 3 秒内自动弹出
- 进度条、状态图标正确显示
- 暂停/恢复/取消按钮功能正常

### Step 3: 验证重试机制

通过临时修改让 LLM 调用失败，观察 retry_count 是否递增、是否按 RETRY_DELAYS 间隔重试：

```python
# 临时调试：在 task_worker.py 的 call_llm_with_timeout 开头加一行抛出异常
raise asyncio.TimeoutError("simulated timeout")
```

观察日志：
```
WARNING - [task_id] LLM timeout after 120s (attempt 1)
INFO    - Retrying in 10s... (attempt 1/3)
WARNING - [task_id] LLM timeout after 120s (attempt 2)
...
ERROR   - Task task_id failed: LLM failed after 3 retries
```

### Step 4: 验证断点续传

1. 提交一个真实任务
2. 在 generating 阶段通过 API 请求暂停
3. 查看 `~/.adalflow/wikicache/tasks/{task_id}/checkpoint.json` 是否保存
4. 恢复任务，验证从断点继续（跳过已完成页面）

### Step 5: Final Commit

```bash
git add -A
git commit -m "feat: complete wiki task queue with retry and checkpoint support"
```

---

## 注意事项

### 关于 prompts.py 实际结构

Task 9 最关键。`api/prompts.py` 当前存储 prompt 文本，但 `api/task_worker.py` 中的 `call_llm_with_retry` 需要的 prompt 必须与 `api/websocket_wiki.py` 保持一致。

**建议的处理方式**：
- 先阅读 `websocket_wiki.py` 中 structure 和 page 的 prompt 构建代码
- 在 `task_worker.py` 的 `run_task()` 中复用完全相同的 prompt 格式
- 如果 prompt 很复杂，可以把构建逻辑提取到 `prompts.py` 中

### 关于 RAG.prepare_retriever 的接口

`rag.prepare_retriever()` 的实际参数签名需要对照 `api/rag.py` 确认。Task 9 执行时需要先验证参数名是否匹配。

### 关于 LLM 超时

`LLM_TIMEOUT = 120` 是保守值。实际生产中：
- Google Gemini 通常 10-30 秒完成
- 大型仓库可能需要更长时间
- 可通过环境变量 `WIKI_LLM_TIMEOUT` 覆盖此值
