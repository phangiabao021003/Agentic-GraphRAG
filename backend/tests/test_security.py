import datetime as dt

import jwt
import pytest

from app.config import settings
from app.auth.security import (
    create_access_token,
    decode_access_token,
    decrypt_token,
    encrypt_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_hash_password_verifies_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_hash_password_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_create_access_token_round_trips_user_id():
    token = create_access_token("user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_access_token_rejects_expired_token():
    expired_payload = {
        "sub": "user-123",
        "exp": dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1),
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_generate_refresh_token_produces_unique_values():
    assert generate_refresh_token() != generate_refresh_token()


def test_hash_refresh_token_is_deterministic():
    token = generate_refresh_token()
    assert hash_refresh_token(token) == hash_refresh_token(token)


def test_hash_refresh_token_differs_for_different_tokens():
    assert hash_refresh_token("a") != hash_refresh_token("b")


def test_encrypt_decrypt_round_trip():
    plaintext = "google-refresh-token-value"
    encrypted = encrypt_token(plaintext)
    assert encrypted != plaintext
    assert decrypt_token(encrypted) == plaintext
