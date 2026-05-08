"""Application settings loaded from environment / .env file.

All configuration is read via pydantic-settings.  Use get_settings()
everywhere — the result is cached after the first call so the .env file
is only parsed once per process.

Field names match the keys in .env.example exactly.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Ollama
    OLLAMA_HOST: str = "http://localhost:11434"
    GEN_MODEL: str = "llama3.1:8b"
    EMBED_MODEL: str = "mxbai-embed-large"

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # Chunking — DESIGN.md §4
    CHUNK_SIZE: int = 1500
    CHUNK_OVERLAP: int = 200

    # Retrieval — DESIGN.md §4
    TOP_K: int = 4

    # Logging
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()
