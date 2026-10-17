import asyncio
import json
import logging
import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from app.agent import run_agent
from app.models.chat import ChatRequest
from app.cache.conversations import (
    append_messages,
    cache_messages,
    get_cached_messages,
    invalidate_conversations,
)
from app.db.conversations import (
    create_conversation,
    get_conversation,
    get_recent_messages,
    insert_message,
    touch_conversation,
)
from app.auth.dependencies import get_current_user
from app.auth.google_token import get_google_access_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

TITLE_MAX_LEN = 50


def _sse(event_type: str, payload: dict) -> dict:
    return {"event": event_type, "data": json.dumps(payload, ensure_ascii=False)}


@router.post("/chat")
async def chat(body: ChatRequest, request: Request, user: dict = Depends(get_current_user)):
    pool = request.app.state.pg_pool
    r = request.app.state.redis_client
    user_id = user["id"]

    new_conversation = False
    if body.conversation_id is not None:
        try:
            conv_uuid = uuid_mod.UUID(body.conversation_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        conversation = await get_conversation(pool, conv_uuid, user_id)
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    else:
        conversation = await create_conversation(pool, user_id, body.message[:TITLE_MAX_LEN])
        new_conversation = True
    conversation_id = conversation["id"]

    history = await get_cached_messages(r, conversation_id)
    if history is None:
        history = await get_recent_messages(pool, conversation_id)
        if history:
            await cache_messages(r, conversation_id, history)

    google_access_token = await get_google_access_token(pool, r, user_id)

    async def event_stream():
        if new_conversation:
            yield _sse("conversation", {"conversation_id": str(conversation_id)})

        answer = None
        trace: list[dict] = []
        try:
            async for event in run_agent(
                history,
                body.message,
                google_access_token=google_access_token,
                doc_ids=body.doc_ids,
            ):
                event_type = event["type"]
                payload = {k: v for k, v in event.items() if k != "type"}
                if event_type == "tool_call":
                    trace.append({"tool": event["tool"], "args": event["args"], "result": None})
                elif event_type == "tool_result" and trace:
                    trace[-1]["result"] = event["result"]
                elif event_type == "answer":
                    answer = event["content"]
                yield _sse(event_type, payload)
        except asyncio.CancelledError:
            # Client disconnected mid-stream: the turn never completed, persist nothing.
            logger.info("chat stream cancelled for conversation %s", conversation_id)
            raise
        except Exception:
            # run_agent is not supposed to raise (#5 guarantees it); belt and braces.
            logger.exception("chat stream crashed for conversation %s", conversation_id)
            answer = answer or "❌ Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau."
            yield _sse("answer", {"content": answer})

        # Persist the turn: Postgres first, then Redis.
        await insert_message(pool, conversation_id, "user", body.message)
        await insert_message(pool, conversation_id, "assistant", answer or "", tool_calls=trace or None)
        await touch_conversation(pool, conversation_id)
        await append_messages(r, conversation_id, [
            {"role": "user", "content": body.message},
            {"role": "assistant", "content": answer or ""},
        ])
        await invalidate_conversations(r, user_id)

    return EventSourceResponse(event_stream())
