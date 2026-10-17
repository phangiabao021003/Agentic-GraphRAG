from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.cache.sessions import delete_session, get_session, set_session
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
from app.auth.google_oauth import build_flow, create_state, verify_state
from app.config import settings
from app.models.auth import (
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
    state = create_state(str(user["id"]))
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    # JSON, not a redirect: the SPA fetches this with a Bearer header (a plain
    # browser navigation cannot carry one), then does window.location = url.
    return {"url": authorization_url}


@router.get("/auth/google/callback")
async def google_callback(code: str, state: str, request: Request):
    try:
        user_id = verify_state(state)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state")

    flow = build_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials
    expiry = credentials.expiry
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    await upsert_google_credentials(
        request.app.state.pg_pool,
        user_id,
        encrypt_token(credentials.refresh_token),
        encrypt_token(credentials.token),
        expiry,
    )
    return RedirectResponse(f"{settings.frontend_url}?google=connected")


@router.get("/auth/google/status")
async def google_status(request: Request, user: dict = Depends(get_current_user)):
    creds = await get_google_credentials(request.app.state.pg_pool, user["id"])
    return {"connected": creds is not None}
