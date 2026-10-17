import logging

from mcp_server.tools.web_search import FALLBACK_MESSAGE, web_search


class FakeResponse:
    def __init__(self, json_data=None, content=b"", status_code=200):
        self._json_data = json_data
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_web_search_returns_fallback_when_no_organic_results(monkeypatch):
    monkeypatch.setattr(
        "mcp_server.tools.web_search.requests.get",
        lambda url, params=None, timeout=None: FakeResponse(json_data={"organic_results": []}),
    )
    assert web_search("query", "fake-key") == FALLBACK_MESSAGE


def test_web_search_returns_page_text_on_success(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        if "serpapi" in url:
            return FakeResponse(json_data={"organic_results": [{"link": "https://example.com"}]})
        return FakeResponse(content=b"<html><body>Hello world</body></html>")

    monkeypatch.setattr("mcp_server.tools.web_search.requests.get", fake_get)
    result = web_search("query", "fake-key", max_results=1)

    assert "Hello world" in result
    assert "https://example.com" in result


def test_web_search_returns_fallback_when_serpapi_fails(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        raise ConnectionError("serpapi down")

    monkeypatch.setattr("mcp_server.tools.web_search.requests.get", fake_get)
    assert web_search("query", "fake-key") == FALLBACK_MESSAGE


def test_web_search_skips_unreadable_pages_but_returns_others(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        if "serpapi" in url:
            return FakeResponse(json_data={"organic_results": [
                {"link": "https://bad.com"}, {"link": "https://good.com"}]})
        if "bad.com" in url:
            raise ConnectionError("page down")
        return FakeResponse(content=b"<html><body>Good content</body></html>")

    monkeypatch.setattr("mcp_server.tools.web_search.requests.get", fake_get)
    result = web_search("query", "fake-key", max_results=2)

    assert "Good content" in result
    assert "bad.com" not in result


def test_web_search_returns_fallback_when_every_page_fails(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        if "serpapi" in url:
            return FakeResponse(json_data={"organic_results": [{"link": "https://bad.com"}]})
        raise ConnectionError("page down")

    monkeypatch.setattr("mcp_server.tools.web_search.requests.get", fake_get)
    assert web_search("query", "fake-key") == FALLBACK_MESSAGE


def test_web_search_logs_exception_on_search_failure(caplog, monkeypatch):
    def fake_get(url, params=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("mcp_server.tools.web_search.requests.get", fake_get)
    with caplog.at_level(logging.ERROR):
        result = web_search("query", "fake-key")

    assert result == FALLBACK_MESSAGE
    assert "web_search failed" in caplog.text
