import uuid

from fastapi.testclient import TestClient

from app.main import app


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


def test_register_returns_token_pair():
    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={"email": _unique_email(), "password": "correct horse battery staple"},
        )
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_register_rejects_duplicate_email():
    email = _unique_email()
    with TestClient(app) as client:
        client.post(
            "/auth/register", json={"email": email, "password": "correct horse battery staple"}
        )
        response = client.post(
            "/auth/register", json={"email": email, "password": "another password"}
        )
    assert response.status_code == 409


def test_login_returns_token_pair_for_correct_credentials():
    email = _unique_email()
    with TestClient(app) as client:
        client.post(
            "/auth/register", json={"email": email, "password": "correct horse battery staple"}
        )
        response = client.post(
            "/auth/login", json={"email": email, "password": "correct horse battery staple"}
        )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_rejects_wrong_password():
    email = _unique_email()
    with TestClient(app) as client:
        client.post(
            "/auth/register", json={"email": email, "password": "correct horse battery staple"}
        )
        response = client.post("/auth/login", json={"email": email, "password": "wrong password"})
    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token():
    email = _unique_email()
    with TestClient(app) as client:
        register_response = client.post(
            "/auth/register", json={"email": email, "password": "correct horse battery staple"}
        )
        access_token = register_response.json()["access_token"]
        response = client.get("/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == email


def test_me_rejects_missing_token():
    with TestClient(app) as client:
        response = client.get("/me")
    assert response.status_code == 401


def test_refresh_rotates_token_and_revokes_old_one():
    email = _unique_email()
    with TestClient(app) as client:
        register_response = client.post(
            "/auth/register", json={"email": email, "password": "correct horse battery staple"}
        )
        old_refresh_token = register_response.json()["refresh_token"]
        refresh_response = client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
        assert refresh_response.status_code == 200
        new_refresh_token = refresh_response.json()["refresh_token"]
        assert new_refresh_token != old_refresh_token

        reuse_response = client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
    assert reuse_response.status_code == 401


def test_logout_revokes_refresh_token():
    email = _unique_email()
    with TestClient(app) as client:
        register_response = client.post(
            "/auth/register", json={"email": email, "password": "correct horse battery staple"}
        )
        refresh_token = register_response.json()["refresh_token"]
        logout_response = client.post("/auth/logout", json={"refresh_token": refresh_token})
        assert logout_response.status_code == 204

        reuse_response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse_response.status_code == 401


# ---- session cache (sub-project #6) ----
import asyncio

import asyncpg
import redis as redis_sync

from app.config import settings
from app.auth.security import hash_refresh_token


def _redis():
    return redis_sync.Redis.from_url(settings.redis_url, decode_responses=True)


def _register(client):
    email = _unique_email()
    resp = client.post(
        "/auth/register", json={"email": email, "password": "correct horse battery staple"}
    )
    return resp.json()


def _delete_refresh_row(token_hash: str):
    async def _run():
        conn = await asyncpg.connect(settings.database_url)
        await conn.execute("DELETE FROM refresh_tokens WHERE token_hash = $1", token_hash)
        await conn.close()

    asyncio.run(_run())


def test_issue_tokens_stores_session_key_with_ttl():
    with TestClient(app) as client:
        tokens = _register(client)
    key = f"session:{hash_refresh_token(tokens['refresh_token'])}"
    r = _redis()
    try:
        assert r.get(key) is not None
        assert r.ttl(key) > 0
    finally:
        r.delete(key)


def test_refresh_serves_from_session_cache_without_postgres_read():
    with TestClient(app) as client:
        tokens = _register(client)
        old_hash = hash_refresh_token(tokens["refresh_token"])
        # remove the PG row: a successful refresh now can only come from Redis
        _delete_refresh_row(old_hash)

        resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert resp.status_code == 200
    r = _redis()
    new_key = f"session:{hash_refresh_token(resp.json()['refresh_token'])}"
    try:
        assert r.get(f"session:{old_hash}") is None  # rotation deleted the old key
        assert r.get(new_key) is not None
    finally:
        r.delete(new_key)


def test_logout_deletes_session_key():
    with TestClient(app) as client:
        tokens = _register(client)
        key = f"session:{hash_refresh_token(tokens['refresh_token'])}"
        assert _redis().get(key) is not None
        client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert _redis().get(key) is None


# ---- Google connect UX changes (sub-project #7) ----


def test_google_connect_returns_authorization_url(monkeypatch):
    class FakeFlow:
        def authorization_url(self, **kwargs):
            return ("https://accounts.google.com/o/oauth2/auth?fake=1", "state123")

    monkeypatch.setattr("app.auth.routes.build_flow", lambda: FakeFlow())
    with TestClient(app) as client:
        tokens = _register(client)
        resp = client.get("/auth/google/connect",
                          headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("https://accounts.google.com/")


def test_google_status_reflects_credentials():
    with TestClient(app) as client:
        tokens = _register(client)
        h = {"Authorization": f"Bearer {tokens['access_token']}"}
        assert client.get("/auth/google/status", headers=h).json() == {"connected": False}
