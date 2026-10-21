"""Error codes surfaced to the UI as SSE `error` events.

Single source of truth for the code → Vietnamese message mapping (spec §3). Keep the
messages short: technical detail belongs in server logs, not in the toast.
"""
from typing import Literal

ERROR_MESSAGES: dict[str, str] = {
    "mcp_unreachable": "Không kết nối được tới máy chủ công cụ. Trợ lý sẽ trả lời không dùng công cụ.",
    "tool_failed": "Công cụ {tool} gặp lỗi, kết quả có thể thiếu.",
    "llm_unavailable": "Mô hình ngôn ngữ không phản hồi. Vui lòng thử lại.",
    "llm_bad_output": "Mô hình trả lời sai định dạng, hiển thị nguyên văn.",
    "agent_crashed": "Hệ thống gặp lỗi khi xử lý câu hỏi.",
}

WARNING_CODES: frozenset[str] = frozenset({"llm_bad_output"})

ToolErrorCode = Literal["mcp_unreachable", "tool_failed"]


def error_event(code: str, *, tool: str | None = None) -> dict:
    """Build the loop-level event dict; chat.py strips "type" and sends the rest as data."""
    message = ERROR_MESSAGES[code].format(tool=tool or "")
    return {
        "type": "error",
        "code": code,
        "message": message,
        "tool": tool,
        "severity": "warning" if code in WARNING_CODES else "error",
    }


class MCPToolError(Exception):
    """Raised by call_mcp_tool; the executor turns it into an `error` event."""

    def __init__(self, code: ToolErrorCode, tool: str):
        super().__init__(f"{code}: {tool}")
        self.code = code
        self.tool = tool
