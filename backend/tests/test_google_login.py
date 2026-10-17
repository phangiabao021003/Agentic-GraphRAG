import asyncio
import uuid

import asyncpg
from fastapi.testclient import TestClient

from app.auth.google_login import find_or_create_google_user
from app.auth.security import verify_password
from app.config import settings
from app.main import app


def _email() -> str:
    return f"{uuid.uuid4()}@example.com"


def _run(coro_fn):
    async def _wrapped():
        pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
        try:
            return await coro_fn(pool)
        finally:
            await pool.close()
    return asyncio.run(_wrapped())


def test_verify_password_rejects_missing_hash():
    assert verify_password("anything", None) is False


def test_creates_new_google_user_without_password():
    email, sub = _email(), f"sub-{uuid.uuid4()}"

    async def go(pool):
        user = await find_or_create_google_user(pool, sub, email)
        row = await pool.fetchrow("SELECT email, password_hash, google_sub FROM users WHERE id = $1", user["id"])
        return user, row

    user, row = _run(go)
    assert user["email"] == email
    assert row["password_hash"] is None
    assert row["google_sub"] == sub


def test_returns_same_user_for_same_sub():
    email, sub = _email(), f"sub-{uuid.uuid4()}"

    async def go(pool):
        first = await find_or_create_google_user(pool, sub, email)
        second = await find_or_create_google_user(pool, sub, email)
        return first, second

    first, second = _run(go)
    assert first["id"] == second["id"]


def test_links_existing_password_user_by_email():
    email, sub = _email(), f"sub-{uuid.uuid4()}"
    with TestClient(app) as client:
        client.post("/auth/register", json={"email": email, "password": "correct horse battery staple"})

    async def go(pool):
        existing = await pool.fetchrow("SELECT id FROM users WHERE email = $1", email)
        user = await find_or_create_google_user(pool, sub, email)
        linked = await pool.fetchval("SELECT google_sub FROM users WHERE id = $1", existing["id"])
        return existing["id"], user["id"], linked

    existing_id, user_id, linked = _run(go)
    assert user_id == existing_id
    assert linked == sub
    # password login still works for the linked account
    with TestClient(app) as client:
        resp = client.post("/auth/login", json={"email": email, "password": "correct horse battery staple"})
    assert resp.status_code == 200


def test_password_login_rejected_for_google_only_user():
    email, sub = _email(), f"sub-{uuid.uuid4()}"
    _run(lambda pool: find_or_create_google_user(pool, sub, email))
    with TestClient(app) as client:
        resp = client.post("/auth/login", json={"email": email, "password": "whatever-password"})
    assert resp.status_code == 401
