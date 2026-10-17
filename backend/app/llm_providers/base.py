from typing import Protocol


class LLMProviderError(Exception):
    """Any failure talking to an LLM backend."""


class LLMProvider(Protocol):
    async def complete(self, messages: list[dict]) -> str: ...
