import json
from datetime import datetime
from typing import Optional

import asyncpg


async def create_conversation(pool: asyncpg.Pool, user_id, title: str) -> dict:
    row = await pool.fetchrow(
        "INSERT INTO conversations (user_id, title) VALUES ($1, $2) "
        "RETURNING id, title, updated_at",
        user_id,
        title,
    )
    return dict(row)


async def get_conversation(pool: asyncpg.Pool, conversation_id, user_id) -> Optional[dict]:
    row = await pool.fetchrow(
        "SELECT id, title, updated_at FROM conversations WHERE id = $1 AND user_id = $2",
        conversation_id,
        user_id,
    )
    return dict(row) if row else None


async def list_conversations(pool: asyncpg.Pool, user_id) -> list[dict]:
    rows = await pool.fetch(
        "SELECT id, title, updated_at FROM conversations "
        "WHERE user_id = $1 ORDER BY updated_at DESC",
        user_id,
    )
    return [dict(r) for r in rows]


async def insert_message(
    pool: asyncpg.Pool, conversation_id, role: str, content: str, tool_calls: Optional[list] = None
) -> None:
    await pool.execute(
        "INSERT INTO messages (conversation_id, role, content, tool_calls) "
        "VALUES ($1, $2, $3, $4::jsonb)",
        conversation_id,
        role,
        content,
        json.dumps(tool_calls, ensure_ascii=False) if tool_calls is not None else None,
    )


async def list_messages(pool: asyncpg.Pool, conversation_id) -> list[dict]:
    rows = await pool.fetch(
        "SELECT role, content, tool_calls, created_at FROM messages "
        "WHERE conversation_id = $1 ORDER BY seq ASC",
        conversation_id,
    )
    result = []
    for r in rows:
        d = dict(r)
        d["tool_calls"] = json.loads(d["tool_calls"]) if d["tool_calls"] else None
        result.append(d)
    return result


async def get_recent_messages(pool: asyncpg.Pool, conversation_id, limit: int = 30) -> list[dict]:
    rows = await pool.fetch(
        "SELECT role, content FROM ("
        "  SELECT role, content, seq FROM messages "
        "  WHERE conversation_id = $1 ORDER BY seq DESC LIMIT $2"
        ") sub ORDER BY seq ASC",
        conversation_id,
        limit,
    )
    return [dict(r) for r in rows]


async def touch_conversation(pool: asyncpg.Pool, conversation_id) -> datetime:
    return await pool.fetchval(
        # clock_timestamp(), not now(): now() is frozen per-transaction, which would
        # leave updated_at unchanged when insert and touch share a transaction.
        "UPDATE conversations SET updated_at = clock_timestamp() WHERE id = $1 RETURNING updated_at",
        conversation_id,
    )


async def delete_conversation(pool: asyncpg.Pool, conversation_id, user_id) -> bool:
    result = await pool.execute(
        "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
        conversation_id,
        user_id,
    )
    return result == "DELETE 1"
