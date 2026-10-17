from app.config import settings
from app.llm_providers.base import LLMProvider, LLMProviderError
from app.llm_providers.gemini import GeminiProvider
from app.llm_providers.openai_compat import OpenAICompatProvider

__all__ = ["LLMProvider", "LLMProviderError", "get_provider"]


def get_provider() -> LLMProvider:
    if settings.llm_provider == "gemini":
        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.llm_model)
    if settings.llm_provider == "openai_compat":
        return OpenAICompatProvider(base_url=settings.llm_server_url, model=settings.llm_model)
    raise LLMProviderError(f"unknown LLM_PROVIDER: {settings.llm_provider!r}")
