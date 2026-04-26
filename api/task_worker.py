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
import re
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from api.chat_runtime import run_chat_once
from api.repo_branch import detect_default_branch
from api.page_source_merge import merge_page_source_files
from api.task_queue import (
    cancel_task as db_cancel_task,
    get_next_queued_task,
    get_paused_task,
    get_task,
    increment_retry,
    init_db,
    is_pause_requested,
    release_stale_locks,
    update_task_status,
)
from api.prompts import SIMPLE_CHAT_SYSTEM_PROMPT
from api.wiki_generation import (
    build_context_text,
    build_shared_page_prompt,
    build_shared_structure_prompt,
    normalize_source_citation_links,
    validate_generated_wiki_page,
)

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────────────────────────

POLL_INTERVAL = 5           # 秒：队列轮询间隔
LLM_TIMEOUT = 120           # 秒：单次 LLM 调用超时
RETRY_DELAYS = [10, 30, 60] # 秒：各次重试等待时间
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

def expand_relevant_files(
    relevant_files: list[str],
    repo_files: list[str],
    per_directory_limit: int = 3,
    total_limit: int = 8,
) -> list[str]:
    """将 relevant_files 中的目录路径受控展开为具体文件路径。"""
    expanded: list[str] = []
    seen: set[str] = set()

    for item in relevant_files:
        if len(expanded) >= total_limit:
            break

        normalized = (item or "").strip()
        if not normalized:
            continue

        if normalized.endswith("/"):
            matches = [
                path for path in repo_files
                if path.startswith(normalized) and not path.endswith("/")
            ][:per_directory_limit]
            for match in matches:
                if match not in seen:
                    expanded.append(match)
                    seen.add(match)
                    if len(expanded) >= total_limit:
                        break
        else:
            if normalized not in seen:
                expanded.append(normalized)
                seen.add(normalized)

    return expanded[:total_limit]


def save_checkpoint(task_id: str, data: dict) -> None:
    """保存断点续传数据"""
    path = get_task_dir(task_id) / "checkpoint.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_checkpoint(task_id: str) -> Optional[dict]:
    """加载断点续传数据"""
    path = get_task_dir(task_id) / "checkpoint.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def _normalize_wiki_output(wiki_struct: dict, generated_pages: dict, task: dict) -> tuple[dict, dict]:
    """
    将 task_worker 输出的 snake_case 字段转换为前端 WikiPage 接口期望的格式。
    同时补全 wiki_structure 缺少的 id 和 rootSections 字段。
    """
    # 转换 wiki_structure
    struct = dict(wiki_struct)
    struct["id"] = struct.get("id") or "wiki-root"
    # rootSections：从 sections 中提取顶级 section 的 id
    struct["rootSections"] = [
        s["id"] for s in struct.get("sections", [])
        if not any(sec.get("subsection_refs") and s["id"] in sec["subsection_refs"]
                   for sec in struct.get("sections", []))
    ][:10] if struct.get("sections") else []

    # 将 worker 风格 sections 转换为 API 期望的字段
    normalized_sections = []
    for section in struct.get("sections", []):
        normalized_section = dict(section)
        if "page_refs" in normalized_section:
            normalized_section["pages"] = normalized_section.pop("page_refs")
        if "subsection_refs" in normalized_section:
            normalized_section["subsections"] = normalized_section.pop("subsection_refs")
        normalized_sections.append(normalized_section)
    struct["sections"] = normalized_sections

    # 转换 wiki_structure.pages 中的字段，并将内容合并进来
    for page in struct.get("pages", []):
        if "relevant_files" in page:
            page["filePaths"] = page.pop("relevant_files")
        if "related_pages" in page:
            page["relatedPages"] = page.pop("related_pages")
        page.pop("parent_section", None)
        page.pop("description", None)
        page.pop("generated_at", None)
        # 补充 content（从 generated_pages 合并）
        page_id = page.get("id")
        if page_id and page_id in generated_pages:
            page["content"] = generated_pages[page_id].get("content", "")

    # 转换 generated_pages（dict by page_id）
    norm_pages = {}
    for pid, pdata in generated_pages.items():
        page = dict(pdata)
        if "relevant_files" in page:
            page["filePaths"] = page.pop("relevant_files")
        if "related_pages" in page:
            page["relatedPages"] = page.pop("related_pages")
        if "parent_section" in page:
            page.pop("parent_section", None)
        page.pop("description", None)
        page.pop("generated_at", None)
        # 确保必要字段存在
        page.setdefault("content", "")
        page.setdefault("importance", "medium")
        page.setdefault("relatedPages", [])
        page.setdefault("filePaths", [])
        norm_pages[pid] = page

    return struct, norm_pages


def save_wiki_output(task_id: str, wiki_data: dict) -> Path:
    """保存最终 Wiki 输出"""
    task_dir = get_task_dir(task_id)
    output_path = task_dir / "wiki_output.json"
    output_path.write_text(json.dumps(wiki_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _save_wiki_output_to_project_cache(wiki_data: dict) -> None:
    """
    将生成的 wiki 保存到项目列表可读取的缓存路径。
    项目列表 API (/api/processed_projects) 扫描的是:
      ~/.adalflow/wikicache/deepwiki_cache_{repo_type}_{owner}_{repo}_{language}.json
    """
    owner = wiki_data.get("owner")
    repo_val = wiki_data.get("repo")
    repo_type = wiki_data.get("repo_type", "github")
    language = wiki_data.get("language", "en")
    # repo 可能是 dict（如新格式）或 string（旧格式）
    repo = repo_val.get("repo") if isinstance(repo_val, dict) else repo_val
    if not owner or not repo:
        return

    try:
        cache_dir = Path.home() / ".adalflow" / "wikicache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        filename = f"deepwiki_cache_{repo_type}_{owner}_{repo}_{language}.json"
        cache_path = cache_dir / filename
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(wiki_data, f, ensure_ascii=False, indent=2)
        logger.info(f"[project-cache] Saved wiki to {cache_path}")
    except Exception as e:
        logger.warning(f"[project-cache] Failed to save wiki cache: {e}")

# ── Wiki 结构解析 ─────────────────────────────────────────────────────────────
async def call_llm_with_retry(
    task_id: str,
    request: SimpleNamespace,
    step_name: str,
    max_retries: int = 3,
) -> str:
    """
    带重试的同源聊天调用。
    - 超时 / 网络错误 / 空响应 → 重试
    - 超过 max_retries → 抛出异常
    """
    last_error: Optional[str] = None
    for attempt in range(max_retries + 1):
        try:
            result = await asyncio.wait_for(run_chat_once(request), timeout=LLM_TIMEOUT)
            if not result or not result.strip():
                raise ValueError(f"LLM returned empty response on step '{step_name}'")
            return result
        except asyncio.TimeoutError:
            last_error = f"[{step_name}] LLM timeout after {LLM_TIMEOUT}s (attempt {attempt + 1}/{max_retries + 1})"
            logger.warning(last_error)
        except Exception as e:
            last_error = f"[{step_name}] LLM error: {type(e).__name__}: {e} (attempt {attempt + 1}/{max_retries + 1})"
            logger.warning(last_error)

        if attempt < max_retries:
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            logger.info(f"[{task_id}] Retrying in {delay}s...")
            increment_retry(task_id, last_error or "")
            await asyncio.sleep(delay)

    raise RuntimeError(last_error or f"LLM failed after {max_retries} retries")

# ── Wiki 结构解析 ─────────────────────────────────────────────────────────────

def parse_wiki_structure_xml(xml_text: str) -> dict:
    """
    解析 LLM 返回的 <wiki_structure> XML，提取 pages 和 sections。
    返回 dict: { pages: [...], sections: [...], title, description }
    """
    pages = []
    sections = []

    # 提取 title
    title_m = re.search(r"<title>(.*?)</title>", xml_text, re.DOTALL)
    title = title_m.group(1).strip() if title_m else "Wiki"

    # 提取 description
    desc_m = re.search(r"<description>(.*?)</description>", xml_text, re.DOTALL)
    description = desc_m.group(1).strip() if desc_m else ""

    # 提取 pages - 需要从 start tag 和 body 分别提取
    page_tag_and_body = re.findall(
        r"<page\b([^>]*)>(.*?)</page>", xml_text, re.DOTALL | re.IGNORECASE
    )
    for attrs, body in page_tag_and_body:
        pid_m = re.search(r'\bid=["\']([^"\']+)["\']', attrs)
        title_m = re.search(r"<title>(.*?)</title>", body, re.DOTALL)
        desc_m = re.search(r"<description>(.*?)</description>", body, re.DOTALL)
        imp_m = re.search(r"<importance>(.*?)</importance>", body, re.DOTALL)
        files = re.findall(r"<file_path>(.*?)</file_path>", body, re.DOTALL)
        related = re.findall(r"<related>(.*?)</related>", body, re.DOTALL)
        parent = re.search(r"<parent_section>(.*?)</parent_section>", body, re.DOTALL)
        if pid_m and title_m:
            pages.append({
                "id": pid_m.group(1).strip(),
                "title": title_m.group(1).strip(),
                "description": desc_m.group(1).strip() if desc_m else "",
                "importance": imp_m.group(1).strip() if imp_m else "medium",
                "relevant_files": [f.strip() for f in files],
                "related_pages": [r.strip() for r in related],
                "parent_section": parent.group(1).strip() if parent else "",
            })

    # 提取 sections
    section_tag_and_body = re.findall(
        r"<section\b([^>]*)>(.*?)</section>", xml_text, re.DOTALL | re.IGNORECASE
    )
    for attrs, body in section_tag_and_body:
        sid_m = re.search(r'\bid=["\']([^"\']+)["\']', attrs)
        title_m = re.search(r"<title>(.*?)</title>", body, re.DOTALL)
        page_refs = re.findall(r"<page_ref>(.*?)</page_ref>", body, re.DOTALL)
        sub_refs = re.findall(r"<section_ref>(.*?)</section_ref>", body, re.DOTALL)
        if sid_m and title_m:
            sections.append({
                "id": sid_m.group(1).strip(),
                "title": title_m.group(1).strip(),
                "page_refs": [p.strip() for p in page_refs],
                "subsection_refs": [s.strip() for s in sub_refs],
            })

    return {
        "title": title,
        "description": description,
        "pages": pages,
        "sections": sections,
    }

def flatten_pages(wiki_struct: dict) -> list:
    """从 wiki 结构中提取所有 page 列表（用于逐页生成）"""
    return wiki_struct.get("pages", [])

# ── 单个页面的 LLM 调用 ──────────────────────────────────────────────────────

def build_page_system_prompt(language: str, repo_name: str) -> str:
    """为页面生成构建 system prompt"""
    lang_map = {
        "zh": "中文", "ja": "日語", "ko": "韩语", "vi": "越南语",
        "es": "西班牙语", "fr": "法语", "ru": "俄语", "pt-br": "巴西葡萄牙语",
    }
    lang_name = lang_map.get(language, "English")
    return f"""You are an expert code analyst creating wiki content for the {repo_name} repository.
You write comprehensive, well-structured wiki pages in {lang_name} language.

IMPORTANT FORMATTING RULES:
1. Write in {lang_name} language
2. Use proper markdown formatting
3. DO NOT wrap your response in markdown code fences
4. Start directly with the content
5. Include code examples with proper syntax highlighting when relevant
6. Use ## headings for major sections
7. Use bullet points or numbered lists where appropriate
8. Include file path references as inline code

Focus on providing accurate, detailed content that helps developers understand and use the codebase."""

# ── 核心 Wiki 生成逻辑 ───────────────────────────────────────────────────────

async def run_task(task: dict) -> None:
    """
    执行单个 Wiki 生成任务。
    阶段：
      1. fetching   - 获取仓库文件 + README，准备 RAG
      2. structure  - 调用 LLM 确定 Wiki 结构
      3. generating - 逐页调用 LLM 生成内容（支持断点续传）
      4. saving     - 保存到缓存文件系统
    """
    task_id = task["id"]
    provider = task.get("provider", "google")
    model = task.get("model", "MiniMax-M2.7")
    language = task.get("language", "en")
    owner = task.get("owner") or ""
    repo = task.get("repo") or ""
    repo_type = task.get("repo_type", "github")
    repo_url = task.get("repo_url") or ""

    repo_name = f"{owner}/{repo}"
    default_branch = detect_default_branch(repo_url, repo_type, task.get('token')) if repo_url and repo_type != 'local' else 'main'

    # ── 阶段 1: fetching ──────────────────────────────────────────────────
    update_task_status(task_id, "running", current_step="fetching",
                       worker_id=_worker_id)
    logger.info(f"[{task_id}] Step 1/4: fetching repository")

    from api.rag import RAG
    from api.data_pipeline import DatabaseManager

    # 准备 extra_kwargs
    extra_kwargs: Dict[str, Any] = {}
    for field in ("excluded_dirs", "excluded_files", "included_dirs", "included_files"):
        if task.get(field):
            extra_kwargs[field] = task[field]

    # 初始化 RAG 并准备数据库
    rag = RAG(provider=provider, model=model)
    await asyncio.to_thread(
        rag.prepare_retriever,
        repo_url_or_path=repo_url,
        type=repo_type,
        access_token=task.get("token"),
        **extra_kwargs,
    )

    # 获取文件列表用于 LLM
    if hasattr(rag, "db_manager") and rag.db_manager:
        db: DatabaseManager = rag.db_manager
        file_list = []
        if hasattr(db, "file_list"):
            file_list = db.file_list if db.file_list else []
        elif hasattr(db, "docs") and db.docs:
            file_list = [d.meta_data.get("file_path", "") for d in db.docs if hasattr(d, "meta_data")]

        # 获取 README 内容
        readme_content = ""
        for f in file_list:
            fname = f.lower()
            if "readme" in fname and fname.endswith((".md", ".txt", "")):
                try:
                    # 尝试从 db 获取 README 内容
                    if hasattr(db, "docs"):
                        for doc in db.docs:
                            fp = doc.meta_data.get("file_path", "") if hasattr(doc, "meta_data") else ""
                            if "readme" in fp.lower():
                                readme_content = doc.text[:3000] if hasattr(doc, "text") else ""
                                break
                except Exception:
                    pass
                if readme_content:
                    break

        repo_files = file_list
        file_contents: dict[str, str] = {}
        context_documents: list[dict[str, str]] = []
        if hasattr(db, "docs") and db.docs:
            for doc in db.docs:
                if not hasattr(doc, "meta_data"):
                    continue
                file_path = doc.meta_data.get("file_path", "")
                if not file_path:
                    continue
                if hasattr(doc, "text") and doc.text:
                    if file_path not in file_contents:
                        file_contents[file_path] = doc.text
                    context_documents.append({
                        "file_path": file_path,
                        "text": doc.text,
                    })
    else:
        repo_files = []
        readme_content = ""
        file_contents = {}
        context_documents = []

    # ── 阶段 2: structure ──────────────────────────────────────────────────
    update_task_status(task_id, "running", current_step="structure")
    logger.info(f"[{task_id}] Step 2/4: determining wiki structure")

    system_prompt = SIMPLE_CHAT_SYSTEM_PROMPT.format(
        repo_type=repo_type,
        repo_url=repo_url,
        repo_name=repo_name,
        language_name=language,
    )

    structure_prompt = build_shared_structure_prompt(
        owner=owner,
        repo=repo,
        repo_files=repo_files,
        readme=readme_content,
        language=language,
        is_comprehensive=bool(task.get("is_comprehensive", 1)),
    )

    structure_request = SimpleNamespace(
        repo_url=repo_url,
        messages=[SimpleNamespace(role='user', content=structure_prompt)],
        filePath=None,
        token=task.get('token'),
        type=repo_type,
        provider=provider,
        model=model,
        language=language,
        excluded_dirs=task.get('excluded_dirs'),
        excluded_files=task.get('excluded_files'),
        included_dirs=task.get('included_dirs'),
        included_files=task.get('included_files'),
    )

    structure_text = await call_llm_with_retry(
        task_id=task_id,
        request=structure_request,
        step_name="wiki_structure",
    )

    # 解析 Wiki 结构
    wiki_struct = parse_wiki_structure_xml(structure_text)
    pages = flatten_pages(wiki_struct)
    total_pages = len(pages)

    if total_pages == 0:
        # 降级：按行解析
        pages = [{"id": f"page_{i}", "title": line.strip(), "description": ""}
                 for i, line in enumerate(structure_text.splitlines())
                 if len(line.strip()) > 3]
        total_pages = len(pages)

    update_task_status(task_id, "running", total_pages=total_pages, completed_pages=0)
    logger.info(f"[{task_id}] Structure parsed: {total_pages} pages")

    # ── 阶段 3: generating（断点续传）───────────────────────────────────────
    update_task_status(task_id, "running", current_step="generating")
    logger.info(f"[{task_id}] Step 3/4: generating {total_pages} pages")

    checkpoint = load_checkpoint(task_id) or {}
    completed_ids: set = set(checkpoint.get("completed_page_ids", []))
    generated_pages: dict = checkpoint.get("generated_pages", {})
    # 重新构建 wiki_struct（如果从 checkpoint 恢复）
    if "wiki_struct" in checkpoint:
        wiki_struct = checkpoint["wiki_struct"]
    else:
        wiki_struct["pages"] = pages  # 确保最新

    for idx, page in enumerate(pages):
        page_id = page.get("id", f"page_{idx}")
        if page_id in completed_ids:
            logger.info(f"[{task_id}] Skipping page {page_id} (already done)")
            continue

        # 暂停检查
        if is_pause_requested(task_id):
            logger.info(f"[{task_id}] Pause requested, saving checkpoint at page {idx}")
            save_checkpoint(task_id, {
                "completed_page_ids": list(completed_ids),
                "generated_pages": generated_pages,
                "wiki_struct": wiki_struct,
                "structure_text": structure_text,
            })
            update_task_status(
                task_id, "paused",
                current_step="generating",
                completed_pages=len(completed_ids),
                current_page_title=page.get("title"),
            )
            return

        update_task_status(
            task_id, "running",
            current_page_title=page.get("title", ""),
            completed_pages=len(completed_ids),
        )

        # 生成页面内容
        page_system = build_page_system_prompt(language, repo_name)
        retrieval_query = f"{page.get('title', '')}\n{page.get('description', '')}".strip()
        relevant_page_files = expand_relevant_files(page.get("relevant_files", []), repo_files)
        page_context_docs = []
        try:
            retrieved_documents = await asyncio.to_thread(rag, retrieval_query, language)
            if retrieved_documents and retrieved_documents[0].documents:
                page_context_docs = [
                    {
                        "file_path": doc.meta_data.get("file_path", "unknown"),
                        "text": doc.text,
                    }
                    for doc in retrieved_documents[0].documents
                    if hasattr(doc, "meta_data") and hasattr(doc, "text")
                ]
                retrieved_file_paths = [doc["file_path"] for doc in page_context_docs if doc.get("file_path")]
                if retrieved_file_paths:
                    relevant_page_files = merge_page_source_files(
                        relevant_page_files,
                        retrieved_file_paths,
                        max_extra=5,
                    )
        except Exception as retrieval_error:
            logger.warning(f"[{task_id}] Per-page retrieval failed for {page.get('title')}: {retrieval_error}")
            page_context_docs = [doc for doc in context_documents if doc["file_path"] in relevant_page_files]

        page_context_text = build_context_text(page_context_docs)
        file_contents_for_page = {path: file_contents[path] for path in relevant_page_files if path in file_contents}
        page_prompt = build_shared_page_prompt(
            page_title=page.get("title", ""),
            file_paths=relevant_page_files,
            language=language,
            repo_url=repo_url,
            default_branch=default_branch,
            file_contents=file_contents_for_page,
        )
        if page_context_text:
            page_prompt = f"{page_prompt}\n\n<START_OF_CONTEXT>\n{page_context_text}\n<END_OF_CONTEXT>"

        page_request = SimpleNamespace(
            repo_url=repo_url,
            messages=[SimpleNamespace(role='user', content=page_prompt)],
            filePath=None,
            token=task.get('token'),
            type=repo_type,
            provider=provider,
            model=model,
            language=language,
            excluded_dirs=task.get('excluded_dirs'),
            excluded_files=task.get('excluded_files'),
            included_dirs=task.get('included_dirs'),
            included_files=task.get('included_files'),
        )

        page_content = await call_llm_with_retry(
            task_id=task_id,
            request=page_request,
            step_name=f"page:{page.get('title', page_id)}",
        )
        page_content = normalize_source_citation_links(page_content, repo_url, default_branch)
        is_valid, validation_reason = validate_generated_wiki_page(page_content, relevant_page_files)
        if not is_valid:
            page_content = (
                f"# {page.get('title', '')}\n\n"
                f"Unable to generate a grounded wiki page for this section.\n\n"
                f"Reason: {validation_reason}\n\n"
                f"Relevant source files: {', '.join(relevant_page_files)}"
            )

        generated_pages[page_id] = {
            **page,
            "content": page_content,
            "generated_at": int(time.time() * 1000),
        }
        completed_ids.add(page_id)

        # 每页完成后保存断点
        save_checkpoint(task_id, {
            "completed_page_ids": list(completed_ids),
            "generated_pages": generated_pages,
            "wiki_struct": wiki_struct,
            "structure_text": structure_text,
        })
        logger.info(f"[{task_id}] Page {len(completed_ids)}/{total_pages}: {page.get('title')}")

    # ── 阶段 4: saving ──────────────────────────────────────────────────────
    update_task_status(task_id, "running", current_step="saving",
                       completed_pages=total_pages, total_pages=total_pages)
    logger.info(f"[{task_id}] Step 4/4: saving wiki output")

    wiki_output = {
        "task_id": task_id,
        "owner": owner,
        "repo_url": repo_url,
        "repo": {"owner": owner, "repo": repo, "type": repo_type},
        "repo_type": repo_type,
        "language": language,
        "provider": provider,
        "model": model,
        "wiki_structure": wiki_struct,
        "generated_pages": generated_pages,
        "created_at": task.get("created_at"),
        "completed_at": int(time.time() * 1000),
    }
    # 字段名转换：snake_case → camelCase（兼容前端 WikiPage 接口）
    wiki_struct_norm, generated_pages_norm = _normalize_wiki_output(wiki_struct, generated_pages, task)
    wiki_output["wiki_structure"] = wiki_struct_norm
    wiki_output["generated_pages"] = generated_pages_norm
    save_wiki_output(task_id, wiki_output)
    # 同时保存到项目列表可读取的缓存目录
    _save_wiki_output_to_project_cache(wiki_output)

    # 清理 checkpoint 文件
    cp_path = get_task_dir(task_id) / "checkpoint.json"
    if cp_path.exists():
        cp_path.unlink()

    update_task_status(
        task_id, "completed",
        current_step="done",
        completed_pages=total_pages,
        total_pages=total_pages,
    )
    logger.info(f"[{task_id}] Task completed successfully")


# ── Worker 主循环 ─────────────────────────────────────────────────────────────

def _worker_loop() -> None:
    """Worker 主循环（在独立线程中运行）"""
    logger.info(f"Worker {_worker_id} started")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while not _stop_event.is_set():
        try:
            # 1. 释放超时锁
            released = release_stale_locks(LOCK_TIMEOUT)
            if released:
                logger.warning(f"Released {released} stale task lock(s)")

            # 2. 优先恢复 paused 任务，其次取 queued 任务
            task = get_paused_task() or get_next_queued_task()

            if task is None:
                _stop_event.wait(timeout=POLL_INTERVAL)
                continue

            task_id = task["id"]
            logger.info(f"Worker {_worker_id} picked up task {task_id}")

            # 3. 检查是否已取消
            fresh = get_task(task_id)
            if fresh and fresh["status"] in ("cancelled",):
                logger.info(f"Task {task_id} was cancelled, skipping")
                continue

            # 4. 运行任务
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
            _stop_event.wait(timeout=POLL_INTERVAL)

    loop.close()
    logger.info(f"Worker {_worker_id} stopped")

# ── 公开 API ──────────────────────────────────────────────────────────────────

def start_worker() -> None:
    """启动后台 Worker 线程"""
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        logger.info("Worker already running")
        return
    init_db()
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=_worker_loop,
        name="wiki-task-worker",
        daemon=True,
    )
    _worker_thread.start()
    logger.info("Wiki task worker started")

def stop_worker() -> None:
    """停止 Worker 线程"""
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
