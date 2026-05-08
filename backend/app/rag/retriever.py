"""QdrantStore adapter and query-embedding helper.

Classes:
    QdrantStore   — implements VectorStoreInterface backed by Qdrant

Helpers:
    embed_query(question, embed_model, ollama_host) -> list[float]
        Embeds *question* with the mxbai-embed-large retrieval prefix
        applied BEFORE calling OllamaEmbeddings.

Retrieval prefix (must match model docs exactly — omitting it measurably
degrades retrieval quality, per DESIGN.md §8):
    "Represent this sentence for searching relevant passages: "

Implemented in: T-14
"""
from __future__ import annotations

from langchain_core.documents import Document

from app.core.interfaces import VectorStoreInterface

# Authoritative retrieval prefix — referenced in test assertions.
MXBAI_RETRIEVAL_PREFIX = "Represent this sentence for searching relevant passages: "


class QdrantStore(VectorStoreInterface):
    """Production VectorStoreInterface backed by a Qdrant collection."""

    def __init__(
        self,
        qdrant_host: str,
        qdrant_port: int,
        embed_model: str,
        ollama_host: str,
    ) -> None:
        raise NotImplementedError("Implemented in T-14")

    async def upsert(self, chunks: list[Document], collection: str) -> None:
        raise NotImplementedError("Implemented in T-14")

    async def search(
        self, query_vector: list[float], collection: str, k: int
    ) -> list[Document]:
        raise NotImplementedError("Implemented in T-14")

    async def delete_collection(self, collection: str) -> None:
        raise NotImplementedError("Implemented in T-14")


async def embed_query(
    question: str,
    embed_model: str,
    ollama_host: str,
) -> list[float]:
    """Return the embedding vector for *question* with the retrieval prefix applied."""
    raise NotImplementedError("Implemented in T-14")
