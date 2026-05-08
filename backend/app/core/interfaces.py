"""Abstract base classes for LLM and vector-store adapters.

These interfaces are the dependency-injection seams that let every
module be tested without live Ollama or Qdrant instances.

  LLMInterface        — implemented by OllamaLLM (T-13/T-15); mocked by MockLLM
  VectorStoreInterface — implemented by QdrantStore (T-14); mocked by InMemoryStore

Place all `from app.core.interfaces import ...` imports at the top of
consumer modules to avoid circular dependencies.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage


class LLMInterface(ABC):
    """Wrapper around a chat-completion model."""

    @abstractmethod
    async def generate(self, messages: list[BaseMessage]) -> str:
        """Return the full response as a single string (non-streaming)."""
        ...

    @abstractmethod
    async def stream(self, messages: list[BaseMessage]) -> AsyncIterator[str]:
        """Yield response tokens one at a time."""
        ...


class VectorStoreInterface(ABC):
    """Wrapper around a vector database collection."""

    @abstractmethod
    async def upsert(self, chunks: list[Document], collection: str) -> None:
        """Embed and store documents; overwrites existing vectors by id."""
        ...

    @abstractmethod
    async def search(
        self, query_vector: list[float], collection: str, k: int
    ) -> list[Document]:
        """Return the *k* most similar documents to *query_vector*."""
        ...

    @abstractmethod
    async def delete_collection(self, collection: str) -> None:
        """Drop an entire collection (used for idempotent re-ingestion)."""
        ...
