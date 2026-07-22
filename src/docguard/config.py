"""Runtime configuration, loaded from env / .env with safe defaults.

Everything defaults to offline mock providers so the whole system runs and
tests deterministically with no API keys.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCGUARD_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # providers
    llm_provider: str = "mock"           # mock | openai | anthropic
    embedding_provider: str = "mock"     # mock | openai
    vector_backend: str = "local"        # local | chroma

    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-5"
    openai_embed_model: str = "text-embedding-3-small"
    # optional OpenAI-compatible endpoint (e.g. NVIDIA / together / local vLLM)
    openai_base_url: str = ""

    # mapping
    similarity_threshold: float = 0.35

    # confidence thresholds (0..1)
    high_confidence: float = 0.85
    medium_confidence: float = 0.5

    # github / action
    auto_fix: bool = False
    docs_paths: str = "docs"
    src_paths: str = "src"

    # secrets read WITHOUT the DOCGUARD_ prefix (standard names)
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    github_token: str = Field(default="", validation_alias="GITHUB_TOKEN")

    def docs_path_list(self) -> list[str]:
        return [p.strip() for p in self.docs_paths.split(",") if p.strip()]

    def src_path_list(self) -> list[str]:
        return [p.strip() for p in self.src_paths.split(",") if p.strip()]


def load_settings(**overrides) -> Settings:
    return Settings(**overrides)
