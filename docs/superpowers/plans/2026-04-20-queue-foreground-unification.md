# Queue-Foreground Wiki Generation Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make background queue wiki generation use the same generation engine as foreground wiki generation so queue output quality, context grounding, and citation behavior match the already-good foreground results.

**Architecture:** Keep the queue system for orchestration only: task persistence, progress tracking, retries, and cache writes. Extract the foreground generation pipeline into shared backend services for structure generation, page context assembly, page prompt construction, output normalization, and grounding validation; then make the queue worker call those shared services instead of maintaining a separate generation path.

**Tech Stack:** Python, FastAPI, Next.js, React, SQLite, AdalFlow RAG

---

### Task 1: Define shared backend generation interfaces

**Files:**
- Create: `api/wiki_generation_service.py`
- Modify: `api/wiki_generation.py`
- Test: `tests/unit/test_wiki_generation.py`

- [ ] **Step 1: Write a failing test for a shared structure prompt builder**

Add a test that asserts a shared structure builder includes repository file tree, README content, and strict `relevant_files` requirements.

```python
def test_build_shared_structure_prompt_mentions_actual_repo_files_requirement():
    prompt = build_shared_structure_prompt(
        owner='safishamsi',
        repo='graphify',
        repo_files=['README.md', 'graphify/api.py'],
        readme='# Graphify',
        language='zh',
        is_comprehensive=True,
    )

    assert '<wiki_structure>' in prompt
    assert 'relevant_files should be actual files from the repository' in prompt
    assert 'README.md' in prompt
    assert 'graphify/api.py' in prompt
```

- [ ] **Step 2: Run the structure prompt test to verify it fails if the interface is missing**

Run: `pytest tests/unit/test_wiki_generation.py::test_build_shared_structure_prompt_mentions_actual_repo_files_requirement -q`
Expected: FAIL with missing import or missing function before implementation.

- [ ] **Step 3: Add the shared structure builder to `api/wiki_generation.py`**

Implement a pure function that mirrors the current foreground structure prompt requirements and returns one complete prompt string.

```python
def build_shared_structure_prompt(
    owner: str,
    repo: str,
    repo_files: list[str],
    readme: str,
    language: str,
    is_comprehensive: bool,
) -> str:
    ...
```

- [ ] **Step 4: Write a failing test for shared page prompt assembly**

Ensure a page prompt contains `<details>`, file links, source contents, and `Sources:` rules.

```python
def test_build_shared_page_prompt_includes_relevant_files_and_citation_rules():
    prompt = build_shared_page_prompt(
        page_title='API 参考',
        file_paths=['graphify/api.py', 'README.md'],
        language='zh',
        repo_url='https://github.com/safishamsi/graphify',
        default_branch='main',
        file_contents={'graphify/api.py': 'def create_app():\n    return app\n'},
    )

    assert '<details>' in prompt
    assert 'Relevant source files' in prompt
    assert 'Sources:' in prompt
    assert 'graphify/api.py' in prompt
    assert 'def create_app()' in prompt
```

- [ ] **Step 5: Run the page prompt test to verify it fails before implementation**

Run: `pytest tests/unit/test_wiki_generation.py::test_build_shared_page_prompt_includes_relevant_files_and_citation_rules -q`
Expected: FAIL with missing function or assertion failure before implementation.

- [ ] **Step 6: Implement shared page prompt and context grouping helpers**

Add these focused helpers to `api/wiki_generation.py`:

```python
def build_repo_file_url(repo_url: str, file_path: str, branch: str = 'main') -> str:
    ...


def build_context_text(documents: list[dict[str, str]]) -> str:
    ...


def build_shared_page_prompt(
    page_title: str,
    file_paths: list[str],
    language: str,
    repo_url: str,
    default_branch: str = 'main',
    file_contents: Optional[dict[str, str]] = None,
) -> str:
    ...
```

- [ ] **Step 7: Run all shared generation unit tests**

Run: `pytest tests/unit/test_wiki_generation.py -q`
Expected: PASS.

### Task 2: Extract foreground-style context collection into a reusable backend service

**Files:**
- Create: `api/wiki_generation_service.py`
- Modify: `api/simple_chat.py`
- Modify: `api/websocket_wiki.py`
- Test: `tests/unit/test_wiki_generation_service.py`

- [ ] **Step 1: Write a failing test for grouped document context generation**

Create a new unit test file that proves grouped context assembly matches the current foreground format.

```python
from api.wiki_generation_service import format_documents_as_context


def test_format_documents_as_context_groups_text_by_file_path():
    docs = [
        {'file_path': 'graphify/api.py', 'text': 'def create_app():\n    return app'},
        {'file_path': 'graphify/api.py', 'text': 'def create_router():\n    return router'},
        {'file_path': 'README.md', 'text': '# Graphify'},
    ]

    context = format_documents_as_context(docs)

    assert '## File Path: graphify/api.py' in context
    assert 'def create_app()' in context
    assert 'def create_router()' in context
    assert '## File Path: README.md' in context
```

- [ ] **Step 2: Run the new service test to verify it fails before implementation**

Run: `pytest tests/unit/test_wiki_generation_service.py::test_format_documents_as_context_groups_text_by_file_path -q`
Expected: FAIL with missing module or function.

- [ ] **Step 3: Implement shared context collection helpers**

Create `api/wiki_generation_service.py` with narrow, reusable helpers extracted from the foreground backend path.

```python
def format_documents_as_context(documents: list[dict[str, str]]) -> str:
    ...


def extract_file_contents_from_docs(raw_docs: list) -> dict[str, str]:
    ...


def filter_documents_for_files(documents: list[dict[str, str]], file_paths: list[str]) -> list[dict[str, str]]:
    ...
```

- [ ] **Step 4: Replace duplicated grouping logic in `api/simple_chat.py` with shared helpers**

Use the shared formatter without changing request behavior.

```python
from api.wiki_generation_service import format_documents_as_context
```

and replace the inline grouping with:

```python
context_text = format_documents_as_context([
    {
        'file_path': doc.meta_data.get('file_path', 'unknown'),
        'text': doc.text,
    }
    for doc in documents
])
```

- [ ] **Step 5: Replace duplicated grouping logic in `api/websocket_wiki.py` with the same shared helpers**

Apply the same change as in `api/simple_chat.py` so the two foreground backends remain behaviorally identical.

- [ ] **Step 6: Run focused tests and syntax checks**

Run: `pytest tests/unit/test_wiki_generation.py tests/unit/test_wiki_generation_service.py -q && python -m py_compile api/wiki_generation.py api/wiki_generation_service.py api/simple_chat.py api/websocket_wiki.py`
Expected: PASS.

### Task 3: Convert queue page generation into an async wrapper over the shared foreground-style backend logic

**Files:**
- Modify: `api/task_worker.py`
- Modify: `api/wiki_generation_service.py`
- Test: `tests/unit/test_task_worker_relevant_files.py`
- Test: `tests/unit/test_wiki_generation_service.py`

- [ ] **Step 1: Write a failing test for queue page prompt assembly using file contents and grouped context**

Add a test that proves queue page generation uses both actual file contents and grouped page context.

```python
def test_build_queue_page_prompt_uses_source_contents_and_context():
    page = {
        'title': 'API 参考',
        'relevant_files': ['graphify/api.py'],
    }
    file_contents = {'graphify/api.py': 'def create_app():\n    return app\n'}
    context_docs = [{'file_path': 'graphify/api.py', 'text': 'class App: ...'}]

    prompt = build_shared_page_prompt(
        page_title=page['title'],
        file_paths=page['relevant_files'],
        language='zh',
        repo_url='https://github.com/safishamsi/graphify',
        default_branch='main',
        file_contents=file_contents,
    )
    context = format_documents_as_context(context_docs)

    assert 'def create_app()' in prompt
    assert 'class App:' in context
```

- [ ] **Step 2: Run the queue-related tests to verify they fail if the shared service is not wired in**

Run: `pytest tests/unit/test_task_worker_relevant_files.py tests/unit/test_wiki_generation_service.py -q`
Expected: FAIL before the queue worker is fully migrated.

- [ ] **Step 3: Replace queue page prompt construction with shared helpers only**

In `api/task_worker.py`, remove queue-specific prompt assembly from the page generation path and use:

```python
relevant_page_files = expand_relevant_files(page.get('relevant_files', []), repo_files)
page_context_docs = filter_documents_for_files(context_documents, relevant_page_files)
page_context_text = format_documents_as_context(page_context_docs)
page_prompt = build_shared_page_prompt(
    page_title=page.get('title', ''),
    file_paths=relevant_page_files,
    language=language,
    repo_url=repo_url,
    default_branch='main',
    file_contents=file_contents,
)
if page_context_text:
    page_prompt = f"{page_prompt}\n\n<START_OF_CONTEXT>\n{page_context_text}\n<END_OF_CONTEXT>"
```

- [ ] **Step 4: Keep queue-only orchestration behavior separate from generation policy**

Do not change queue responsibilities such as:
- checkpoint writes
- pause/resume
- retry handling
- task progress updates
- final cache save

Only replace generation policy and context assembly.

- [ ] **Step 5: Run queue-related tests to verify green**

Run: `pytest tests/unit/test_task_worker_relevant_files.py tests/unit/test_wiki_generation_service.py -q`
Expected: PASS.

### Task 4: Convert queue structure generation into the shared foreground-aligned structure builder

**Files:**
- Modify: `api/task_worker.py`
- Modify: `api/wiki_generation.py`
- Test: `tests/unit/test_wiki_generation.py`

- [ ] **Step 1: Write a failing test asserting queue structure prompt comes from the shared builder**

Add an assertion that the shared structure prompt contains the current foreground-compatible XML contract and real file-tree inputs.

```python
def test_build_shared_structure_prompt_requires_actual_repository_files():
    prompt = build_shared_structure_prompt(
        owner='safishamsi',
        repo='graphify',
        repo_files=['README.md', 'graphify/api.py'],
        readme='# Graphify',
        language='zh',
        is_comprehensive=True,
    )

    assert 'Create a structured wiki' in prompt
    assert 'The relevant_files should be actual files from the repository' in prompt
    assert '<file_tree>' in prompt
```

- [ ] **Step 2: Run the structure test to verify red if not yet aligned**

Run: `pytest tests/unit/test_wiki_generation.py::test_build_shared_structure_prompt_requires_actual_repository_files -q`
Expected: FAIL if contract is missing.

- [ ] **Step 3: Replace queue-specific structure prompt usage**

In `api/task_worker.py`, swap:

```python
structure_prompt = _build_structure_prompt(...)
```

for:

```python
structure_prompt = build_shared_structure_prompt(
    owner=owner,
    repo=repo,
    repo_files=repo_files,
    readme=readme_content,
    language=language,
    is_comprehensive=bool(task.get('is_comprehensive', 1)),
)
```

- [ ] **Step 4: Keep old private helpers only if still required by unrelated code**

If `_build_structure_prompt` becomes unused, remove it in a separate green step; if any other code still uses it, leave it alone until a follow-up cleanup task.

- [ ] **Step 5: Run structure-focused tests**

Run: `pytest tests/unit/test_wiki_generation.py -q`
Expected: PASS.

### Task 5: Add grounding validation so queue refuses to save obviously fake pages

**Files:**
- Modify: `api/wiki_generation_service.py`
- Modify: `api/task_worker.py`
- Test: `tests/unit/test_wiki_generation_service.py`

- [ ] **Step 1: Write a failing test for missing citation rejection**

```python
from api.wiki_generation_service import validate_generated_wiki_page


def test_validate_generated_wiki_page_rejects_missing_sources():
    valid, reason = validate_generated_wiki_page(
        markdown='# Title\n\nNo citations here',
        file_paths=['graphify/api.py'],
    )

    assert valid is False
    assert 'Sources' in reason
```

- [ ] **Step 2: Run the new validation test to verify it fails before implementation**

Run: `pytest tests/unit/test_wiki_generation_service.py::test_validate_generated_wiki_page_rejects_missing_sources -q`
Expected: FAIL with missing function.

- [ ] **Step 3: Implement a minimal grounding validator**

Add to `api/wiki_generation_service.py`:

```python
def validate_generated_wiki_page(markdown: str, file_paths: list[str]) -> tuple[bool, str]:
    if 'Sources:' not in markdown:
        return False, 'Missing Sources citations'
    if not any(file_path in markdown for file_path in file_paths):
        return False, 'Generated page does not reference selected source files'
    return True, ''
```

- [ ] **Step 4: Use validation in the queue worker before saving page content**

In `api/task_worker.py`, after normalization and before `generated_pages[page_id] = ...`:

```python
is_valid, validation_reason = validate_generated_wiki_page(page_content, relevant_page_files)
if not is_valid:
    page_content = (
        f"# {page.get('title', '')}\n\n"
        f"Unable to generate a grounded wiki page for this section.\n\n"
        f"Reason: {validation_reason}\n\n"
        f"Relevant source files: {', '.join(relevant_page_files)}"
    )
```

- [ ] **Step 5: Run validation and queue tests**

Run: `pytest tests/unit/test_wiki_generation_service.py tests/unit/test_task_worker_relevant_files.py -q`
Expected: PASS.

### Task 6: Verify that queue and foreground share generation logic without changing foreground behavior

**Files:**
- Modify: `api/wiki_generation.py`
- Modify: `api/wiki_generation_service.py`
- Modify: `api/task_worker.py`
- Modify: `api/simple_chat.py`
- Modify: `api/websocket_wiki.py`
- Test: `tests/unit/test_wiki_generation.py`
- Test: `tests/unit/test_wiki_generation_service.py`
- Test: `tests/unit/test_task_worker_relevant_files.py`

- [ ] **Step 1: Run all targeted backend tests**

Run: `pytest tests/unit/test_wiki_generation.py tests/unit/test_wiki_generation_service.py tests/unit/test_task_worker_relevant_files.py -q`
Expected: PASS.

- [ ] **Step 2: Run Python syntax verification on all touched backend files**

Run: `python -m py_compile api/wiki_generation.py api/wiki_generation_service.py api/task_worker.py api/simple_chat.py api/websocket_wiki.py`
Expected: PASS.

- [ ] **Step 3: Run the project build to verify the untouched foreground UI still builds**

Run: `npm run build`
Expected: PASS with no new errors; existing lint warnings may remain unchanged.

- [ ] **Step 4: Create a new queue generation for a known repo and verify the output is grounded**

Run the app, submit a queue refresh for `https://github.com/safishamsi/graphify`, then inspect:
- the latest task in `~/.adalflow/wiki_tasks.db`
- the cache file `~/.adalflow/wikicache/deepwiki_cache_github_safishamsi_graphify_zh.json`

Expected:
- `repo_url` is the real GitHub URL
- pages include `Sources:` when grounded content is generated
- obviously fake pages are replaced by the explicit grounded-failure message instead of hallucinated wiki prose

- [ ] **Step 5: Commit the unification changes**

```bash
git add api/wiki_generation.py api/wiki_generation_service.py api/task_worker.py api/simple_chat.py api/websocket_wiki.py tests/unit/test_wiki_generation.py tests/unit/test_wiki_generation_service.py tests/unit/test_task_worker_relevant_files.py
git commit -m "refactor: unify queue wiki generation with foreground pipeline"
```
