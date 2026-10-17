import logging

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_HEADER = "x-google-access-token"

MISSING_TOKEN_MESSAGE = (
    "❌ Chưa kết nối Google Calendar. Người dùng cần kết nối tài khoản Google trước."
)


def extract_access_token(request) -> str | None:
    """Read the caller's Google access token from the MCP request headers.

    The token is deliberately not a tool parameter: anything in a tool signature
    ends up in the JSON schema the planner's LLM is asked to fill in.
    """
    if request is None:
        logger.warning("MCP context has no HTTP request; cannot read %s", GOOGLE_TOKEN_HEADER)
        return None
    return request.headers.get(GOOGLE_TOKEN_HEADER) or None
