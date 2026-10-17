import uuid

import asyncpg
import pytest

from app.config import settings
from app.db.conversations import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_recent_messages,
    insert_message,
    list_conversations,
    list_messages,
    touch_conversation,
)
from app.db.users import create_user, get_google_credentials


@pytest.fixture
async def conn():
    connection = await asyncpg.connect(settings.database_url)
    transaction = connection.transaction()
    await transaction.start()
    try:
        yield connection
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.fixture
async def user(conn):
    return await create_user(conn, f"{uuid.uuid4()}@example.com", "hash")


async def test_create_and_get_conversation_enforces_ownership(conn, user):
    conv = await create_conversation(conn, user["id"], "Hỏi về vitamin C")
    fetched = await get_conversation(conn, conv["id"], user["id"])
    assert fetched["title"] == "Hỏi về vitamin C"

    stranger = await create_user(conn, f"{uuid.uuid4()}@example.com", "hash")
    assert await get_conversation(conn, conv["id"], stranger["id"]) is None


async def test_list_conversations_orders_by_updated_at_desc(conn, user):
    c1 = await create_conversation(conn, user["id"], "one")
    c2 = await create_conversation(conn, user["id"], "two")
    await touch_conversation(conn, c1["id"])  # c1 becomes most recent

    result = await list_conversations(conn, user["id"])
    assert [c["title"] for c in result] == ["one", "two"]


async def test_insert_and_list_messages_roundtrip_with_tool_calls(conn, user):
    conv = await create_conversation(conn, user["id"], "t")
    await insert_message(conn, conv["id"], "user", "hi")
    await insert_message(conn, conv["id"], "assistant", "hello",
                         tool_calls=[{"tool": "rag_search", "args": {"query": "x"}, "result": "ctx"}])

    msgs = await list_messages(conn, conv["id"])
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["tool_calls"] is None
    assert msgs[1]["tool_calls"][0]["tool"] == "rag_search"


async def test_get_recent_messages_limits_and_stays_chronological(conn, user):
    conv = await create_conversation(conn, user["id"], "t")
    for i in range(5):
        await insert_message(conn, conv["id"], "user", f"m{i}")

    recent = await get_recent_messages(conn, conv["id"], limit=3)
    assert [m["content"] for m in recent] == ["m2", "m3", "m4"]
    assert set(recent[0].keys()) == {"role", "content"}


async def test_touch_conversation_bumps_updated_at(conn, user):
    conv = await create_conversation(conn, user["id"], "t")
    bumped = await touch_conversation(conn, conv["id"])
    assert bumped >= conv["updated_at"]


async def test_delete_conversation_cascades_and_checks_owner(conn, user):
    conv = await create_conversation(conn, user["id"], "t")
    await insert_message(conn, conv["id"], "user", "hi")

    stranger = await create_user(conn, f"{uuid.uuid4()}@example.com", "hash")
    assert await delete_conversation(conn, conv["id"], stranger["id"]) is False

    assert await delete_conversation(conn, conv["id"], user["id"]) is True
    assert await get_conversation(conn, conv["id"], user["id"]) is None
    assert await list_messages(conn, conv["id"]) == []


async def test_get_google_credentials_none_then_roundtrip(conn, user):
    assert await get_google_credentials(conn, user["id"]) is None

    from datetime import datetime, timedelta, timezone
    from app.db.users import upsert_google_credentials
    await upsert_google_credentials(conn, user["id"], "enc-refresh", "enc-access",
                                    datetime.now(timezone.utc) + timedelta(hours=1))
    creds = await get_google_credentials(conn, user["id"])
    assert creds["refresh_token_encrypted"] == "enc-refresh"
