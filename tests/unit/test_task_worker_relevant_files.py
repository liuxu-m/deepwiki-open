from api.task_worker import expand_relevant_files, _normalize_wiki_output


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


def test_normalize_wiki_output_preserves_raw_content_and_validation_flags():
    wiki_struct = {
        'title': 'Demo Wiki',
        'description': 'demo',
        'pages': [
            {
                'id': 'page-1',
                'title': 'Overview',
                'importance': 'high',
                'relevant_files': ['README.md'],
                'related_pages': [],
                'parent_section': '',
            }
        ],
        'sections': [],
    }
    generated_pages = {
        'page-1': {
            'id': 'page-1',
            'title': 'Overview',
            'importance': 'high',
            'relevant_files': ['README.md'],
            'related_pages': [],
            'content': '# Overview\n\nBody',
            'raw_content': '# Overview\n\nBody',
            'validation_failed': True,
            'validation_reason': 'Must cite at least 2 non-README source files',
        }
    }

    struct, pages = _normalize_wiki_output(wiki_struct, generated_pages, {})

    assert struct['pages'][0]['content'] == '# Overview\n\nBody'
    assert pages['page-1']['content'] == '# Overview\n\nBody'
    assert pages['page-1']['raw_content'] == '# Overview\n\nBody'
    assert pages['page-1']['validation_failed'] is True
    assert pages['page-1']['validation_reason'] == 'Must cite at least 2 non-README source files'


