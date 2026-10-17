import pytest

from app.llm_providers import get_provider
from app.llm_providers.base import LLMProviderError
from app.llm_providers.gemini import GeminiProvider
from app.llm_providers.openai_compat import OpenAICompatProvider

MESSAGES = [
    {"role": "system", "content": "sys"},
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": "hello"},
    {"role": "user", "content": "again"},
]


def test_gemini_build_payload_maps_roles():
    p = GeminiProvider(api_key="k", model="m")
    payload = p.build_payload(MESSAGES)
    assert payload["systemInstruction"] == {"parts": [{"text": "sys"}]}
    roles = [c["role"] for c in payload["contents"]]
    assert roles == ["user", "model", "user"]
    assert payload["contents"][0]["parts"] == [{"text": "hi"}]


def test_gemini_extract_text():
    data = {"candidates": [{"content": {"parts": [{"text": "a"}, {"text": "b"}]}}]}
    assert GeminiProvider(api_key="k", model="m").extract_text(data) == "ab"


def test_gemini_extract_text_raises_on_empty():
    with pytest.raises(LLMProviderError):
        GeminiProvider(api_key="k", model="m").extract_text({"candidates": []})


def test_openai_compat_build_payload():
    p = OpenAICompatProvider(base_url="http://x", model="m")
    payload = p.build_payload(MESSAGES)
    assert payload == {"model": "m", "messages": MESSAGES, "temperature": 0}


def test_openai_compat_extract_text():
    data = {"choices": [{"message": {"content": "out"}}]}
    assert OpenAICompatProvider(base_url="http://x", model="m").extract_text(data) == "out"


def test_get_provider_selects_gemini(monkeypatch):
    monkeypatch.setattr("app.llm_providers.settings.llm_provider", "gemini")
    assert isinstance(get_provider(), GeminiProvider)


def test_get_provider_selects_openai_compat(monkeypatch):
    monkeypatch.setattr("app.llm_providers.settings.llm_provider", "openai_compat")
    assert isinstance(get_provider(), OpenAICompatProvider)


def test_get_provider_rejects_unknown(monkeypatch):
    monkeypatch.setattr("app.llm_providers.settings.llm_provider", "nope")
    with pytest.raises(LLMProviderError):
        get_provider()


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=self)

    def json(self):
        return self._json


async def test_gemini_retries_on_503_then_succeeds(monkeypatch):
    import app.llm_providers.gemini as gm

    attempts = []
    ok = {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            attempts.append(headers)
            return _FakeResponse(503) if len(attempts) < 3 else _FakeResponse(200, ok)

    monkeypatch.setattr(gm.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(gm, "RETRY_DELAYS", [0, 0])

    result = await GeminiProvider(api_key="sekret", model="m").complete(
        [{"role": "user", "content": "x"}]
    )
    assert result == "hi"
    assert len(attempts) == 3
    assert attempts[0]["x-goog-api-key"] == "sekret"  # key travels in a header


async def test_gemini_raises_after_exhausting_retries(monkeypatch):
    import app.llm_providers.gemini as gm

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            return _FakeResponse(503)

    monkeypatch.setattr(gm.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(gm, "RETRY_DELAYS", [0, 0])

    with pytest.raises(LLMProviderError):
        await GeminiProvider(api_key="k", model="m").complete([{"role": "user", "content": "x"}])
