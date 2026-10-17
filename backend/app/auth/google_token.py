"""Per-user Google access token: Redis-cached, refreshed from the stored
(encrypted) refresh token when needed. Failure never blocks chat."""
import logging

import httpx

from app.cache.sessions import get_google_token, set_google_token
from app.config import settings
from app.db.users import get_google_credentials
from app.auth.security import decrypt_token

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


async def get_google_access_token(pool, r, user_id) -> str | None:
    cached = await get_google_token(r, user_id)
    if cached:
        return cached

    creds = await get_google_credentials(pool, user_id)
    if creds is None:
        return None

    try:
        refresh_token = decrypt_token(creds["refresh_token_encrypted"])
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                },
            )
            resp.raise_for_status()
            access_token = resp.json()["access_token"]
    except Exception:
        logger.exception("Google token refresh failed for user %s", user_id)
        return None

    await set_google_token(r, user_id, access_token)
    return access_token
