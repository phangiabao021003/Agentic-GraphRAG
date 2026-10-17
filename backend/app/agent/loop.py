import logging
from typing import AsyncIterator, TypedDict

from langgraph.graph import END, StateGraph

from app.agent.mcp_client import call_mcp_tool, fetch_tool_catalog
from app.agent.parser import ParseError, parse_planner_output
from app.agent.prompts import planner_user_message, rewrite_messages, system_prompt
from app.llm_providers import LLMProviderError, get_provider

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5
MAX_HISTORY = 10
APOLOGY = "❌ Xin lỗi, hệ thống đang gặp sự cố khi xử lý câu hỏi của bạn. Vui lòng thử lại sau."


class AgentState(TypedDict, total=False):
    history: list[dict]
    query: str
    standalone_query: str
    tool_results: list[dict]
    iterations: int
    pending_tool: dict | None
    answer: str | None
    doc_ids: list[str] | None
    google_access_token: str | None


def _build_graph(provider, catalog):
    known = {t["name"] for t in catalog}

    async def rewrite(state: AgentState) -> dict:
        if not state["history"]:
            return {"standalone_query": state["query"]}
        try:
            text = await provider.complete(
                rewrite_messages(state["history"][-MAX_HISTORY:], state["query"])
            )
            return {"standalone_query": text.strip() or state["query"]}
        except LLMProviderError:
            logger.exception("rewrite failed; using the raw query")
            return {"standalone_query": state["query"]}

    async def planner(state: AgentState) -> dict:
        iterations = state.get("iterations", 0) + 1
        force = iterations >= MAX_ITERATIONS
        messages = [{"role": "system", "content": system_prompt(catalog, force_answer=force)}]
        messages += state["history"][-MAX_HISTORY:]
        messages.append({
            "role": "user",
            "content": planner_user_message(state["standalone_query"],
                                            state.get("tool_results", [])),
        })
        try:
            text = await provider.complete(messages)
        except LLMProviderError:
            logger.exception("planner LLM call failed")
            return {"answer": APOLOGY, "pending_tool": None, "iterations": iterations}

        try:
            kind, value = parse_planner_output(text, known)
        except ParseError as exc:
            iterations += 1  # the retry is a planner visit too (spec §5)
            retry = messages + [
                {"role": "assistant", "content": text},
                {"role": "user",
                 "content": f"Invalid: {exc}. Reply with exactly one JSON object."},
            ]
            try:
                text2 = await provider.complete(retry)
                kind, value = parse_planner_output(text2, known)
            except LLMProviderError:
                logger.exception("planner retry LLM call failed")
                return {"answer": APOLOGY, "pending_tool": None, "iterations": iterations}
            except ParseError:
                logger.warning("planner output unparseable twice; degrading to raw text")
                return {"answer": text2, "pending_tool": None, "iterations": iterations}

        if kind == "tool" and not force:
            return {"pending_tool": value, "answer": None, "iterations": iterations}
        if kind == "tool":  # force mode but the model still tried to call a tool
            logger.warning("model called a tool in force-answer mode; degrading")
            return {"answer": APOLOGY, "pending_tool": None, "iterations": iterations}
        return {"answer": value, "pending_tool": None, "iterations": iterations}

    async def executor(state: AgentState) -> dict:
        call = state["pending_tool"]
        args = dict(call["args"])
        if call["tool"] == "rag_search" and state.get("doc_ids"):
            args["doc_ids"] = state["doc_ids"]
        result = await call_mcp_tool(call["tool"], args, state.get("google_access_token"))
        record = {"tool": call["tool"], "args": args, "result": result}
        return {"tool_results": state.get("tool_results", []) + [record], "pending_tool": None}

    graph = StateGraph(AgentState)
    graph.add_node("rewrite", rewrite)
    graph.add_node("planner", planner)
    graph.add_node("executor", executor)
    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "planner")
    graph.add_conditional_edges(
        "planner",
        lambda s: "executor" if s.get("pending_tool") else END,
        {"executor": "executor", END: END},
    )
    graph.add_edge("executor", "planner")
    return graph.compile()


async def run_agent(
    history: list[dict],
    query: str,
    *,
    google_access_token: str | None = None,
    doc_ids: list[str] | None = None,
) -> AsyncIterator[dict]:
    catalog = await fetch_tool_catalog()
    provider = get_provider()
    app = _build_graph(provider, catalog)
    state: AgentState = {
        "history": history[-MAX_HISTORY:],
        "query": query,
        "tool_results": [],
        "iterations": 0,
        "doc_ids": doc_ids,
        "google_access_token": google_access_token,
    }
    answer = APOLOGY
    try:
        async for update in app.astream(state, stream_mode="updates"):
            for node, delta in update.items():
                if node == "rewrite":
                    yield {"type": "rewrite", "standalone_query": delta["standalone_query"]}
                elif node == "planner" and delta.get("pending_tool"):
                    call = delta["pending_tool"]
                    yield {"type": "tool_call", "tool": call["tool"], "args": call["args"]}
                elif node == "planner" and delta.get("answer") is not None:
                    answer = delta["answer"]
                elif node == "executor":
                    record = delta["tool_results"][-1]
                    yield {"type": "tool_result", "tool": record["tool"], "result": record["result"]}
    except Exception:
        logger.exception("agent loop crashed")
    yield {"type": "answer", "content": answer}
