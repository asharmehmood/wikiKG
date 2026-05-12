"""Shared pytest fixtures for unit and integration tests.

Fixtures:
    mock_llm            — MockLLM that returns a fixed string
    in_memory_store     — InMemoryStore implementing VectorStoreInterface
    app_client          — AsyncClient pointed at the test FastAPI app with
                          mocked LLM and in-memory vector store

Qdrant integration fixtures live in tests/integration/conftest.py.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

from app.core.interfaces import LLMInterface, VectorStoreInterface


# ---------------------------------------------------------------------------
# MockLLM
# ---------------------------------------------------------------------------

class MockLLM(LLMInterface):
    """Returns a fixed answer string; no Ollama required."""

    FIXED_ANSWER = "This is a mock LLM response."

    async def generate(self, messages: list[BaseMessage]) -> str:
        return self.FIXED_ANSWER

    async def stream(self, messages: list[BaseMessage]) -> AsyncIterator[str]:  # type: ignore[override]
        for word in self.FIXED_ANSWER.split():
            yield word + " "


@pytest.fixture
def mock_llm() -> MockLLM:
    return MockLLM()


# ---------------------------------------------------------------------------
# InMemoryStore (VectorStoreInterface)
# ---------------------------------------------------------------------------

class InMemoryStore(VectorStoreInterface):
    """Stores documents in memory; uses sequential integer 'vectors'."""

    def __init__(self) -> None:
        self._collections: dict[str, list[Document]] = {}

    async def upsert(self, chunks: list[Document], collection: str) -> None:
        self._collections[collection] = list(chunks)

    async def search(
        self, query_vector: list[float], collection: str, k: int
    ) -> list[Document]:
        return self._collections.get(collection, [])[:k]

    async def delete_collection(self, collection: str) -> None:
        self._collections.pop(collection, None)


@pytest.fixture
def in_memory_store() -> InMemoryStore:
    return InMemoryStore()


# ---------------------------------------------------------------------------
# FastAPI test client with dependency overrides
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def app_client(mock_llm: MockLLM, in_memory_store: InMemoryStore):
    """Return an AsyncClient wired to the FastAPI app with mocked dependencies."""
    from app.main import create_app
    from app.rag import retriever as retriever_module
    from app.ingestion import graph as ingestion_graph_module
    from app.rag import graph as rag_graph_module
    import app.api.routes as routes_module

    application = create_app()

    # Patch the factory functions in routes.py to return our mocks
    original_make_store = routes_module._make_store
    original_make_llm = routes_module._make_llm

    routes_module._make_store = lambda: in_memory_store  # type: ignore[assignment]
    routes_module._make_llm = lambda: mock_llm  # type: ignore[assignment]

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        yield client

    # Restore originals
    routes_module._make_store = original_make_store
    routes_module._make_llm = original_make_llm
