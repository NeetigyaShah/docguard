"""Select providers from settings. Defaults to deterministic mocks."""

from __future__ import annotations

from docguard.config import Settings
from docguard.providers.base import EmbeddingProvider, LLMProvider
from docguard.providers.mock import MockEmbeddingProvider, MockLLMProvider


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "openai":
        from docguard.providers.real import OpenAIEmbeddings

        return OpenAIEmbeddings(settings)
    return MockEmbeddingProvider()


def get_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "openai":
        from docguard.providers.real import OpenAILLM

        return OpenAILLM(settings)
    if settings.llm_provider == "anthropic":
        from docguard.providers.real import AnthropicLLM

        return AnthropicLLM(settings)
    return MockLLMProvider()
