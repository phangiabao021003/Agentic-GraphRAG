import uuid

import pytest
import redis.asyncio as aioredis

from app.cache.conversations import (
    append_messages,
    cache_conversations,
    cache_messages,
    drop_conversation,
    get_cached_conversations,
    get_cached_messages,
    invalidate_conversations,
)
from app.cache.sessions import (
    delete_session,
    get_google_token,
    get_session,
    set_google_token,
    set_session,
)
from app.config import settings


@pytest.fixture
async def r():
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    created = []
    original_set = None
    try:
        yield client
    finally:
        keys = await client.keys("test:*")
        keys += await client.keys("conv:test:*")
        keys += await client.keys("user:test:*")
        keys += await client.keys("session:test:*")
        keys += await client.keys("google_token:test:*")
        if keys:
            await client.delete(*keys)
        await client.aclose()


class BrokenRedis:
    def __getattr__(self, name):
        async def boom(*a, **k):
            raise ConnectionError("redis down")
        return boom


def cid():
    return f"test:{uuid.uuid4()}"


MSGS = [{"role": "user", "content": "xin chào"}, {"role": "assistant", "content": "chào bạn"}]


async def test_messages_roundtrip_and_ttl(r):
    c = cid()
    await cache_messages(r, c, MSGS)
    assert await get_cached_messages(r, c) == MSGS
    assert await r.ttl(f"conv:{c}:messages") > 0


async def test_get_cached_messages_returns_none_on_miss(r):
    assert await get_cached_messages(r, cid()) is None


async def test_append_only_when_key_exists(r):
    c = cid()
    await append_messages(r, c, MSGS)  # key absent -> must NOT create a partial list
    assert await get_cached_messages(r, c) is None

    await cache_messages(r, c, MSGS)
    await append_messages(r, c, [{"role": "user", "content": "next"}])
    cached = await get_cached_messages(r, c)
    assert len(cached) == 3 and cached[-1]["content"] == "next"


async def test_append_trims_to_last_30(r):
    c = cid()
    await cache_messages(r, c, [{"role": "user", "content": f"m{i}"} for i in range(30)])
    await append_messages(r, c, [{"role": "user", "content": "m30"}])
    cached = await get_cached_messages(r, c)
    assert len(cached) == 30
    assert cached[0]["content"] == "m1" and cached[-1]["content"] == "m30"


async def test_conversations_roundtrip_and_invalidate(r):
    u = cid()
    payload = [{"id": "c1", "title": "hỏi vitamin", "updated_at": "2026-09-06T09:00:00"}]
    await cache_conversations(r, u, payload)
    assert await get_cached_conversations(r, u) == payload
    await invalidate_conversations(r, u)
    assert await get_cached_conversations(r, u) is None


async def test_drop_conversation_removes_both_keys(r):
    u, c = cid(), cid()
    await cache_messages(r, c, MSGS)
    await cache_conversations(r, u, [{"id": c}])
    await drop_conversation(r, u, c)
    assert await get_cached_messages(r, c) is None
    assert await get_cached_conversations(r, u) is None


async def test_session_set_get_delete(r):
    h = cid()
    await set_session(r, h, "user-42", ttl=60)
    assert await get_session(r, h) == "user-42"
    await delete_session(r, h)
    assert await get_session(r, h) is None


async def test_google_token_roundtrip(r):
    u = cid()
    await set_google_token(r, u, "ya29.x")
    assert await get_google_token(r, u) == "ya29.x"
    assert await r.ttl(f"google_token:{u}") > 0


async def test_every_helper_degrades_when_redis_is_down():
    broken = BrokenRedis()
    assert await get_cached_messages(broken, "c") is None
    await cache_messages(broken, "c", MSGS)
    await append_messages(broken, "c", MSGS)
    assert await get_cached_conversations(broken, "u") is None
    await cache_conversations(broken, "u", [])
    await invalidate_conversations(broken, "u")
    await drop_conversation(broken, "u", "c")
    await set_session(broken, "h", "u", ttl=1)
    assert await get_session(broken, "h") is None
    await delete_session(broken, "h")
    assert await get_google_token(broken, "u") is None
    await set_google_token(broken, "u", "t")


async def test_login_code_is_single_use():
    import redis.asyncio as aioredis
    from app.config import settings
    from app.cache.sessions import LOGIN_CODE_TTL, pop_login_code, store_login_code

    r = aioredis.from_url(settings.redis_url)
    try:
        code = f"test-{uuid.uuid4()}"
        assert await store_login_code(r, code, {"access_token": "a", "refresh_token": "b"}) is True
        assert 0 < await r.ttl(f"google_login:{code}") <= LOGIN_CODE_TTL
        assert await pop_login_code(r, code) == {"access_token": "a", "refresh_token": "b"}
        assert await pop_login_code(r, code) is None
    finally:
        await r.aclose()


async def test_login_code_helpers_degrade_when_redis_is_down():
    from app.cache.sessions import pop_login_code, store_login_code

    broken = BrokenRedis()
    assert await store_login_code(broken, "c", {"access_token": "a", "refresh_token": "b"}) is False
    assert await pop_login_code(broken, "c") is None
