from api.wiki_generation import (
    build_shared_page_prompt,
    build_context_text,
    build_shared_structure_prompt,
    build_repo_file_url,
    normalize_source_citation_links,
    validate_generated_wiki_page,
)


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
    assert 'The very first thing on the page MUST be a `<details>` block' in prompt
    assert 'You MUST cite AT LEAST 5 different source files' in prompt


def test_build_context_text_groups_documents_by_file_path():
    docs = [
        {'file_path': 'graphify/api.py', 'text': 'def create_app():\n    return app'},
        {'file_path': 'graphify/api.py', 'text': 'def create_router():\n    return router'},
        {'file_path': 'README.md', 'text': '# Graphify'},
    ]

    context_text = build_context_text(docs)

    assert '## File Path: graphify/api.py' in context_text
    assert 'def create_app()' in context_text
    assert 'def create_router()' in context_text
    assert '## File Path: README.md' in context_text


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
    assert 'Extensibility and Customization' in prompt
    assert 'Model Integration' in prompt


def test_build_shared_structure_prompt_includes_files_beyond_200_entries():
    repo_files = [f'src/module_{index}.py' for index in range(205)]

    prompt = build_shared_structure_prompt(
        owner='safishamsi',
        repo='graphify',
        repo_files=repo_files,
        readme='# Graphify',
        language='en',
        is_comprehensive=False,
    )

    assert 'src/module_204.py' in prompt


def test_build_repo_file_url_uses_explicit_default_branch():
    result = build_repo_file_url('https://github.com/livekit/agents', 'README.md', branch='master')

    assert result == 'https://github.com/livekit/agents/blob/master/README.md'


def test_build_repo_file_url_ignores_unknown_host():
    result = build_repo_file_url('http://example/safishamsi/graphify', 'README.md')

    assert result == ''


def test_normalize_source_citation_links_normalizes_windows_separators():
    markdown = 'Sources: [livekit-plugins\\livekit-plugins-openai\\livekit\\plugins\\openai\\__init__.py:40-55](#source:livekit-plugins\\livekit-plugins-openai\\livekit\\plugins\\openai\\__init__.py:40-55)'

    normalized = normalize_source_citation_links(markdown, 'https://github.com/livekit/agents')

    assert 'livekit-plugins/livekit-plugins-openai/livekit/plugins/openai/__init__.py#L40-L55' in normalized
    assert '\\' not in normalized

    valid, reason = validate_generated_wiki_page('# Title\n\nNo citations here', ['graphify/api.py'])

    assert valid is False
    assert 'details' in reason.lower()


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
    # Fails because: only 1 H2 section (needs 2+) or only README citations
    assert 'H2' in reason or 'non-README' in reason.lower()


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


def test_validate_generated_wiki_page_allows_summary_sections_without_sources():
    markdown = '''<details>
<summary>Relevant source files</summary>

- [README.md](https://github.com/example/repo/blob/main/README.md)
- [src/main.py](https://github.com/example/repo/blob/main/src/main.py)
- [src/utils.py](https://github.com/example/repo/blob/main/src/utils.py)
</details>

# 项目概览

Sources: [src/main.py:1-10](https://github.com/example/repo/blob/main/src/main.py#L1-L10)

## 架构设计

架构说明段落。

Sources: [src/main.py:20-30](https://github.com/example/repo/blob/main/src/main.py#L20-L30)

## 核心功能

功能描述段落。

Sources: [src/utils.py:5-15](https://github.com/example/repo/blob/main/src/utils.py#L5-L15)

## 总结

这是总结段落，没有额外 Sources。
'''

    valid, reason = validate_generated_wiki_page(
        markdown,
        ['README.md', 'src/main.py', 'src/utils.py']
    )

    assert valid, f'Expected valid but got: {reason}'


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
    assert 'non-readme' in reason.lower()

