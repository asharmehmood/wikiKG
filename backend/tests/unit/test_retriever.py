"""Unit tests for rag/retriever.py — QdrantStore adapter.

All Qdrant and Ollama calls are mocked via unittest.mock.

Test cases:
  - upsert: empty chunks → no-op (no client calls)
  - upsert: creates new collection when absent, then calls client.upsert
  - upsert: skips collection creation when already exists
  - search: maps ScoredPoint payloads to Document objects correctly
  - delete_collection: delegates to client.delete_collection
  - delete_collection: silently ignores exceptions (collection absent)
  - embed_query: prepends the retrieval prefix before embedding
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.rag.retriever import MXBAI_RETRIEVAL_PREFIX, QdrantStore, embed_query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> QdrantStore:
    """Return a QdrantStore with mocked internals."""
    store = QdrantStore.__new__(QdrantStore)
    store._client = AsyncMock()
    store._embeddings = AsyncMock()
    return store


def _scored_point(page_content: str, section: str = "Intro") -> MagicMock:
    point = MagicMock()
    point.payload = {"page_content": page_content, "section_title": section}
    return point


# ---------------------------------------------------------------------------
# upsert — empty chunks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_empty_chunks_is_noop():
    store = _make_store()
    await store.upsert([], "col1")
    store._client.upsert.assert_not_called()
    store._embeddings.aembed_documents.assert_not_called()


# ---------------------------------------------------------------------------
# upsert — creates collection when absent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_creates_collection_when_absent():
    store = _make_store()

    # Simulate no existing collections
    existing = MagicMock()
    existing.collections = []
    store._client.get_collections = AsyncMock(return_value=existing)
    store._client.create_collection = AsyncMock()
    store._client.upsert = AsyncMock()
    store._embeddings.aembed_documents = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    doc = Document(page_content="Hello world", metadata={"section_title": "Intro"})
    await store.upsert([doc], "new_col")

    store._client.create_collection.assert_called_once()
    store._client.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# upsert — skips collection creation when already exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_skips_create_when_collection_exists():
    store = _make_store()

    existing_col = MagicMock()
    existing_col.name = "existing_col"
    existing = MagicMock()
    existing.collections = [existing_col]
    store._client.get_collections = AsyncMock(return_value=existing)
    store._client.create_collection = AsyncMock()
    store._client.upsert = AsyncMock()
    store._embeddings.aembed_documents = AsyncMock(return_value=[[0.1, 0.2]])

    doc = Document(page_content="Text", metadata={})
    await store.upsert([doc], "existing_col")

    store._client.create_collection.assert_not_called()
    store._client.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# search — maps payload to Document correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_maps_payload_to_documents():
    store = _make_store()
    hit = _scored_point("Some content", "History")
    store._client.search = AsyncMock(return_value=[hit])

    docs = await store.search(query_vector=[0.1, 0.2], collection="col1", k=3)

    assert len(docs) == 1
    assert docs[0].page_content == "Some content"
    assert docs[0].metadata["section_title"] == "History"


# ---------------------------------------------------------------------------
# search — returns empty list when no results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_returns_empty_list_when_no_results():
    store = _make_store()
    store._client.search = AsyncMock(return_value=[])

    docs = await store.search(query_vector=[0.0], collection="col1", k=4)
    assert docs == []


# ---------------------------------------------------------------------------
# delete_collection — delegates to client
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_collection_calls_client():
    store = _make_store()
    store._client.delete_collection = AsyncMock()

    await store.delete_collection("my_col")
    store._client.delete_collection.assert_called_once_with(collection_name="my_col")


# ---------------------------------------------------------------------------
# delete_collection — silently ignores errors (collection absent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_collection_ignores_exception():
    store = _make_store()
    store._client.delete_collection = AsyncMock(side_effect=Exception("not found"))

    # Should not raise
    await store.delete_collection("ghost_col")


# ---------------------------------------------------------------------------
# embed_query — prepends retrieval prefix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_query_prepends_retrieval_prefix():
    captured: list[str] = []

    async def fake_embed(text: str) -> list[float]:
        captured.append(text)
        return [0.1, 0.2, 0.3]

    with patch("app.rag.retriever.OllamaEmbeddings") as MockEmbed:
        instance = MockEmbed.return_value
        instance.aembed_query = AsyncMock(side_effect=fake_embed)

        result = await embed_query("What is RAG?", "mxbai-embed-large", "http://localhost:11434")

    assert len(captured) == 1
    assert captured[0].startswith(MXBAI_RETRIEVAL_PREFIX)
    assert "What is RAG?" in captured[0]
    assert result == [0.1, 0.2, 0.3]
