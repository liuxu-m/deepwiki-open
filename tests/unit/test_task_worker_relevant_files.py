from api.task_worker import expand_relevant_files


def test_expand_relevant_files_replaces_directories_with_matching_files():
    repo_files = [
        'multica/models/base.py',
        'multica/models/runner.py',
        'multica/data/loader.py',
        'multica/trainers/core.py',
        'README.md',
    ]

    result = expand_relevant_files(
        ['multica/models/', 'multica/data/', 'multica/trainers/'],
        repo_files,
        per_directory_limit=2,
        total_limit=5,
    )

    assert 'multica/models/' not in result
    assert 'multica/data/' not in result
    assert 'multica/trainers/' not in result
    assert 'multica/models/base.py' in result
    assert 'multica/models/runner.py' in result
    assert 'multica/data/loader.py' in result
    assert 'multica/trainers/core.py' in result


def test_expand_relevant_files_keeps_explicit_files_and_caps_output():
    repo_files = [
        'multica/models/base.py',
        'multica/models/runner.py',
        'multica/models/extra.py',
        'README.md',
    ]

    result = expand_relevant_files(
        ['README.md', 'multica/models/'],
        repo_files,
        per_directory_limit=2,
        total_limit=3,
    )

    assert result[0] == 'README.md'
    assert len(result) == 3
    assert 'multica/models/' not in result
