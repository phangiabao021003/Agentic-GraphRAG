import asyncio
import logging

import httpx

from app.llm_providers.base import LLMProviderError

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 120  # thinking-generation models on free tiers can be slow
MAX_ATTEMPTS = 3
RETRY_DELAYS = [2, 5]  # seconds before attempt 2 and 3
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    def build_payload(self, messages: list[dict]) -> dict:
        payload: dict = {"contents": []}
        for m in messages:
            if m["role"] == "system":
                payload["systemInstruction"] = {"parts": [{"text": m["content"]}]}
            else:
                role = "model" if m["role"] == "assistant" else "user"
                payload["contents"].append({"role": role, "parts": [{"text": m["content"]}]})
        return payload

    def extract_text(self, data: dict) -> str:
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(f"unexpected Gemini response shape: {data}") from exc

    async def complete(self, messages: list[dict]) -> str:
        url = f"{GEMINI_BASE}/models/{self._model}:generateContent"
        payload = self.build_payload(messages)
        # The key goes in a header, NOT a query param — query params show up in
        # exception messages and logs.
        headers = {"x-goog-api-key": self._api_key}
        for attempt in range(MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    return self.extract_text(resp.json())
            except LLMProviderError:
                raise
            except Exception as exc:
                retryable = isinstance(exc, httpx.TimeoutException) or (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code in RETRYABLE_STATUS
                )
                if retryable and attempt < MAX_ATTEMPTS - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        "Gemini call failed (%s), retrying in %ss (attempt %d/%d)",
                        type(exc).__name__, delay, attempt + 1, MAX_ATTEMPTS,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.exception("Gemini call failed")
                raise LLMProviderError(str(exc)) from exc
        raise LLMProviderError("unreachable")  # pragma: no cover
