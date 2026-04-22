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


def test_build_repo_file_url_ignores_unknown_host():
    result = build_repo_file_url('http://example/safishamsi/graphify', 'README.md')

    assert result == ''


def test_normalize_source_citation_links_rewrites_placeholder_link():
    markdown = 'Sources: [README.md:1-10](#source:README.md:1-10)'

    normalized = normalize_source_citation_links(markdown, 'https://github.com/safishamsi/graphify')

    assert 'https://github.com/safishamsi/graphify/blob/main/README.md#L1-L10' in normalized


def test_validate_generated_wiki_page_rejects_missing_sources():
    valid, reason = validate_generated_wiki_page('# Title\n\nNo citations here', ['graphify/api.py'])

    assert valid is False
    assert 'details' in reason.lower()


def test_validate_generated_wiki_page_requires_relevant_sources_details_block():
    markdown = '# Title\n\nSources: [graphify/api.py:1](https://github.com/safishamsi/graphify/blob/main/graphify/api.py#L1)'

    valid, reason = validate_generated_wiki_page(markdown, ['graphify/api.py'])

    assert valid is False
    assert 'details' in reason.lower()
