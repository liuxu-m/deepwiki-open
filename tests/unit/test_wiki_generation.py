from api.wiki_generation import (
    build_shared_page_prompt,
    build_context_text,
    build_shared_structure_prompt,
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
