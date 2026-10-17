import json
import uuid

import redis as redis_sync
from fastapi.testclient import TestClient

import app.api.chat as chat_mod
from app.config import settings
from app.main import app


def _register(client):
    resp = client.post(
        "/auth/register",
        json={"email": f"{uuid.uuid4()}@example.com", "password": "correct horse battery staple"},
    )
    return resp.json()["access_token"]


def _fake_agent():
    async def fake(history, query, *, google_access_token=None, doc_ids=None):
        yield {"type": "rewrite", "standalone_query": query}
        yield {"type": "answer", "content": "ok"}
    return fake


def _chat(client, token, message, conversation_id=None):
    body = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    resp = client.post("/chat", json=body, headers={"Authorization": f"Bearer {token}"})
    for line in resp.text.splitlines():
        if line.startswith("data: ") and "conversation_id" in line:
            return json.loads(line[6:])["conversation_id"]
    return conversation_id


def test_list_conversations_own_only_and_cache_backfill(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent())
    with TestClient(app) as client:
        token_a = _register(client)
        token_b = _register(client)
        cid_a = _chat(client, token_a, "hội thoại của A")
        _chat(client, token_b, "hội thoại của B")

        resp = client.get("/conversations", headers={"Authorization": f"Bearer {token_a}"})
        assert resp.status_code == 200
        titles = [c["title"] for c in resp.json()]
        assert titles == ["hội thoại của A"]
        assert resp.json()[0]["id"] == cid_a

        # second call must come from cache: poison the cache and expect the poison back
        r = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)
        me = client.get("/me", headers={"Authorization": f"Bearer {token_a}"}).json()
        r.set(f"user:{me['id']}:conversations", json.dumps([{"id": "cached", "title": "từ cache",
                                                             "updated_at": "2026-01-01T00:00:00"}]))
        resp2 = client.get("/conversations", headers={"Authorization": f"Bearer {token_a}"})
        assert resp2.json()[0]["title"] == "từ cache"
        r.delete(f"user:{me['id']}:conversations")


def test_get_messages_roundtrip(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent())
    with TestClient(app) as client:
        token = _register(client)
        cid = _chat(client, token, "câu hỏi một")

        resp = client.get(f"/conversations/{cid}/messages",
                          headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    msgs = resp.json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "câu hỏi một"


def test_get_messages_foreign_conversation_404(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent())
    with TestClient(app) as client:
        token_a = _register(client)
        token_b = _register(client)
        cid = _chat(client, token_a, "của A")
        resp = client.get(f"/conversations/{cid}/messages",
                          headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404


def test_delete_conversation_and_cleanup(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent())
    with TestClient(app) as client:
        token = _register(client)
        cid = _chat(client, token, "sẽ bị xóa")
        _chat(client, token, "tiếp", conversation_id=cid)  # ensures message cache exists

        resp = client.delete(f"/conversations/{cid}",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200 and resp.json() == {"deleted": True}

        gone = client.get(f"/conversations/{cid}/messages",
                          headers={"Authorization": f"Bearer {token}"})
        assert gone.status_code == 404

    r = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)
    assert r.exists(f"conv:{cid}:messages") == 0


def test_delete_foreign_conversation_404(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent())
    with TestClient(app) as client:
        token_a = _register(client)
        token_b = _register(client)
        cid = _chat(client, token_a, "của A")
        resp = client.delete(f"/conversations/{cid}",
                             headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404
