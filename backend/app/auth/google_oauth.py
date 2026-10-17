from datetime import datetime, timedelta, timezone

import jwt
from google_auth_oauthlib.flow import Flow

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]
STATE_LIFETIME = timedelta(minutes=10)


def build_flow() -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_oauth_redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri,
    )


def create_state(user_id: str) -> str:
    payload = {"user_id": user_id, "exp": datetime.now(timezone.utc) + STATE_LIFETIME}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_state(state: str) -> str:
    payload = jwt.decode(state, settings.jwt_secret, algorithms=["HS256"])
    return payload["user_id"]
