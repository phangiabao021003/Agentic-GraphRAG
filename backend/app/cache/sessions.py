"""Session (refresh-token mirror), Google-access-token and Google sign-in handoff keys."""
import json
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


LOGIN_CODE_TTL = 60  # seconds the SPA has to exchange a Google sign-in handoff code


async def store_login_code(r, code: str, tokens: dict) -> bool:
    """Transient handoff, not an entity mirror: the refresh token is already in Postgres.
    Returns False (logged) on failure so the caller can fail the login."""
    try:
        await r.set(f"google_login:{code}", json.dumps(tokens), ex=LOGIN_CODE_TTL)
        return True
    except Exception:
        logger.exception("store_login_code failed")
        return False


async def pop_login_code(r, code: str) -> dict | None:
    try:
        value = await r.getdel(f"google_login:{code}")
        if value is None:
            return None
        return json.loads(value.decode() if isinstance(value, bytes) else value)
    except Exception:
        logger.exception("pop_login_code failed")
        return None
