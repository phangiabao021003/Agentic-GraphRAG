import datetime as dt

import jwt
import pytest

from app.config import settings
from app.auth.google_oauth import create_state, verify_state


def test_create_state_round_trips_user_id():
    state = create_state("user-123")
    assert verify_state(state) == "user-123"


def test_verify_state_rejects_expired_state():
    expired_payload = {
        "user_id": "user-123",
        "exp": dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1),
    }
    expired_state = jwt.encode(expired_payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_state(expired_state)
