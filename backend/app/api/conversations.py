import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.cache.conversations import (
    cache_conversations,
    drop_conversation,
    get_cached_conversations,
)
from app.db.conversations import (
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
)
from app.auth.dependencies import get_current_user

router = APIRouter(tags=["conversations"])


def _parse_uuid(value: str):
    try:
        return uuid_mod.UUID(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.get("/conversations")
async def get_conversations(request: Request, user: dict = Depends(get_current_user)):
    r = request.app.state.redis_client
    cached = await get_cached_conversations(r, user["id"])
    if cached is not None:
        return cached

    rows = await list_conversations(request.app.state.pg_pool, user["id"])
    payload = [
        {"id": str(row["id"]), "title": row["title"], "updated_at": row["updated_at"].isoformat()}
        for row in rows
    ]
    await cache_conversations(r, user["id"], payload)
    return payload


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, request: Request, user: dict = Depends(get_current_user)):
    conv_uuid = _parse_uuid(conversation_id)
    pool = request.app.state.pg_pool
    conversation = await get_conversation(pool, conv_uuid, user["id"])
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    rows = await list_messages(pool, conv_uuid)
    return [
        {"role": m["role"], "content": m["content"], "tool_calls": m["tool_calls"],
         "created_at": m["created_at"].isoformat()}
        for m in rows
    ]


@router.delete("/conversations/{conversation_id}")
async def remove_conversation(conversation_id: str, request: Request,
                              user: dict = Depends(get_current_user)):
    conv_uuid = _parse_uuid(conversation_id)
    deleted = await delete_conversation(request.app.state.pg_pool, conv_uuid, user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    await drop_conversation(request.app.state.redis_client, user["id"], conv_uuid)
    return {"deleted": True}
