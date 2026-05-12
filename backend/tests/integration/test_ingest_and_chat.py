"""Integration tests — full pipeline with mocked I/O.

Ollama is replaced by MockLLM + InMemoryStore (from conftest.py).
Wikipedia HTTP calls are intercepted by respx.
No live Qdrant, Ollama, or network access required.

Test cases (T-23):
  - POST /api/ingest (valid URL)     → 200, IngestResponse with chunk_count > 0
  - POST /api/chat  (valid id)       → 200, SSE ends with {"done": true}
  - POST /api/ingest (same URL ×2)   → idempotent; second call also succeeds
  - POST /api/ingest (non-Wikipedia) → 422
  - POST /api/chat  (unknown id)     → 404

Implemented in: T-23
"""
from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient

from tests.conftest import InMemoryStore, MockLLM

_WIKI_URL = "https://en.wikipedia.org/wiki/Retrieval-augmented_generation"
_ARTICLE_TITLE = "Retrieval-augmented_generation"
_SECTIONS_URL = f"https://en.wikipedia.org/api/rest_v1/page/mobile-sections/{_ARTICLE_TITLE}"
_COLLECTION_ID = hashlib.md5(_WIKI_URL.encode()).hexdigest()

@pytest.fixture(autouse=True)
def patch_ollama_embeddings(monkeypatch):
    """Prevent any OllamaEmbeddings call from hitting a real Ollama server."""
    from unittest.mock import AsyncMock, MagicMock
    import langchain_ollama.embeddings as emb_module

    async def _fake_aembed_documents(self, texts):
        return [[0.0] * 1024 for _ in texts]

    async def _fake_aembed_query(self, text):
        return [0.0] * 1024

    monkeypatch.setattr(emb_module.OllamaEmbeddings, "aembed_documents", _fake_aembed_documents)
    monkeypatch.setattr(emb_module.OllamaEmbeddings, "aembed_query", _fake_aembed_query)


_GOOD_PAYLOAD = {
    "lead": {
        "displaytitle": "Retrieval-augmented generation",
        "sections": [{"text": "<p>" + ("RAG is a technique that augments LLMs. " * 30) + "</p>"}],
    },
    "remaining": {
        "sections": [
            {"line": "History", "text": "<p>" + ("Early research on retrieval. " * 30) + "</p>"},
            {"line": "Applications", "text": "<p>" + ("Used in chatbots and search. " * 30) + "</p>"},
        ]
    },
}


@pytest_asyncio.fixture
async def client(mock_llm: MockLLM, in_memory_store: InMemoryStore):
    """FastAPI test client with mocked store + LLM, Wikipedia HTTP mocked by respx."""
    import app.api.routes as routes_module
    from app.main import create_app

    application = create_app()
    original_make_store = routes_module._make_store
    original_make_llm = routes_module._make_llm

    routes_module._make_store = lambda: in_memory_store  # type: ignore[assignment]
    routes_module._make_llm = lambda: mock_llm  # type: ignore[assignment]

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as c:
        yield c

    routes_module._make_store = original_make_store
    routes_module._make_llm = original_make_llm


# ---------------------------------------------------------------------------
# T-23.1 — POST /api/ingest (valid URL) → 200, IngestResponse
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_ingest_valid_url_returns_200(client: AsyncClient):
    respx.get(_SECTIONS_URL).mock(return_value=httpx.Response(200, json=_GOOD_PAYLOAD))

    resp = await client.post("/api/ingest", json={"url": _WIKI_URL})
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunk_count"] > 0
    assert body["collection_id"] == _COLLECTION_ID
    assert body["article_title"] != ""
    assert body["summary"] == MockLLM.FIXED_ANSWER


# ---------------------------------------------------------------------------
# T-23.2 — POST /api/chat (valid collection_id) → 200, SSE with done event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_valid_collection_streams_sse(
    client: AsyncClient, in_memory_store: InMemoryStore
):
    # Pre-populate a collection so /api/chat finds it
    from langchain_core.documents import Document
    await in_memory_store.upsert(
        [Document(page_content="RAG content.", metadata={"source_url": _WIKI_URL, "section_title": "Intro"})],
        _COLLECTION_ID,
    )

    mock_qdrant_client = AsyncMock()
    mock_qdrant_client.get_collection = AsyncMock(return_value=MagicMock())
    mock_qdrant_client.close = AsyncMock()

    # embed_query touches Ollama — replace with a zero vector
    async def _fake_embed(question, embed_model, ollama_host):
        return [0.0] * 1024

    with (
        patch("app.api.routes.AsyncQdrantClient", return_value=mock_qdrant_client),
        patch("app.rag.graph.embed_query", side_effect=_fake_embed),
    ):
        async with client.stream(
            "POST",
            "/api/chat",
            json={"question": "What is RAG?", "collection_id": _COLLECTION_ID},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            events = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

    assert events, "No SSE events received"
    done_events = [e for e in events if e.get("done") is True]
    assert done_events, "No done event received in SSE stream"


# ---------------------------------------------------------------------------
# T-23.3 — POST /api/ingest same URL twice → idempotent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_ingest_idempotent(client: AsyncClient):
    respx.get(_SECTIONS_URL).mock(return_value=httpx.Response(200, json=_GOOD_PAYLOAD))
    resp1 = await client.post("/api/ingest", json={"url": _WIKI_URL})
    assert resp1.status_code == 200
    count1 = resp1.json()["chunk_count"]

    respx.get(_SECTIONS_URL).mock(return_value=httpx.Response(200, json=_GOOD_PAYLOAD))
    resp2 = await client.post("/api/ingest", json={"url": _WIKI_URL})
    assert resp2.status_code == 200
    count2 = resp2.json()["chunk_count"]

    assert count1 == count2, "Chunk count should be identical on re-ingestion"


# ---------------------------------------------------------------------------
# T-23.4 — POST /api/ingest (non-Wikipedia URL) → 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_non_wikipedia_url_returns_422(client: AsyncClient):
    resp = await client.post("/api/ingest", json={"url": "https://example.com/wiki/Test"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# T-23.5 — POST /api/chat (unknown collection_id) → 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_unknown_collection_returns_404(client: AsyncClient):
    from qdrant_client.http.exceptions import UnexpectedResponse

    mock_qdrant_client = AsyncMock()
    mock_qdrant_client.get_collection = AsyncMock(
        side_effect=UnexpectedResponse(
            status_code=404, reason_phrase="Not Found", content=b"", headers={}
        )
    )
    mock_qdrant_client.close = AsyncMock()

    with patch("app.api.routes.AsyncQdrantClient", return_value=mock_qdrant_client):
        resp = await client.post(
            "/api/chat",
            json={"question": "What is this?", "collection_id": "unknown_collection_id"},
        )
    assert resp.status_code == 404
