import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from app.config import settings
from app.db.users import (
    create_user,
    get_refresh_token,
    get_user_by_email,
    get_user_by_id,
    insert_refresh_token,
    revoke_refresh_token,
    upsert_google_credentials,
)


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


async def test_create_user_and_get_by_email(conn):
    email = f"{uuid.uuid4()}@example.com"
    created = await create_user(conn, email, "hashed-password")
    fetched = await get_user_by_email(conn, email)
    assert fetched["id"] == created["id"]
    assert fetched["email"] == email


async def test_get_user_by_email_returns_none_when_missing(conn):
    assert await get_user_by_email(conn, "nobody@example.com") is None


async def test_get_user_by_id_returns_user(conn):
    email = f"{uuid.uuid4()}@example.com"
    created = await create_user(conn, email, "hashed-password")
    fetched = await get_user_by_id(conn, created["id"])
    assert fetched["email"] == email


async def test_insert_and_get_refresh_token(conn):
    email = f"{uuid.uuid4()}@example.com"
    user = await create_user(conn, email, "hashed-password")
    expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    await insert_refresh_token(conn, user["id"], "token-hash-abc", expires_at)
    fetched = await get_refresh_token(conn, "token-hash-abc")
    assert fetched["user_id"] == user["id"]
    assert fetched["revoked_at"] is None


async def test_revoke_refresh_token(conn):
    email = f"{uuid.uuid4()}@example.com"
    user = await create_user(conn, email, "hashed-password")
    expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    await insert_refresh_token(conn, user["id"], "token-hash-xyz", expires_at)
    await revoke_refresh_token(conn, "token-hash-xyz")
    fetched = await get_refresh_token(conn, "token-hash-xyz")
    assert fetched["revoked_at"] is not None


async def test_upsert_google_credentials_inserts_then_updates(conn):
    email = f"{uuid.uuid4()}@example.com"
    user = await create_user(conn, email, "hashed-password")
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await upsert_google_credentials(conn, user["id"], "enc-refresh-1", "enc-access-1", expires_at)
    await upsert_google_credentials(conn, user["id"], "enc-refresh-2", "enc-access-2", expires_at)
    row = await conn.fetchrow(
        "SELECT refresh_token_encrypted FROM google_credentials WHERE user_id = $1", user["id"]
    )
    assert row["refresh_token_encrypted"] == "enc-refresh-2"
