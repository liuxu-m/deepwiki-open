# Wiki Grounding 修复计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 消除前端重复定义、强化页面 grounding 校验（section 级引用）、加固失败页策略、增加 embedding 重试。

**Architecture:** 前端收敛到共享 helper，后端 validator 从"全文 2 个 Sources"升级为"每个 H2 section 至少 1 个 Sources"，校验失败页不再写入伪成功内容，embedding 调用增加 retry。

**Tech Stack:** Python FastAPI + adalflow + Next.js 15 + TypeScript + pytest

---

## 背景

当前 4 个已知问题（详见 `docs/plans/2026-04-26-current-wiki-generation-issues.md`）：

1. `page.tsx:152` 有内联 `buildStructureRequestBody`，与 `src/utils/wikiRequestBodies.js` 重复
2. 页面正文关键段落仍缺少 `Sources: [file:line](url)` 格式引用
3. `validate_generated_wiki_page` 仅检查全文 2 个 Sources，校验失败后仍写入伪成功内容
4. embedding 超时/空向量导致 RAG 检索质量下降

---

### Task 1: 消除前端 `buildStructureRequestBody` 重复定义

**Files:**
- Modify: `src/app/[owner]/[repo]/page.tsx:152-171`
- Reference: `src/utils/wikiRequestBodies.js:1-22`

**Step 1: 删除 page.tsx 内联定义，改为 import**

在 `page.tsx` 顶部 import 区域增加：
```typescript
import { buildStructureRequestBody } from '@/utils/wikiRequestBodies';
```

然后删除第 152-171 行的内联 `buildStructureRequestBody` 常量。

**Step 2: 验证 TypeScript 编译通过**

```bash
npx tsc --noEmit
```
Expected: 无新增类型错误。

**Step 3: 提交**

```bash
git add src/app/[owner]/[repo]/page.tsx
git commit -m "refactor: use shared buildStructureRequestBody from wikiRequestBodies"
```

---

### Task 2: 强化 `validate_generated_wiki_page` 到 section 级引用

**Files:**
- Modify: `api/wiki_generation.py:63-74`
- Modify: `tests/unit/test_wiki_generation.py`

**Step 1: 重写校验函数，要求每个 H2 section 至少包含 1 个 `Sources:` 引用**

```python
import re

def validate_generated_wiki_page(markdown: str, file_paths: list[str]) -> tuple[bool, str]:
    # 1. 必须包含 details block
    if '<details>' not in markdown or 'Relevant source files' not in markdown:
        return False, 'Missing Relevant source files details block'

    # 2. 按 H2 拆分 section
    sections = re.split(r'\n(?=## )', markdown)
    # 第一个 section 之前的内容（details block + H1 title）不要求 Sources
    body_sections = [s for s in sections if s.strip().startswith('## ')]

    if len(body_sections) < 2:
        return False, 'At least two H2 sections are required'

    # 3. 每个 H2 section 至少 1 个 Sources:
    sections_without_sources = []
    for sec in body_sections:
        if 'Sources:' not in sec:
            heading = sec.split('\n')[0].strip()
            sections_without_sources.append(heading)

    if sections_without_sources:
        return False, (
            f'Every H2 section must include at least one Sources citation. '
            f'Missing in: {", ".join(sections_without_sources[:3])}'
        )

    # 4. 至少引用 3 个不同文件（不只是 README）
    cited_files = set()
    for match in re.finditer(r'Sources:\s*\[([^:\]]+)', markdown):
        cited_files.add(match.group(1))

    non_readme_files = {f for f in cited_files if 'readme' not in f.lower()}
    if len(non_readme_files) < 2:
        return False, (
            f'Must cite at least 2 non-README source files. '
            f'Found: {", ".join(sorted(non_readme_files)) if non_readme_files else "none"}'
        )

    # 5. 引用的文件必须在 file_paths 中存在
    matched_files = [fp for fp in file_paths if fp in markdown]
    if file_paths and len(matched_files) < min(3, len(file_paths)):
        return False, (
            f'Generated page must reference at least 3 selected source files. '
            f'Matched: {len(matched_files)}/{len(file_paths)}'
        )

    return True, ''
```

**Step 2: 更新已有测试并新增测试用例**

在 `tests/unit/test_wiki_generation.py` 增加：

```python
def test_validate_generated_wiki_page_requires_sources_in_each_h2_section():
    markdown = '''<details>
<summary>Relevant source files</summary>

- [README.md](https://github.com/example/repo/blob/main/README.md)
- [src/main.py](https://github.com/example/repo/blob/main/src/main.py)
- [src/utils.py](https://github.com/example/repo/blob/main/src/utils.py)
</details>

# 项目概览

这是介绍段落。

Sources: [src/main.py:1-10](https://github.com/example/repo/blob/main/src/main.py#L1-L10)

## 架构设计

架构说明段落。

Sources: [src/main.py:20-30](https://github.com/example/repo/blob/main/src/main.py#L20-L30)

## 核心功能

功能描述段落。
Sources: [src/utils.py:5-15](https://github.com/example/repo/blob/main/src/utils.py#L5-L15)
'''

    valid, reason = validate_generated_wiki_page(
        markdown,
        ['README.md', 'src/main.py', 'src/utils.py']
    )

    assert valid, f'Expected valid but got: {reason}'


def test_validate_generated_wiki_page_rejects_missing_section_sources():
    markdown = '''<details>
<summary>Relevant source files</summary>

- [README.md](https://github.com/example/repo/blob/main/README.md)
- [src/main.py](https://github.com/example/repo/blob/main/src/main.py)
</details>

# 项目概览

Sources: [src/main.py:1-10](https://github.com/example/repo/blob/main/src/main.py#L1-L10)

## 架构设计

架构说明段落，但没有 Sources 引用。
'''

    valid, reason = validate_generated_wiki_page(
        markdown,
        ['README.md', 'src/main.py']
    )

    assert valid is False
    assert 'H2 section' in reason


def test_validate_generated_wiki_page_rejects_readme_only_citations():
    markdown = '''<details>
<summary>Relevant source files</summary>

- [README.md](https://github.com/example/repo/blob/main/README.md)
</details>

# 项目概览

Sources: [README.md:1-10](https://github.com/example/repo/blob/main/README.md#L1-L10)

## 安装说明

Sources: [README.md:20-30](https://github.com/example/repo/blob/main/README.md#L20-L30)

## 使用指南

Sources: [README.md:40-50](https://github.com/example/repo/blob/main/README.md#L40-L50)
'''

    valid, reason = validate_generated_wiki_page(
        markdown,
        ['README.md']
    )

    assert valid is False
    assert 'non-README' in reason.lower()
```

**Step 3: 更新已有测试 `test_validate_generated_wiki_page_rejects_single_surface_level_source_block`**

原来的测试只有一个 H2 section 且只有一个 Sources（会被"至少两个 H2 section"规则拒绝，或者因为没有引用非 README 文件而拒绝）。需要更新预期：

```python
def test_validate_generated_wiki_page_rejects_single_surface_level_source_block():
    markdown = '''<details>
<summary>Relevant source files</summary>

- [README.md](https://github.com/livekit/agents/blob/main/README.md)
</details>

# 项目概览

这是一个概览段落。

Sources: [README.md:1-10](https://github.com/livekit/agents/blob/main/README.md#L1-L10)
'''

    valid, reason = validate_generated_wiki_page(markdown, ['README.md', 'livekit-agents/livekit/agents/worker.py'])

    assert valid is False
    # 新版校验会因为缺少 H2 section 或缺少非 README 引用而失败
```

**Step 4: 运行全部单元测试**

```bash
python -m pytest tests/unit/test_wiki_generation.py -v
```
Expected: 所有测试通过。

**Step 5: 提交**

```bash
git add api/wiki_generation.py tests/unit/test_wiki_generation.py
git commit -m "feat: require per-section Sources citations and multi-file coverage in page validation"
```

---

### Task 3: 增加页面校验审计日志 + 加固失败页策略

**Files:**
- Modify: `api/task_worker.py:597-621`
- Modify: `api/wiki_generation.py` (已有函数，无需改动，但增加日志调用)

**Step 1: 在 task_worker.py 中增加校验审计日志**

在 `task_worker.py` 的页面生成循环中（约 597-605 行），改为：

```python
page_content = await call_llm_with_retry(...)
page_content = normalize_source_citation_links(page_content, repo_url, default_branch)
is_valid, validation_reason = validate_generated_wiki_page(page_content, relevant_page_files)

# 审计日志
logger.info(
    f"[{task_id}] Page '{page.get('title', page_id)}' validation: "
    f"valid={is_valid}, reason={validation_reason or 'OK'}, "
    f"structure_files={len(page.get('relevant_files', []))}, "
    f"merged_files={len(relevant_page_files)}, "
    f"content_sources={page_content.count('Sources:')}, "
    f"content_h2={page_content.count('\\n## ')}"
)

if not is_valid:
    # 不再写入伪成功内容，标记为 failed 并跳过
    logger.warning(
        f"[{task_id}] Page '{page.get('title', page_id)}' FAILED grounding validation: "
        f"{validation_reason}"
    )
    generated_pages[page_id] = {
        **page,
        "content": "",
        "generated_at": int(time.time() * 1000),
        "validation_failed": True,
        "validation_reason": validation_reason,
    }
    completed_ids.add(page_id)
    # 保存断点后继续下一页（不阻塞剩余页面）
    save_checkpoint(task_id, {...})
    continue
```

**Step 2: 前端感知校验失败状态**

在 `src/app/[owner]/[repo]/page.tsx` 的页面渲染区域，检测 `validation_failed` 字段：

在 `WikiPage` 接口增加：
```typescript
interface WikiPage {
  // ... existing fields
  validation_failed?: boolean;
  validation_reason?: string;
}
```

页面内容为空且 `validation_failed` 为 true 时，显示"该页面无法生成通过校验的文档"而非空白。

**Step 3: 运行测试**

```bash
python -m pytest tests/unit/ -v
```
Expected: 现有测试通过。

**Step 4: 提交**

```bash
git add api/task_worker.py api/wiki_generation.py src/app/\[owner\]/\[repo\]/page.tsx
git commit -m "feat: add validation audit logging and prevent weak-grounded pages from writing to cache"
```

---

### Task 4: Embedding 调用增加重试机制

**Files:**
- Modify: `api/tools/embedder.py`
- Modify: `api/rag.py` (调用 embedder 处)

**Step 1: 在 embedder 中增加 retry wrapper**

在 `api/tools/embedder.py` 中，为 embedding 调用增加简单的重试装饰器：

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

EMBED_MAX_RETRIES = 3
EMBED_RETRY_DELAY = 2  # seconds

async def embed_with_retry(embed_fn, texts: list[str], **kwargs):
    """对 embedding 调用增加 retry，处理 timeout 和空向量。"""
    last_error = None
    for attempt in range(EMBED_MAX_RETRIES + 1):
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(embed_fn, texts, **kwargs),
                timeout=60
            )
            # 检查空向量
            if result and hasattr(result, 'embeddings'):
                empty_count = sum(1 for e in result.embeddings if not e or all(v == 0 for v in e))
                if empty_count == len(result.embeddings):
                    raise ValueError("All embeddings returned empty vectors")
                if empty_count > 0:
                    logger.warning(
                        f"Embedding batch: {empty_count}/{len(result.embeddings)} empty vectors "
                        f"(attempt {attempt + 1})"
                    )
            return result
        except (asyncio.TimeoutError, ValueError) as e:
            last_error = str(e)
            if attempt < EMBED_MAX_RETRIES:
                delay = EMBED_RETRY_DELAY * (attempt + 1)
                logger.warning(f"Embedding retry {attempt + 1}/{EMBED_MAX_RETRIES} after {delay}s: {last_error}")
                await asyncio.sleep(delay)

    raise RuntimeError(f"Embedding failed after {EMBED_MAX_RETRIES} retries: {last_error}")
```

**Step 2: 在 RAG 初始化中接入 retry**

在 `api/rag.py` 的 `prepare_retriever` 方法中，找到 embedding 调用点，接入 `embed_with_retry`。

**Step 3: 运行测试**

```bash
python -m pytest tests/unit/test_all_embedders.py tests/unit/test_google_embedder.py -v
```
Expected: 测试通过，无新增错误。

**Step 4: 提交**

```bash
git add api/tools/embedder.py api/rag.py
git commit -m "feat: add retry with backoff for embedding calls"
```

---

### Task 5: 提交 STARTUP.md 改动

**Files:**
- `STARTUP.md` (已修改，未提交)

**Step 1: 提交**

```bash
git add STARTUP.md
git commit -m "chore: remove redundant PORT override line from startup docs"
```

---

## 验证清单

完成所有 task 后运行：

```bash
# 后端单元测试
python -m pytest tests/unit/ -v

# 前端类型检查
npx tsc --noEmit

# 前端构建
npm run build
```

Expected: 全部通过，无回归。
