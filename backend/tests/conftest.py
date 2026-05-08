"""Shared pytest fixtures for unit and integration tests.

Fixtures:
    settings_override   — overrides get_settings() with test values
    mock_llm            — MockLLM that returns a fixed string
    mock_embedder       — MockEmbedder that returns a zero vector
    qdrant_service      — spins up a real Qdrant Docker container (integration)
    async_client        — httpx.AsyncClient pointed at the test FastAPI app

MockLLM and InMemoryStore are used via FastAPI dependency_overrides so
that no live Ollama or Qdrant instance is required for unit tests.

See T-23 for integration-test fixture implementation.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Placeholder fixtures — implemented in T-23
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    """Return a MockLLM stub.  Implemented in T-23."""
    raise NotImplementedError("Implemented in T-23")


@pytest.fixture
def mock_embedder():
    """Return a MockEmbedder stub.  Implemented in T-23."""
    raise NotImplementedError("Implemented in T-23")
