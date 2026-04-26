from api.page_source_merge import merge_page_source_files


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
