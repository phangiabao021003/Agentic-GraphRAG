"""Every Redis touch goes through here. All helpers swallow Redis failures
(logged) — the cache accelerates, it must never break a request."""
import json
import logging

logger = logging.getLogger(__name__)

CONV_TTL = 21600  # 6h — must stay far below the pg_cron 60-day cleanup (spec §6)
MAX_CACHED_MESSAGES = 30


def _messages_key(conversation_id) -> str:
    return f"conv:{conversation_id}:messages"


def _conversations_key(user_id) -> str:
    return f"user:{user_id}:conversations"


async def get_cached_messages(r, conversation_id) -> list | None:
    try:
        items = await r.lrange(_messages_key(conversation_id), 0, -1)
        if not items:
            return None
        return [json.loads(i) for i in items]
    except Exception:
        logger.exception("get_cached_messages failed for %s", conversation_id)
        return None


async def cache_messages(r, conversation_id, messages: list[dict]) -> None:
    """Backfill: replace the whole list."""
    try:
        key = _messages_key(conversation_id)
        pipe = r.pipeline()
        pipe.delete(key)
        if messages:
            pipe.rpush(key, *[json.dumps(m, ensure_ascii=False) for m in messages])
            pipe.expire(key, CONV_TTL)
        await pipe.execute()
    except Exception:
        logger.exception("cache_messages failed for %s", conversation_id)


async def append_messages(r, conversation_id, messages: list[dict]) -> None:
    """Append after a turn — only if the key exists. RPUSH on a missing key would
    create a 2-message list that later reads would mistake for the full history."""
    try:
        key = _messages_key(conversation_id)
        if not await r.exists(key):
            return
        pipe = r.pipeline()
        pipe.rpush(key, *[json.dumps(m, ensure_ascii=False) for m in messages])
        pipe.ltrim(key, -MAX_CACHED_MESSAGES, -1)
        pipe.expire(key, CONV_TTL)
        await pipe.execute()
    except Exception:
        logger.exception("append_messages failed for %s", conversation_id)


async def get_cached_conversations(r, user_id) -> list | None:
    try:
        raw = await r.get(_conversations_key(user_id))
        return json.loads(raw) if raw else None
    except Exception:
        logger.exception("get_cached_conversations failed for %s", user_id)
        return None


async def cache_conversations(r, user_id, payload: list[dict]) -> None:
    try:
        await r.set(_conversations_key(user_id), json.dumps(payload, ensure_ascii=False), ex=CONV_TTL)
    except Exception:
        logger.exception("cache_conversations failed for %s", user_id)


async def invalidate_conversations(r, user_id) -> None:
    try:
        await r.delete(_conversations_key(user_id))
    except Exception:
        logger.exception("invalidate_conversations failed for %s", user_id)


async def drop_conversation(r, user_id, conversation_id) -> None:
    try:
        await r.delete(_messages_key(conversation_id), _conversations_key(user_id))
    except Exception:
        logger.exception("drop_conversation failed for %s", conversation_id)
