import datetime as dt

import jwt
import pytest

from app.config import settings
from app.auth.google_oauth import LOGIN_SCOPES, build_flow, create_state, verify_state


def test_connect_state_round_trips_user_id():
    payload = verify_state(create_state("connect", "user-123"))
    assert payload["purpose"] == "connect"
    assert payload["user_id"] == "user-123"


def test_login_state_has_no_user():
    payload = verify_state(create_state("login"))
    assert payload["purpose"] == "login"
    assert "user_id" not in payload


def test_legacy_state_without_purpose_is_connect():
    legacy = jwt.encode(
        {"user_id": "u1", "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    assert verify_state(legacy)["purpose"] == "connect"


def test_verify_state_rejects_expired_state():
    expired_state = jwt.encode(
        {"purpose": "login", "exp": dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_state(expired_state)


def test_build_flow_does_not_generate_pkce_verifier():
    # The callback builds a fresh Flow, so a verifier made at auth-URL time is lost
    # and Google rejects the exchange with "Missing code verifier".
    flow = build_flow()
    url, _ = flow.authorization_url(access_type="offline", state="s")
    assert flow.code_verifier is None
    assert "code_challenge" not in url


def test_login_scopes_use_full_urls_and_include_calendar():
    assert "openid" in LOGIN_SCOPES
    assert "https://www.googleapis.com/auth/userinfo.email" in LOGIN_SCOPES
    assert "https://www.googleapis.com/auth/calendar" in LOGIN_SCOPES
