import json

ToolInfo = dict  # {"name": str, "description": str, "schema": dict}


def render_catalog(tools: list[ToolInfo]) -> str:
    blocks = []
    for t in tools:
        props = t["schema"].get("properties", {})
        args = {name: spec.get("type", "any") for name, spec in props.items()}
        blocks.append(
            f"### {t['name']}\n{t['description']}\nArguments (JSON): {json.dumps(args)}\n"
            f"Required: {t['schema'].get('required', [])}"
        )
    return "\n\n".join(blocks)


SYSTEM_TEMPLATE = """You are a nutrition assistant with access to tools.

## Tools
{catalog}

## Rules
- Reply with EXACTLY ONE JSON object and nothing else. Either:
  {{"tool": "<tool name>", "args": {{...}}}}  to call a tool, or
  {{"answer": "<your final answer>"}}          to answer the user.
- Datetimes without an offset are Vietnam time (+07:00).
- Use rag_search for nutrition/health questions, web_search for current/general
  information, calendar_* for schedules. Answer directly for small talk.
- Write the final answer in the same language as the user's question.
{force}"""

FORCE_LINE = (
    '- You have reached the tool limit: you must not call any more tools. '
    'Reply with {"answer": ...} now.'
)


def system_prompt(tools: list[ToolInfo], force_answer: bool) -> str:
    return SYSTEM_TEMPLATE.format(
        catalog=render_catalog(tools), force=FORCE_LINE if force_answer else ""
    )


REWRITE_SYSTEM = (
    "Rewrite the latest user question as a standalone question that needs no chat "
    "history to understand. Keep the original language. If it is already standalone, "
    "return it unchanged. Return ONLY the rewritten question."
)


def rewrite_messages(history: list[dict], query: str) -> list[dict]:
    lines = [f"{m['role']}: {m['content']}" for m in history]
    body = "CHAT HISTORY:\n" + "\n".join(lines) + f"\n\nLATEST QUESTION: {query}"
    return [{"role": "system", "content": REWRITE_SYSTEM}, {"role": "user", "content": body}]


def planner_user_message(standalone_query: str, tool_results: list[dict]) -> str:
    if not tool_results:
        return standalone_query
    parts = ["Results from tools you already called:"]
    for r in tool_results:
        parts.append(f"[{r['tool']} args={json.dumps(r['args'], ensure_ascii=False)}]\n{r['result']}")
    parts.append(f"The user's question: {standalone_query}")
    return "\n\n".join(parts)
