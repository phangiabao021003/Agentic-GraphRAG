import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import settings

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_HEADER = "X-Google-Access-Token"

_catalog: list[dict] | None = None


def extract_text_result(result) -> str:
    parts = [c.text for c in result.content if getattr(c, "text", None)]
    return "\n".join(parts) if parts else ""


def _mcp_url() -> str:
    return settings.mcp_server_url.rstrip("/") + "/mcp"


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
    headers = {GOOGLE_TOKEN_HEADER: google_access_token} if google_access_token else None
    try:
        async with streamablehttp_client(_mcp_url(), headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, args)
        return extract_text_result(result)
    except Exception:
        logger.exception("MCP tool call failed: %s(%s)", name, args)
        return f"❌ Không thể gọi công cụ {name}: lỗi kết nối tới mcp-server."
