from api.task_queue import create_task, get_task, init_db, request_pause, resume_task, update_task_status


def test_resume_task_allows_pause_requested_state():
    init_db()
    task = create_task(
        owner='AsyncFuncAI',
        repo='deepwiki-open',
        repo_type='github',
        repo_url='https://github.com/AsyncFuncAI/deepwiki-open',
        language='zh',
    )

    update_task_status(task['id'], 'running')
    assert request_pause(task['id']) is True

    paused_request_task = get_task(task['id'])
    assert paused_request_task['status'] == 'pause_requested'

    assert resume_task(task['id']) is True

    resumed_task = get_task(task['id'])
    assert resumed_task['status'] == 'queued'


def test_resume_task_still_allows_paused_state():
    init_db()
    task = create_task(
        owner='AsyncFuncAI',
        repo='deepwiki-open',
        repo_type='github',
        repo_url='https://github.com/AsyncFuncAI/deepwiki-open',
        language='zh',
    )

    update_task_status(task['id'], 'paused')

    assert resume_task(task['id']) is True

    resumed_task = get_task(task['id'])
    assert resumed_task['status'] == 'queued'
