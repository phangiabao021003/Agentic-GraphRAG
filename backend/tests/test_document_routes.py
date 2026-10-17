import uuid

from fastapi.testclient import TestClient

import app.api.documents as doc_mod
from app.main import app


def _register(client):
    resp = client.post(
        "/auth/register",
        json={"email": f"{uuid.uuid4()}@example.com", "password": "correct horse battery staple"},
    )
    return resp.json()["access_token"]


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


def _fake_client(captured, response_json):
    class FakeClient:
        def __init__(self, timeout=None):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, files=None):
            captured.update(url=url, files=files)
            return FakeResponse(response_json)

        async def get(self, url):
            captured["url"] = url
            return FakeResponse(response_json)

    return FakeClient


def test_upload_rejects_non_pdf():
    with TestClient(app) as client:
        token = _register(client)
        resp = client.post("/documents", files={"file": ("notes.txt", b"x", "text/plain")},
                           headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


def test_upload_forwards_pdf_to_mcp_server(monkeypatch):
    captured = {}
    monkeypatch.setattr(doc_mod.httpx, "AsyncClient",
                        _fake_client(captured, {"status": "success", "message": "ingested"}))
    with TestClient(app) as client:
        token = _register(client)
        resp = client.post("/documents", files={"file": ("bible.pdf", b"%PDF-", "application/pdf")},
                           headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "message": "ingested"}
    assert captured["url"].endswith("/internal/ingest")
    assert captured["files"]["file"][0] == "bible.pdf"


def test_list_documents_proxies(monkeypatch):
    captured = {}
    monkeypatch.setattr(doc_mod.httpx, "AsyncClient",
                        _fake_client(captured, {"doc_ids": ["a.pdf"]}))
    with TestClient(app) as client:
        token = _register(client)
        resp = client.get("/documents", headers={"Authorization": f"Bearer {token}"})
    assert resp.json() == {"doc_ids": ["a.pdf"]}
    assert captured["url"].endswith("/internal/documents")


def test_mcp_server_unreachable_returns_502(monkeypatch):
    class BoomClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            raise ConnectionError("down")

    monkeypatch.setattr(doc_mod.httpx, "AsyncClient", BoomClient)
    with TestClient(app) as client:
        token = _register(client)
        resp = client.get("/documents", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 502
