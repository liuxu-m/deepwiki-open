from api.page_source_merge import merge_page_source_files, prioritize_page_source_files


def test_prioritize_page_source_files_limits_readme_overflow_and_keeps_code_files():
    prioritized = prioritize_page_source_files([
        'README.md',
        'README.zh.md',
        'README.ja.md',
        'src/app/page.tsx',
        'src/components/Markdown.tsx',
        'api/task_worker.py',
    ])

    assert 'src/app/page.tsx' in prioritized
    assert 'src/components/Markdown.tsx' in prioritized
    assert 'api/task_worker.py' in prioritized
    assert len([p for p in prioritized if 'readme' in p.lower()]) <= 1


def test_merge_page_source_files_preserves_base_files_first():
    merged = merge_page_source_files(
        base_files=['README.md', 'docs/architecture.md'],
        retrieved_files=['src/worker.py', 'README.md', 'src/session.py'],
        max_extra=5,
    )

    assert merged[:2] == ['README.md', 'docs/architecture.md']
    assert 'src/worker.py' in merged
    assert 'src/session.py' in merged


def test_merge_page_source_files_limits_extra_retrieved_files():
    merged = merge_page_source_files(
        base_files=['README.md'],
        retrieved_files=['a.py', 'b.py', 'c.py'],
        max_extra=2,
    )

    assert merged == ['README.md', 'a.py', 'b.py']
