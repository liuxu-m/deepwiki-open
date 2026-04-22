from types import SimpleNamespace

import pytest

from api import chat_runtime


class _FakeModel:
    def __init__(self):
        self.api_kwargs_seen = None

    async def acall(self, api_kwargs=None, model_type=None):
        self.api_kwargs_seen = api_kwargs
        return 'ok'


@pytest.mark.asyncio
async def test_run_chat_once_disables_stream_for_openai_compatible_calls(monkeypatch):
    fake_model = _FakeModel()

    async def fake_build_chat_runtime(request):
        return fake_model, {'stream': True, 'messages': []}, 'prompt'

    monkeypatch.setattr(chat_runtime, 'build_chat_runtime', fake_build_chat_runtime)

    request = SimpleNamespace(provider='openai')
    result = await chat_runtime.run_chat_once(request)

    assert result == 'ok'
    assert fake_model.api_kwargs_seen['stream'] is False
