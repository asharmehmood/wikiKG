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

import uuid

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.interfaces import VectorStoreInterface
from app.core.logging import get_logger

# Authoritative retrieval prefix — referenced in test assertions.
MXBAI_RETRIEVAL_PREFIX = "Represent this sentence for searching relevant passages: "

logger = get_logger(__name__)


class QdrantStore(VectorStoreInterface):
    """Production VectorStoreInterface backed by a Qdrant collection."""

    def __init__(
        self,
        qdrant_host: str,
        qdrant_port: int,
        embed_model: str,
        ollama_host: str,
    ) -> None:
        self._client = AsyncQdrantClient(
            url=f"http://{qdrant_host}:{qdrant_port}"
        )
        self._embeddings = OllamaEmbeddings(
            model=embed_model,
            base_url=ollama_host,
        )

    async def upsert(self, chunks: list[Document], collection: str) -> None:
        """Embed and store *chunks* in *collection*; creates the collection if absent."""
        if not chunks:
            return

        texts = [doc.page_content for doc in chunks]
        vectors: list[list[float]] = await self._embeddings.aembed_documents(texts)
        vector_size = len(vectors[0])

        # Ensure collection exists with correct vector config
        existing = {c.name for c in (await self._client.get_collections()).collections}
        if collection not in existing:
            await self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            logger.info("qdrant_collection_created", extra={"collection": collection})

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={"page_content": doc.page_content, **doc.metadata},
            )
            for doc, vec in zip(chunks, vectors)
        ]
        await self._client.upsert(collection_name=collection, points=points)
        logger.info(
            "qdrant_upsert_done",
            extra={"collection": collection, "count": len(points)},
        )

    async def search(
        self, query_vector: list[float], collection: str, k: int
    ) -> list[Document]:
        """Return the *k* most similar documents to *query_vector*."""
        results = await self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=k,
            with_payload=True,
        )
        docs: list[Document] = []
        for hit in results:
            payload = dict(hit.payload or {})
            page_content = payload.pop("page_content", "")
            docs.append(Document(page_content=page_content, metadata=payload))
        return docs

    async def delete_collection(self, collection: str) -> None:
        """Drop *collection* if it exists; silently no-ops otherwise."""
        try:
            await self._client.delete_collection(collection_name=collection)
            logger.info("qdrant_collection_deleted", extra={"collection": collection})
        except Exception:
            # Collection may not exist on first ingestion — that is fine.
            pass


async def embed_query(
    question: str,
    embed_model: str,
    ollama_host: str,
) -> list[float]:
    """Return the embedding vector for *question* with the retrieval prefix applied."""
    prefixed = MXBAI_RETRIEVAL_PREFIX + question
    embeddings = OllamaEmbeddings(model=embed_model, base_url=ollama_host)
    vector: list[float] = await embeddings.aembed_query(prefixed)
    return vector
