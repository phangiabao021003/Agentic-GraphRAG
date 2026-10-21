import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.auth.google_oauth import create_state
from app.main import app


class FakeCredentials:
    def __init__(self, refresh_token="refresh-xyz"):
        self.id_token = "fake-id-token"
        self.token = "access-xyz"
        self.refresh_token = refresh_token
        self.expiry = None


class FakeFlow:
    def __init__(self, refresh_token="refresh-xyz"):
        self.credentials = FakeCredentials(refresh_token)
        self.fetched_code = None

    def authorization_url(self, **kwargs):
        self.auth_kwargs = kwargs
        return ("https://accounts.google.com/o/oauth2/auth?fake=1", kwargs.get("state"))

    def fetch_token(self, code):
        self.fetched_code = code


@pytest.fixture
def google(monkeypatch):
    state = {"flow": FakeFlow(), "claims": None}
    monkeypatch.setattr("app.auth.routes.build_flow", lambda scopes=None: state["flow"])
    monkeypatch.setattr("app.auth.routes.verify_google_id_token", lambda token: state["claims"])
    return state


def _claims(email=None, verified=True):
    return {"sub": f"sub-{uuid.uuid4()}", "email": email or f"{uuid.uuid4()}@example.com",
            "email_verified": verified}


def _query(resp):
    return parse_qs(urlparse(resp.headers["location"]).query)


def test_login_redirects_to_google(google):
    with TestClient(app) as client:
        resp = client.get("/auth/google/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"].startswith("https://accounts.google.com/")
    assert google["flow"].auth_kwargs["access_type"] == "offline"


def test_callback_login_issues_code_that_exchanges_once(google):
    google["claims"] = _claims()
    with TestClient(app) as client:
        resp = client.get("/auth/google/callback",
                          params={"state": create_state("login"), "code": "auth-code"},
                          follow_redirects=False)
        assert resp.status_code in (302, 307)
        code = _query(resp)["google_login"][0]

        pair = client.post("/auth/google/exchange", json={"code": code})
        assert pair.status_code == 200
        access = pair.json()["access_token"]
        me = client.get("/me", headers={"Authorization": f"Bearer {access}"})
        assert me.json()["email"] == google["claims"]["email"]

        status_resp = client.get("/auth/google/status", headers={"Authorization": f"Bearer {access}"})
        assert status_resp.json() == {"connected": True}

        assert client.post("/auth/google/exchange", json={"code": code}).status_code == 401
    assert google["flow"].fetched_code == "auth-code"


def test_callback_login_without_refresh_token_still_logs_in(google):
    google["flow"] = FakeFlow(refresh_token=None)
    google["claims"] = _claims()
    with TestClient(app) as client:
        resp = client.get("/auth/google/callback",
                          params={"state": create_state("login"), "code": "c"},
                          follow_redirects=False)
        assert "google_login" in _query(resp)


def test_callback_login_rejects_unverified_email(google):
    google["claims"] = _claims(verified=False)
    with TestClient(app) as client:
        resp = client.get("/auth/google/callback",
                          params={"state": create_state("login"), "code": "c"},
                          follow_redirects=False)
    assert _query(resp)["google_error"] == ["unverified_email"]


def test_callback_login_denied(google):
    with TestClient(app) as client:
        resp = client.get("/auth/google/callback",
                          params={"state": create_state("login"), "error": "access_denied"},
                          follow_redirects=False)
    assert _query(resp)["google_error"] == ["denied"]


def test_callback_bad_state(google):
    with TestClient(app) as client:
        resp = client.get("/auth/google/callback",
                          params={"state": "not-a-jwt", "code": "c"},
                          follow_redirects=False)
    assert _query(resp)["google_error"] == ["invalid_state"]


def test_callback_login_token_exchange_failure(google):
    def boom(code):
        raise RuntimeError("google down")
    google["flow"].fetch_token = boom
    with TestClient(app) as client:
        resp = client.get("/auth/google/callback",
                          params={"state": create_state("login"), "code": "c"},
                          follow_redirects=False)
    assert _query(resp)["google_error"] == ["failed"]


def test_exchange_rejects_unknown_code():
    with TestClient(app) as client:
        assert client.post("/auth/google/exchange", json={"code": "nope"}).status_code == 401
