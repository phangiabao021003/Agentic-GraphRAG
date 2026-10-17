from datetime import datetime
from typing import Optional

import asyncpg


async def create_user(pool: asyncpg.Pool, email: str, password_hash: str) -> dict:
    row = await pool.fetchrow(
        "INSERT INTO users (email, password_hash) VALUES ($1, $2) "
        "RETURNING id, email, password_hash, created_at",
        email,
        password_hash,
    )
    return dict(row)


async def get_user_by_email(pool: asyncpg.Pool, email: str) -> Optional[dict]:
    row = await pool.fetchrow(
        "SELECT id, email, password_hash, created_at FROM users WHERE email = $1", email
    )
    return dict(row) if row else None


async def get_user_by_id(pool: asyncpg.Pool, user_id: str) -> Optional[dict]:
    row = await pool.fetchrow(
        "SELECT id, email, created_at FROM users WHERE id = $1", user_id
    )
    return dict(row) if row else None


async def insert_refresh_token(
    pool: asyncpg.Pool, user_id, token_hash: str, expires_at: datetime
) -> None:
    await pool.execute(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES ($1, $2, $3)",
        user_id,
        token_hash,
        expires_at,
    )


async def get_refresh_token(pool: asyncpg.Pool, token_hash: str) -> Optional[dict]:
    row = await pool.fetchrow(
        "SELECT id, user_id, expires_at, revoked_at FROM refresh_tokens WHERE token_hash = $1",
        token_hash,
    )
    return dict(row) if row else None


async def revoke_refresh_token(pool: asyncpg.Pool, token_hash: str) -> None:
    await pool.execute(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE token_hash = $1", token_hash
    )


async def upsert_google_credentials(
    pool: asyncpg.Pool,
    user_id,
    refresh_token_encrypted: str,
    access_token_encrypted: str,
    expires_at: datetime,
) -> None:
    await pool.execute(
        "INSERT INTO google_credentials "
        "(user_id, refresh_token_encrypted, access_token_encrypted, expires_at) "
        "VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (user_id) DO UPDATE SET "
        "refresh_token_encrypted = EXCLUDED.refresh_token_encrypted, "
        "access_token_encrypted = EXCLUDED.access_token_encrypted, "
        "expires_at = EXCLUDED.expires_at, "
        "updated_at = now()",
        user_id,
        refresh_token_encrypted,
        access_token_encrypted,
        expires_at,
    )


async def get_google_credentials(pool: asyncpg.Pool, user_id) -> Optional[dict]:
    row = await pool.fetchrow(
        "SELECT refresh_token_encrypted, access_token_encrypted, expires_at "
        "FROM google_credentials WHERE user_id = $1",
        user_id,
    )
    return dict(row) if row else None
