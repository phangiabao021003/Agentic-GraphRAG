import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.config import settings

ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
REFRESH_TOKEN_LIFETIME = timedelta(days=30)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + ACCESS_TOKEN_LIFETIME}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    return payload["sub"]


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + REFRESH_TOKEN_LIFETIME


def encrypt_token(value: str) -> str:
    fernet = Fernet(settings.google_token_encryption_key.encode("utf-8"))
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_token(value: str) -> str:
    fernet = Fernet(settings.google_token_encryption_key.encode("utf-8"))
    return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
