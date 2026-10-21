import asyncio
import json
import uuid

import asyncpg
import redis as redis_sync
from fastapi.testclient import TestClient

import app.api.chat as chat_mod
from app.config import settings
from app.main import app


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


def _register(client):
    resp = client.post(
        "/auth/register", json={"email": _unique_email(), "password": "correct horse battery staple"}
    )
    return resp.json()["access_token"]


def _fake_agent(events, calls=None):
    async def fake(history, query, *, google_access_token=None, doc_ids=None):
        if calls is not None:
            calls.append({"history": history, "query": query,
                          "google_access_token": google_access_token, "doc_ids": doc_ids})
        for e in events:
            yield e
    return fake


DEFAULT_EVENTS = [
    {"type": "rewrite", "standalone_query": "q?"},
    {"type": "tool_call", "tool": "rag_search", "args": {"query": "q?"}},
    {"type": "tool_result", "tool": "rag_search", "result": "context"},
    {"type": "answer", "content": "câu trả lời"},
]


def _parse_sse(text):
    events = []
    current = {}
    for line in text.splitlines():
        if line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            current["data"] = json.loads(line[6:])
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return [e for e in events if "event" in e]


def _pg(query, *args):
    async def _run():
        conn = await asyncpg.connect(settings.database_url)
        try:
            return [dict(r) for r in await conn.fetch(query, *args)]
        finally:
            await conn.close()
    return asyncio.run(_run())


def test_new_conversation_streams_events_and_persists(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent(DEFAULT_EVENTS))
    with TestClient(app) as client:
        token = _register(client)
        resp = client.post("/chat", json={"message": "Vitamin C là gì?"},
                           headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    names = [e["event"] for e in events]
    assert names == ["conversation", "rewrite", "tool_call", "tool_result", "answer"]
    assert events[-1]["data"]["content"] == "câu trả lời"

    conv_id = events[0]["data"]["conversation_id"]
    rows = _pg("SELECT role, content, tool_calls FROM messages "
               "WHERE conversation_id = $1 ORDER BY seq", uuid.UUID(conv_id))
    assert [r["role"] for r in rows] == ["user", "assistant"]
    assert rows[0]["content"] == "Vitamin C là gì?"
    assert rows[1]["content"] == "câu trả lời"
    trace = json.loads(rows[1]["tool_calls"])
    assert trace[0]["tool"] == "rag_search" and trace[0]["result"] == "context"

    convs = _pg("SELECT title FROM conversations WHERE id = $1", uuid.UUID(conv_id))
    assert convs[0]["title"] == "Vitamin C là gì?"


def test_existing_conversation_has_no_conversation_event_and_caches(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent(DEFAULT_EVENTS))
    calls = []
    with TestClient(app) as client:
        token = _register(client)
        first = client.post("/chat", json={"message": "câu một"},
                            headers={"Authorization": f"Bearer {token}"})
        conv_id = _parse_sse(first.text)[0]["data"]["conversation_id"]

        monkeypatch.setattr(chat_mod, "run_agent", _fake_agent(DEFAULT_EVENTS, calls))
        second = client.post("/chat", json={"message": "câu hai", "conversation_id": conv_id},
                             headers={"Authorization": f"Bearer {token}"})

    names = [e["event"] for e in _parse_sse(second.text)]
    assert "conversation" not in names
    # second turn saw the first turn in history
    assert calls[0]["history"] == [{"role": "user", "content": "câu một"},
                                   {"role": "assistant", "content": "câu trả lời"}]
    # after the second turn the cache holds all 4 messages
    r = redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)
    cached = [json.loads(x) for x in r.lrange(f"conv:{conv_id}:messages", 0, -1)]
    assert len(cached) == 4 and cached[-1]["content"] == "câu trả lời"


def test_foreign_conversation_returns_404(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent(DEFAULT_EVENTS))
    with TestClient(app) as client:
        token_a = _register(client)
        first = client.post("/chat", json={"message": "của A"},
                            headers={"Authorization": f"Bearer {token_a}"})
        conv_id = _parse_sse(first.text)[0]["data"]["conversation_id"]

        token_b = _register(client)
        resp = client.post("/chat", json={"message": "xâm nhập", "conversation_id": conv_id},
                           headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404


def test_empty_message_rejected():
    with TestClient(app) as client:
        token = _register(client)
        resp = client.post("/chat", json={"message": ""},
                           headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


def test_doc_ids_forwarded_to_agent(monkeypatch):
    calls = []
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent(DEFAULT_EVENTS, calls))
    with TestClient(app) as client:
        token = _register(client)
        client.post("/chat", json={"message": "hỏi", "doc_ids": ["doc1.pdf"]},
                    headers={"Authorization": f"Bearer {token}"})
    assert calls[0]["doc_ids"] == ["doc1.pdf"]


ERROR_EVENTS = [
    {"type": "rewrite", "standalone_query": "q?"},
    {"type": "tool_call", "tool": "web_search", "args": {"query": "q?"}},
    {"type": "error", "code": "tool_failed", "message": "Công cụ web_search gặp lỗi, kết quả có thể thiếu.",
     "tool": "web_search", "severity": "error"},
    {"type": "tool_result", "tool": "web_search", "result": "❌ Công cụ web_search không khả dụng."},
    {"type": "answer", "content": "trả lời không có web"},
]


def test_error_events_are_forwarded_and_not_persisted_in_trace(monkeypatch):
    monkeypatch.setattr(chat_mod, "run_agent", _fake_agent(ERROR_EVENTS))
    with TestClient(app) as client:
        token = _register(client)
        resp = client.post("/chat", json={"message": "hỏi"},
                           headers={"Authorization": f"Bearer {token}"})

    events = _parse_sse(resp.text)
    names = [e["event"] for e in events]
    assert names == ["conversation", "rewrite", "tool_call", "error", "tool_result", "answer"]
    err = next(e for e in events if e["event"] == "error")
    assert err["data"] == {"code": "tool_failed", "tool": "web_search", "severity": "error",
                           "message": "Công cụ web_search gặp lỗi, kết quả có thể thiếu."}

    conv_id = events[0]["data"]["conversation_id"]
    rows = _pg("SELECT tool_calls FROM messages WHERE conversation_id = $1 AND role = 'assistant'",
               uuid.UUID(conv_id))
    trace = json.loads(rows[0]["tool_calls"])
    assert [t["tool"] for t in trace] == ["web_search"]
    assert all("code" not in t for t in trace)


def test_stream_crash_emits_agent_crashed_error_then_answer(monkeypatch):
    async def exploding(history, query, *, google_access_token=None, doc_ids=None):
        yield {"type": "rewrite", "standalone_query": "q?"}
        raise RuntimeError("kaboom")
    monkeypatch.setattr(chat_mod, "run_agent", exploding)
    with TestClient(app) as client:
        token = _register(client)
        resp = client.post("/chat", json={"message": "hỏi"},
                           headers={"Authorization": f"Bearer {token}"})

    events = _parse_sse(resp.text)
    names = [e["event"] for e in events]
    assert names == ["conversation", "rewrite", "error", "answer"]
    assert events[2]["data"]["code"] == "agent_crashed"
    assert events[2]["data"]["message"] == "Hệ thống gặp lỗi khi xử lý câu hỏi."
    assert "❌" in events[3]["data"]["content"]
