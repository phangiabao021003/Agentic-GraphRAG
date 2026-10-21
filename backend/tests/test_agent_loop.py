import pytest

import app.agent.loop as loop_mod
from app.agent import run_agent
from app.agent.errors import MCPToolError

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


async def test_llm_failure_emits_error_event_before_apology(wire, monkeypatch):
    wire([])

    class Boom:
        async def complete(self, messages):
            raise loop_mod.LLMProviderError("down")
    monkeypatch.setattr(loop_mod, "get_provider", lambda: Boom())

    events = await collect(run_agent([], "q"))
    assert [e["type"] for e in events] == ["rewrite", "error", "answer"]
    assert events[1]["code"] == "llm_unavailable"
    assert events[1]["severity"] == "error"
    assert events[1]["message"] == "Mô hình ngôn ngữ không phản hồi. Vui lòng thử lại."
    assert events[-1]["content"] == loop_mod.APOLOGY


async def test_llm_failure_on_retry_emits_error_event(wire, monkeypatch):
    provider, _ = wire(["garbage"])

    async def complete(messages):
        if provider.responses:
            return provider.responses.pop(0)
        raise loop_mod.LLMProviderError("down on retry")
    monkeypatch.setattr(provider, "complete", complete)

    events = await collect(run_agent([], "q"))
    assert [e["type"] for e in events] == ["rewrite", "error", "answer"]
    assert events[1]["code"] == "llm_unavailable"


async def test_twice_unparseable_emits_warning_and_raw_text(wire):
    wire(["garbage one", "garbage two"])
    events = await collect(run_agent([], "q"))
    assert [e["type"] for e in events] == ["rewrite", "error", "answer"]
    assert events[1]["code"] == "llm_bad_output"
    assert events[1]["severity"] == "warning"
    assert events[-1]["content"] == "garbage two"


async def test_tool_failure_emits_error_then_result_and_continues(wire, monkeypatch):
    provider, _ = wire(['{"tool": "rag_search", "args": {"query": "x"}}', '{"answer": "ok"}'])

    async def failing_call(name, args, google_access_token=None):
        raise MCPToolError("tool_failed", name)
    monkeypatch.setattr(loop_mod, "call_mcp_tool", failing_call)

    events = await collect(run_agent([], "q"))
    assert [e["type"] for e in events] == ["rewrite", "tool_call", "error", "tool_result", "answer"]
    assert events[2]["code"] == "tool_failed"
    assert events[2]["tool"] == "rag_search"
    assert events[2]["message"] == "Công cụ rag_search gặp lỗi, kết quả có thể thiếu."
    assert "không khả dụng" in events[3]["result"]
    # the planner still sees the failure note in its next prompt
    assert "không khả dụng" in provider.calls[1][-1]["content"]


async def test_tool_connection_failure_is_mcp_unreachable(wire, monkeypatch):
    wire(['{"tool": "rag_search", "args": {"query": "x"}}', '{"answer": "ok"}'])

    async def failing_call(name, args, google_access_token=None):
        raise MCPToolError("mcp_unreachable", name)
    monkeypatch.setattr(loop_mod, "call_mcp_tool", failing_call)

    events = await collect(run_agent([], "q"))
    errors = [e for e in events if e["type"] == "error"]
    assert len(errors) == 1 and errors[0]["code"] == "mcp_unreachable"


async def test_empty_catalog_emits_mcp_unreachable_first(wire, monkeypatch):
    wire(['{"answer": "no tools"}'])

    async def empty_catalog():
        return []
    monkeypatch.setattr(loop_mod, "fetch_tool_catalog", empty_catalog)

    events = await collect(run_agent([], "q"))
    assert events[0] == {
        "type": "error", "code": "mcp_unreachable", "tool": None, "severity": "error",
        "message": "Không kết nối được tới máy chủ công cụ. Trợ lý sẽ trả lời không dùng công cụ.",
    }
    assert [e["type"] for e in events].count("answer") == 1
    assert events[-1]["type"] == "answer"


async def test_loop_crash_emits_agent_crashed_then_apology(wire, monkeypatch):
    wire([])

    class Broken:
        async def complete(self, messages):
            raise RuntimeError("unexpected")  # not an LLMProviderError → escapes the node
    monkeypatch.setattr(loop_mod, "get_provider", lambda: Broken())

    events = await collect(run_agent([], "q"))
    assert [e["type"] for e in events][-2:] == ["error", "answer"]
    assert events[-2]["code"] == "agent_crashed"
    assert events[-1]["content"] == loop_mod.APOLOGY


async def test_provider_error_before_loop_emits_agent_crashed_then_apology(wire, monkeypatch):
    wire([])

    def bad_provider():
        raise loop_mod.LLMProviderError("bad provider")
    monkeypatch.setattr(loop_mod, "get_provider", bad_provider)

    events = await collect(run_agent([], "q"))
    assert [e["type"] for e in events][-2:] == ["error", "answer"]
    assert events[-2]["code"] == "agent_crashed"
    assert events[-1]["content"] == loop_mod.APOLOGY
