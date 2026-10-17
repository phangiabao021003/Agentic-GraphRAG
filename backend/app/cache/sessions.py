"""Session (refresh-token mirror) and Google-access-token keys."""
import logging

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_TTL = 3000  # 50 min; Google issues 60-min tokens


async def set_session(r, token_hash: str, user_id: str, ttl: int) -> None:
    try:
        await r.set(f"session:{token_hash}", str(user_id), ex=ttl)
    except Exception:
        logger.exception("set_session failed")


async def get_session(r, token_hash: str) -> str | None:
    try:
        value = await r.get(f"session:{token_hash}")
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else value
    except Exception:
        logger.exception("get_session failed")
        return None


async def delete_session(r, token_hash: str) -> None:
    try:
        await r.delete(f"session:{token_hash}")
    except Exception:
        logger.exception("delete_session failed")


async def get_google_token(r, user_id) -> str | None:
    try:
        value = await r.get(f"google_token:{user_id}")
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else value
    except Exception:
        logger.exception("get_google_token failed for %s", user_id)
        return None


async def set_google_token(r, user_id, token: str) -> None:
    try:
        await r.set(f"google_token:{user_id}", token, ex=GOOGLE_TOKEN_TTL)
    except Exception:
        logger.exception("set_google_token failed for %s", user_id)
