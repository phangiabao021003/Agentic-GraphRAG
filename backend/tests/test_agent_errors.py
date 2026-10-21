import pytest

from app.agent.errors import ERROR_MESSAGES, MCPToolError, error_event


def test_error_event_shape_for_error_severity():
    ev = error_event("llm_unavailable")
    assert ev == {
        "type": "error",
        "code": "llm_unavailable",
        "message": "Mô hình ngôn ngữ không phản hồi. Vui lòng thử lại.",
        "tool": None,
        "severity": "error",
    }


def test_llm_bad_output_is_a_warning():
    assert error_event("llm_bad_output")["severity"] == "warning"


def test_tool_failed_message_names_the_tool():
    ev = error_event("tool_failed", tool="web_search")
    assert ev["tool"] == "web_search"
    assert ev["message"] == "Công cụ web_search gặp lỗi, kết quả có thể thiếu."


def test_unknown_code_is_rejected():
    with pytest.raises(KeyError):
        error_event("nope")


def test_all_spec_codes_exist():
    assert set(ERROR_MESSAGES) == {
        "mcp_unreachable", "tool_failed", "llm_unavailable", "llm_bad_output", "agent_crashed",
    }


def test_mcp_tool_error_carries_code_and_tool():
    exc = MCPToolError("mcp_unreachable", "rag_search")
    assert exc.code == "mcp_unreachable"
    assert exc.tool == "rag_search"
    assert "rag_search" in str(exc)
