from typing import Literal

import anyio
from mcp.server.fastmcp import FastMCP

from app.tools.calendar import (
    build_calendar_service,
    create_event,
    delete_event,
    read_events,
    update_event,
)
from app.config import settings
from app.models import reranker_model, reranker_tokenizer, vectordb
from app.tools.rag import search
from app.tools.context import MISSING_TOKEN_MESSAGE, extract_access_token
from app.tools.web_search import web_search as _web_search

mcp = FastMCP("nutrition-va-mcp")


def _access_token() -> str | None:
    """Read the caller's Google token from the request headers.

    Called on the event loop (it is a dict lookup) so that the contextvar holding the
    MCP request context is still the right one — only the blocking Google work below
    is pushed to a worker thread.
    """
    return extract_access_token(mcp.get_context().request_context.request)


@mcp.tool()
async def rag_search(query: str, doc_ids: list[str] | None = None, top_k: int = 3) -> str:
    """Search ingested nutrition documents for context relevant to the query."""
    return await anyio.to_thread.run_sync(
        lambda: search(query, vectordb, reranker_model, reranker_tokenizer,
                       doc_ids=doc_ids, top_k=top_k)
    )


@mcp.tool()
async def calendar_create(
    summary: str,
    start: str,
    end: str | None = None,
    location: str | None = None,
    description: str | None = None,
    attendees: list[str] | None = None,
    recurrence: list[str] | None = None,
    color_id: str | None = None,
    reminder_minutes: int | None = None,
    check_conflict: bool = True,
) -> str:
    """Create a Google Calendar event.

    `start`/`end` are ISO 8601; a value without a timezone offset is treated as
    Vietnam time (+07:00), and `end` defaults to one hour after `start`.
    `recurrence` takes standard RRULE strings, e.g. ["RRULE:FREQ=DAILY;COUNT=5"],
    which creates the whole repeating series in one call. An UNTIL value must be
    UTC, e.g. RRULE:FREQ=WEEKLY;UNTIL=20261231T170000Z (Google rejects local time).
    When `check_conflict` is true the event is NOT created if the slot is already
    busy; the clashing events are returned instead.
    """
    token = _access_token()
    if not token:
        return MISSING_TOKEN_MESSAGE

    def run():
        service = build_calendar_service(token)
        return create_event(
            service, summary, start, end=end, location=location, description=description,
            attendees=attendees, recurrence=recurrence, color_id=color_id,
            reminder_minutes=reminder_minutes, check_conflict=check_conflict,
        )

    return await anyio.to_thread.run_sync(run)


@mcp.tool()
async def calendar_read(
    time_min: str | None = None,
    time_max: str | None = None,
    q: str | None = None,
) -> str:
    """List Google Calendar events, defaulting to the next two weeks.

    `q` is a free-text search over event content — use it to find the id of an event
    the user described in words. Each returned line carries [id: ...], and events in a
    repeating series also carry [series: ...] for deleting the whole series.
    """
    token = _access_token()
    if not token:
        return MISSING_TOKEN_MESSAGE

    def run():
        service = build_calendar_service(token)
        return read_events(service, time_min=time_min, time_max=time_max, q=q)

    return await anyio.to_thread.run_sync(run)


@mcp.tool()
async def calendar_update(
    event_id: str,
    summary: str | None = None,
    start: str | None = None,
    end: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> str:
    """Update one Google Calendar event, changing only the fields given.

    Get `event_id` from calendar_read. Giving `start` without `end` moves the event
    while keeping its original duration.
    """
    token = _access_token()
    if not token:
        return MISSING_TOKEN_MESSAGE

    def run():
        service = build_calendar_service(token)
        return update_event(service, event_id, summary=summary, start=start, end=end,
                            location=location, description=description)

    return await anyio.to_thread.run_sync(run)


@mcp.tool()
async def calendar_delete(
    event_id: str,
    scope: Literal["instance", "series"] = "instance",
) -> str:
    """Delete a Google Calendar event.

    Get `event_id` from calendar_read. Use scope="instance" (the default) to remove a
    single occurrence, or scope="series" to remove an entire repeating series.
    """
    token = _access_token()
    if not token:
        return MISSING_TOKEN_MESSAGE

    def run():
        service = build_calendar_service(token)
        return delete_event(service, event_id, scope=scope)

    return await anyio.to_thread.run_sync(run)


@mcp.tool()
async def web_search(query: str, max_results: int = 3) -> str:
    """Search the web and return readable text from the top result pages."""
    return await anyio.to_thread.run_sync(
        lambda: _web_search(query, settings.serpapi_api_key, max_results=max_results)
    )
