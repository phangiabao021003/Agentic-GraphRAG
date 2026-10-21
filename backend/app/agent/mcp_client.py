import logging

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.agent.errors import MCPToolError
from app.config import settings

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_HEADER = "X-Google-Access-Token"

_catalog: list[dict] | None = None

_CONNECTION_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, OSError)


def extract_text_result(result) -> str:
    parts = [c.text for c in result.content if getattr(c, "text", None)]
    return "\n".join(parts) if parts else ""


def _mcp_url() -> str:
    return settings.mcp_server_url.rstrip("/") + "/mcp"


def _classify(exc: BaseException) -> str:
    """Map a failure to an error code. The MCP client runs inside an anyio task group,
    so connection errors usually arrive wrapped in an ExceptionGroup."""
    if isinstance(exc, BaseExceptionGroup):
        if any(_classify(sub) == "mcp_unreachable" for sub in exc.exceptions):
            return "mcp_unreachable"
        return "tool_failed"
    if isinstance(exc, _CONNECTION_ERRORS):
        return "mcp_unreachable"
    return "tool_failed"


async def fetch_tool_catalog() -> list[dict]:
    """Cached tool list; empty list (not an exception) when mcp-server is unreachable
    so backend keeps booting and the next agent run retries."""
    global _catalog
    if _catalog:
        return _catalog
    try:
        async with streamablehttp_client(_mcp_url()) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
        _catalog = [
            {"name": t.name, "description": t.description or "", "schema": t.inputSchema}
            for t in tools.tools
        ]
        logger.info("Loaded %d MCP tools", len(_catalog))
        return _catalog
    except Exception:
        logger.exception("Could not fetch MCP tool catalog from %s", _mcp_url())
        return []


async def call_mcp_tool(name: str, args: dict, google_access_token: str | None = None) -> str:
    """Call one MCP tool. Raises MCPToolError (code mcp_unreachable | tool_failed)."""
    headers = {GOOGLE_TOKEN_HEADER: google_access_token} if google_access_token else None
    try:
        async with streamablehttp_client(_mcp_url(), headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, args)
        return extract_text_result(result)
    except Exception as exc:
        logger.exception("MCP tool call failed: %s(%s)", name, args)
        raise MCPToolError(_classify(exc), name) from exc
