import logging

import app.auth.google_token as gt_mod
from app.auth.google_token import get_google_access_token
from app.auth.security import encrypt_token


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value


async def test_cache_hit_returns_without_touching_postgres():
    r = FakeRedis()
    r.store["google_token:u1"] = "ya29.cached"
    # pool=None proves no DB access happens on a hit
    assert await get_google_access_token(None, r, "u1") == "ya29.cached"


async def test_no_credentials_returns_none(monkeypatch):
    async def no_creds(pool, user_id):
        return None
    monkeypatch.setattr(gt_mod, "get_google_credentials", no_creds)

    assert await get_google_access_token(object(), FakeRedis(), "u1") is None


async def test_refresh_success_caches_token(monkeypatch):
    async def creds(pool, user_id):
        return {"refresh_token_encrypted": encrypt_token("refresh-secret")}
    monkeypatch.setattr(gt_mod, "get_google_credentials", creds)

    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "ya29.fresh", "expires_in": 3599}

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None):
            captured.update(url=url, data=data)
            return FakeResponse()

    monkeypatch.setattr(gt_mod.httpx, "AsyncClient", FakeClient)

    r = FakeRedis()
    token = await get_google_access_token(object(), r, "u1")

    assert token == "ya29.fresh"
    assert r.store["google_token:u1"] == "ya29.fresh"
    assert captured["data"]["refresh_token"] == "refresh-secret"
    assert captured["data"]["grant_type"] == "refresh_token"


async def test_refresh_failure_returns_none_and_logs(monkeypatch, caplog):
    async def creds(pool, user_id):
        return {"refresh_token_encrypted": encrypt_token("refresh-secret")}
    monkeypatch.setattr(gt_mod, "get_google_credentials", creds)

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None):
            raise ConnectionError("google down")

    monkeypatch.setattr(gt_mod.httpx, "AsyncClient", FakeClient)

    with caplog.at_level(logging.ERROR):
        result = await get_google_access_token(object(), FakeRedis(), "u1")

    assert result is None
    assert "Google token refresh failed" in caplog.text
