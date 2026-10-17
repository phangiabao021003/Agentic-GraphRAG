from app.agent.prompts import (
    planner_user_message,
    render_catalog,
    rewrite_messages,
    system_prompt,
)

TOOLS = [{"name": "rag_search", "description": "Search docs.",
          "schema": {"properties": {"query": {"type": "string"}}, "required": ["query"]}}]


def test_render_catalog_contains_name_description_and_args():
    text = render_catalog(TOOLS)
    assert "### rag_search" in text
    assert "Search docs." in text
    assert '"query"' in text


def test_system_prompt_embeds_catalog_and_protocol():
    text = system_prompt(TOOLS, force_answer=False)
    assert "### rag_search" in text
    assert '{"tool"' in text and '{"answer"' in text
    assert "+07:00" in text  # VN timezone rule lives in the prompt


def test_system_prompt_force_answer_mode():
    text = system_prompt(TOOLS, force_answer=True)
    assert "must not call any more tools" in text


def test_rewrite_messages_includes_history_and_query():
    msgs = rewrite_messages([{"role": "user", "content": "what is vit C?"},
                             {"role": "assistant", "content": "..."}], "tell me more")
    assert msgs[0]["role"] == "system"
    assert "tell me more" in msgs[-1]["content"]
    assert "what is vit C?" in msgs[-1]["content"]


def test_planner_user_message_renders_tool_results():
    text = planner_user_message("q", [{"tool": "rag_search", "args": {"query": "x"}, "result": "CTX"}])
    assert "rag_search" in text and "CTX" in text and text.strip().endswith("q")
