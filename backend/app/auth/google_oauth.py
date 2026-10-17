from datetime import datetime, timedelta, timezone

import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow

from app.config import settings

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
SCOPES = [CALENDAR_SCOPE]
# Full URLs: Google echoes scopes back in this form and oauthlib raises
# "Scope has changed" if the requested spelling differs.
LOGIN_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    CALENDAR_SCOPE,
]
STATE_LIFETIME = timedelta(minutes=10)


def build_flow(scopes: list[str] = SCOPES) -> Flow:
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
        scopes=scopes,
        redirect_uri=settings.google_oauth_redirect_uri,
        # Confidential client (has a secret): PKCE is optional, and the callback
        # builds a new Flow that would not have the verifier anyway.
        autogenerate_code_verifier=False,
    )


def create_state(purpose: str, user_id: str | None = None) -> str:
    payload = {"purpose": purpose, "exp": datetime.now(timezone.utc) + STATE_LIFETIME}
    if user_id is not None:
        payload["user_id"] = user_id
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_state(state: str) -> dict:
    payload = jwt.decode(state, settings.jwt_secret, algorithms=["HS256"])
    payload.setdefault("purpose", "connect")  # states issued before Google sign-in
    return payload


def verify_google_id_token(token: str) -> dict:
    """Blocking (may fetch Google certs); call from a thread."""
    return google_id_token.verify_oauth2_token(
        token, google_requests.Request(), settings.google_oauth_client_id
    )
