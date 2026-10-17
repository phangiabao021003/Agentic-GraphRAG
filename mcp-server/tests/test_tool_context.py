import logging

from app.tools.context import GOOGLE_TOKEN_HEADER, extract_access_token


class FakeRequest:
    def __init__(self, headers):
        self.headers = headers


def test_extract_access_token_returns_header_value():
    request = FakeRequest({GOOGLE_TOKEN_HEADER: "ya29.token"})
    assert extract_access_token(request) == "ya29.token"


def test_extract_access_token_returns_none_when_header_absent():
    assert extract_access_token(FakeRequest({})) is None


def test_extract_access_token_returns_none_when_header_empty():
    assert extract_access_token(FakeRequest({GOOGLE_TOKEN_HEADER: ""})) is None


def test_extract_access_token_returns_none_and_logs_when_request_is_none(caplog):
    with caplog.at_level(logging.WARNING):
        result = extract_access_token(None)
    assert result is None
    assert "no http request" in caplog.text.lower()
