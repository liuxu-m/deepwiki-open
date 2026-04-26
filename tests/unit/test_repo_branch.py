from api.repo_branch import detect_default_branch


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_detect_default_branch_for_github(monkeypatch):
    def fake_get(url, headers=None, timeout=10):
        return _Response(200, {'default_branch': 'master'})

    monkeypatch.setattr('api.repo_branch.requests.get', fake_get)

    branch = detect_default_branch('https://github.com/livekit/agents', 'github')
    assert branch == 'master'


def test_detect_default_branch_falls_back_to_main(monkeypatch):
    def fake_get(url, headers=None, timeout=10):
        return _Response(404, {})

    monkeypatch.setattr('api.repo_branch.requests.get', fake_get)

    branch = detect_default_branch('https://github.com/livekit/agents', 'github')
    assert branch == 'main'
