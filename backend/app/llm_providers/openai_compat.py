import logging

import httpx

from app.llm_providers.base import LLMProviderError

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 120  # thinking-generation models on free tiers can be slow


class OpenAICompatProvider:
    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    def build_payload(self, messages: list[dict]) -> dict:
        return {"model": self._model, "messages": messages, "temperature": 0}

    def extract_text(self, data: dict) -> str:
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(f"unexpected response shape: {data}") from exc

    async def complete(self, messages: list[dict]) -> str:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions", json=self.build_payload(messages)
                )
                resp.raise_for_status()
                return self.extract_text(resp.json())
        except LLMProviderError:
            raise
        except Exception as exc:
            logger.exception("OpenAI-compatible LLM call failed")
            raise LLMProviderError(str(exc)) from exc
