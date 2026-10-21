import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.cache.sessions import (
    delete_session,
    get_session,
    pop_login_code,
    set_session,
    store_login_code,
)
from app.db.users import (
    create_user,
    get_google_credentials,
    get_refresh_token,
    get_user_by_email,
    insert_refresh_token,
    revoke_refresh_token,
    upsert_google_credentials,
)
from app.auth.dependencies import get_current_user
from app.auth.google_login import find_or_create_google_user
from app.auth.google_oauth import (
    LOGIN_SCOPES,
    build_flow,
    create_state,
    verify_google_id_token,
    verify_state,
)
from app.config import settings
from app.models.auth import (
    GoogleExchangeRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.auth.security import (
    create_access_token,
    encrypt_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


async def _issue_tokens(request: Request, user_id) -> TokenResponse:
    access_token = create_access_token(str(user_id))
    refresh_token = generate_refresh_token()
    token_hash = hash_refresh_token(refresh_token)
    expires_at = refresh_token_expiry()
    await insert_refresh_token(
        request.app.state.pg_pool,
        user_id,
        token_hash,
        expires_at,
    )
    # Postgres first (source of truth), then the Redis session mirror.
    ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    await set_session(request.app.state.redis_client, token_hash, str(user_id), ttl)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request):
    existing = await get_user_by_email(request.app.state.pg_pool, body.email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = await create_user(request.app.state.pg_pool, body.email, hash_password(body.password))
    return await _issue_tokens(request, user["id"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    user = await get_user_by_email(request.app.state.pg_pool, body.email)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return await _issue_tokens(request, user["id"])


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"id": str(user["id"]), "email": user["email"]}


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request):
    token_hash = hash_refresh_token(body.refresh_token)
    # Session cache first: the value IS the user_id, so a hit needs no Postgres read.
    cached_user_id = await get_session(request.app.state.redis_client, token_hash)
    if cached_user_id is not None:
        user_id = cached_user_id
    else:
        record = await get_refresh_token(request.app.state.pg_pool, token_hash)
        if (
            record is None
            or record["revoked_at"] is not None
            or record["expires_at"] < datetime.now(timezone.utc)
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        user_id = record["user_id"]
    await revoke_refresh_token(request.app.state.pg_pool, token_hash)
    await delete_session(request.app.state.redis_client, token_hash)
    return await _issue_tokens(request, user_id)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, request: Request):
    token_hash = hash_refresh_token(body.refresh_token)
    await revoke_refresh_token(request.app.state.pg_pool, token_hash)
    await delete_session(request.app.state.redis_client, token_hash)


@router.get("/auth/google/connect")
async def google_connect(user: dict = Depends(get_current_user)):
    flow = build_flow()
    state = create_state("connect", str(user["id"]))
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    # JSON, not a redirect: the SPA fetches this with a Bearer header (a plain
    # browser navigation cannot carry one), then does window.location = url.
    return {"url": authorization_url}


def _frontend(query: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/?{query}")


async def _store_google_credentials(pool, user_id, credentials) -> None:
    expiry = credentials.expiry or (datetime.now(timezone.utc) + timedelta(hours=1))
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    await upsert_google_credentials(
        pool, user_id, encrypt_token(credentials.refresh_token), encrypt_token(credentials.token), expiry
    )


@router.get("/auth/google/login")
async def google_login():
    flow = build_flow(LOGIN_SCOPES)
    authorization_url, _ = flow.authorization_url(
        access_type="offline", prompt="select_account", state=create_state("login")
    )
    return RedirectResponse(authorization_url)


@router.get("/auth/google/callback")
async def google_callback(request: Request, state: str, code: str | None = None, error: str | None = None):
    try:
        payload = verify_state(state)
    except jwt.PyJWTError:
        logger.warning("Google callback with invalid or expired state")
        return _frontend("google_error=invalid_state")
    if payload["purpose"] == "login":
        return await _complete_google_login(request, code, error)
    return await _complete_google_connect(request, payload["user_id"], code, error)


async def _complete_google_connect(request: Request, user_id: str, code: str | None, error: str | None):
    if error or not code:
        logger.warning("Google connect returned error=%s", error)
        return _frontend("google=error")
    flow = build_flow()
    await run_in_threadpool(flow.fetch_token, code=code)
    await _store_google_credentials(request.app.state.pg_pool, user_id, flow.credentials)
    return _frontend("google=connected")


async def _complete_google_login(request: Request, code: str | None, error: str | None):
    if error or not code:
        logger.warning("Google sign-in returned error=%s", error)
        return _frontend("google_error=denied")
    try:
        flow = build_flow(LOGIN_SCOPES)
        await run_in_threadpool(flow.fetch_token, code=code)
        credentials = flow.credentials
        claims = await run_in_threadpool(verify_google_id_token, credentials.id_token)
    except Exception:
        logger.exception("Google sign-in token exchange / ID-token verification failed")
        return _frontend("google_error=failed")
    if not claims.get("email_verified"):
        logger.warning("Google sign-in rejected: unverified email %s", claims.get("email"))
        return _frontend("google_error=unverified_email")
    try:
        pool = request.app.state.pg_pool
        user = await find_or_create_google_user(pool, claims["sub"], claims["email"])
        if credentials.refresh_token:  # only on first grant; keep existing creds otherwise
            await _store_google_credentials(pool, user["id"], credentials)
        tokens = await _issue_tokens(request, user["id"])
        login_code = secrets.token_urlsafe(32)
        stored = await store_login_code(request.app.state.redis_client, login_code, tokens.model_dump())
    except Exception:
        logger.exception("Google sign-in failed while creating the session")
        return _frontend("google_error=failed")
    if not stored:
        return _frontend("google_error=failed")
    return _frontend(f"google_login={login_code}")


@router.post("/auth/google/exchange", response_model=TokenResponse)
async def google_exchange(body: GoogleExchangeRequest, request: Request):
    tokens = await pop_login_code(request.app.state.redis_client, body.code)
    if tokens is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired login code")
    return TokenResponse(**tokens)


@router.get("/auth/google/status")
async def google_status(request: Request, user: dict = Depends(get_current_user)):
    creds = await get_google_credentials(request.app.state.pg_pool, user["id"])
    return {"connected": creds is not None}
