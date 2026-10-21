import httpx
import pytest

import app.agent.mcp_client as mcp_client
from app.agent.errors import MCPToolError


def test_connect_error_is_unreachable():
    assert mcp_client._classify(httpx.ConnectError("refused")) == "mcp_unreachable"


def test_connect_timeout_is_unreachable():
    assert mcp_client._classify(httpx.ConnectTimeout("slow")) == "mcp_unreachable"


def test_os_error_is_unreachable():
    assert mcp_client._classify(ConnectionRefusedError()) == "mcp_unreachable"


def test_connect_error_nested_in_exception_group_is_unreachable():
    group = ExceptionGroup("unhandled errors in a TaskGroup", [httpx.ConnectError("refused")])
    assert mcp_client._classify(group) == "mcp_unreachable"


def test_other_errors_are_tool_failed():
    assert mcp_client._classify(RuntimeError("boom")) == "tool_failed"
    group = ExceptionGroup("g", [ValueError("x")])
    assert mcp_client._classify(group) == "tool_failed"


class _BrokenClient:
    """Stand-in for streamablehttp_client that fails on enter."""

    def __init__(self, exc):
        self.exc = exc

    async def __aenter__(self):
        raise self.exc

    async def __aexit__(self, *a):
        return False


async def test_call_mcp_tool_raises_mcp_tool_error_with_classification(monkeypatch):
    monkeypatch.setattr(
        mcp_client, "streamablehttp_client",
        lambda url, headers=None: _BrokenClient(httpx.ConnectError("refused")),
    )
    with pytest.raises(MCPToolError) as info:
        await mcp_client.call_mcp_tool("web_search", {"query": "x"})
    assert info.value.code == "mcp_unreachable"
    assert info.value.tool == "web_search"


async def test_call_mcp_tool_non_connection_error_is_tool_failed(monkeypatch):
    monkeypatch.setattr(
        mcp_client, "streamablehttp_client",
        lambda url, headers=None: _BrokenClient(RuntimeError("bad schema")),
    )
    with pytest.raises(MCPToolError) as info:
        await mcp_client.call_mcp_tool("rag_search", {})
    assert info.value.code == "tool_failed"
