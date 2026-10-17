import pytest

import app.agent.loop as loop_mod
from app.agent import run_agent

CATALOG = [
    {"name": "rag_search", "description": "d", "schema": {"properties": {"query": {"type": "string"}}}},
    {"name": "calendar_read", "description": "d", "schema": {"properties": {}}},
]


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


@pytest.fixture
def wire(monkeypatch):
    def _wire(responses, tool_result="TOOL-OUT"):
        provider = FakeProvider(responses)
        calls = []

        async def fake_catalog():
            return CATALOG

        async def fake_call(name, args, google_access_token=None):
            calls.append({"name": name, "args": args, "token": google_access_token})
            return tool_result

        monkeypatch.setattr(loop_mod, "get_provider", lambda: provider)
        monkeypatch.setattr(loop_mod, "fetch_tool_catalog", fake_catalog)
        monkeypatch.setattr(loop_mod, "call_mcp_tool", fake_call)
        return provider, calls
    return _wire


async def collect(agen):
    return [e async for e in agen]


async def test_direct_answer_no_history_skips_rewrite(wire):
    provider, calls = wire(['{"answer": "hi"}'])
    events = await collect(run_agent([], "hello"))
    assert events == [{"type": "rewrite", "standalone_query": "hello"},
                      {"type": "answer", "content": "hi"}]
    assert len(provider.calls) == 1  # no rewrite LLM call, one planner call
    assert calls == []


async def test_rewrite_called_when_history_present(wire):
    provider, _ = wire(["standalone?", '{"answer": "ok"}'])
    events = await collect(run_agent([{"role": "user", "content": "a"}], "it?"))
    assert events[0] == {"type": "rewrite", "standalone_query": "standalone?"}
    assert len(provider.calls) == 2


async def test_single_tool_then_answer(wire):
    provider, calls = wire(['{"tool": "rag_search", "args": {"query": "vit c"}}',
                            '{"answer": "done"}'])
    events = await collect(run_agent([], "q"))
    types = [e["type"] for e in events]
    assert types == ["rewrite", "tool_call", "tool_result", "answer"]
    assert calls[0]["name"] == "rag_search"
    assert "TOOL-OUT" in provider.calls[1][-1]["content"]  # result fed back to planner


async def test_doc_ids_injected_into_rag_search_only(wire):
    _, calls = wire(['{"tool": "rag_search", "args": {"query": "x"}}',
                     '{"tool": "calendar_read", "args": {}}',
                     '{"answer": "ok"}'])
    await collect(run_agent([], "q", doc_ids=["doc1"]))
    assert calls[0]["args"]["doc_ids"] == ["doc1"]
    assert "doc_ids" not in calls[1]["args"]


async def test_google_token_passed_to_tool_calls(wire):
    _, calls = wire(['{"tool": "calendar_read", "args": {}}', '{"answer": "ok"}'])
    await collect(run_agent([], "q", google_access_token="tok"))
    assert calls[0]["token"] == "tok"


async def test_parse_retry_then_success(wire):
    provider, _ = wire(["not json at all", '{"answer": "recovered"}'])
    events = await collect(run_agent([], "q"))
    assert events[-1] == {"type": "answer", "content": "recovered"}
    assert "exactly one JSON object" in str(provider.calls[1][-1]["content"])


async def test_twice_unparseable_degrades_to_raw_text(wire):
    wire(["garbage one", "garbage two"])
    events = await collect(run_agent([], "q"))
    assert events[-1] == {"type": "answer", "content": "garbage two"}


async def test_iteration_cap_forces_answer(wire):
    responses = ['{"tool": "calendar_read", "args": {}}'] * 4 + ['{"answer": "forced"}']
    provider, calls = wire(responses)
    events = await collect(run_agent([], "q"))
    assert events[-1] == {"type": "answer", "content": "forced"}
    assert len(calls) == 4
    assert "must not call any more tools" in provider.calls[4][0]["content"]


async def test_provider_error_yields_apology(wire, monkeypatch):
    wire([])  # wires the fake catalog/tool call so no real network is touched

    class Boom:
        async def complete(self, messages):
            raise loop_mod.LLMProviderError("down")
    monkeypatch.setattr(loop_mod, "get_provider", lambda: Boom())
    events = await collect(run_agent([], "q"))
    assert events[-1]["type"] == "answer"
    assert "❌" in events[-1]["content"]


async def test_answer_event_is_always_last_and_unique(wire):
    wire(['{"tool": "rag_search", "args": {"query": "x"}}', '{"answer": "a"}'])
    events = await collect(run_agent([], "q"))
    assert [e["type"] for e in events].count("answer") == 1
    assert events[-1]["type"] == "answer"
