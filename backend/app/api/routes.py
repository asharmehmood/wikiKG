"""FastAPI route handlers.

POST /api/ingest  — validate URL, run IngestionGraph, return IngestResponse
POST /api/chat    — validate collection_id, run RagGraph, stream SSE tokens

SSE event format (must match frontend api.js parser exactly):
  data: {"token": "…"}\\n\\n
  data: {"done": true, "sources": ["Section A", "…"]}\\n\\n

HTTP error mapping (FR-5):
  ValidationError / DisambiguationError / EmptyArticleError → 422
  Ollama unavailable                                        → 503
  Qdrant unavailable                                        → 503
  Unknown collection_id                                     → 404

Implemented in: T-17
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import BaseMessage
from langchain_ollama import ChatOllama
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.api.schemas import ChatRequest, ErrorResponse, IngestRequest, IngestResponse
from app.core.config import get_settings
from app.core.interfaces import LLMInterface
from app.core.logging import get_logger
from app.ingestion.article_fetcher import (
    DisambiguationError,
    EmptyArticleError,
    FetchError,
    ValidationError,
)
from app.ingestion.graph import run_ingestion
from app.rag.graph import prepare_rag
from app.rag.retriever import QdrantStore

router = APIRouter(prefix="/api", tags=["wikiKG"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Concrete LLM adapter (private to this module)
# ---------------------------------------------------------------------------

class _OllamaLLM(LLMInterface):
    """Thin adapter that maps LLMInterface to ChatOllama."""

    def __init__(self, model: str, base_url: str) -> None:
        self._chat = ChatOllama(model=model, base_url=base_url)

    async def generate(self, messages: list[BaseMessage]) -> str:
        response = await self._chat.ainvoke(messages)
        return str(response.content)

    async def stream(self, messages: list[BaseMessage]) -> AsyncIterator[str]:  # type: ignore[override]
        async for chunk in self._chat.astream(messages):
            if chunk.content:
                yield str(chunk.content)


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def _make_store() -> QdrantStore:
    s = get_settings()
    return QdrantStore(
        qdrant_host=s.QDRANT_HOST,
        qdrant_port=s.QDRANT_PORT,
        embed_model=s.EMBED_MODEL,
        ollama_host=s.OLLAMA_HOST,
    )


def _make_llm() -> _OllamaLLM:
    s = get_settings()
    return _OllamaLLM(model=s.GEN_MODEL, base_url=s.OLLAMA_HOST)


# ---------------------------------------------------------------------------
# POST /api/ingest
# ---------------------------------------------------------------------------

@router.post(
    "/ingest",
    response_model=IngestResponse,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def ingest(request: IngestRequest) -> IngestResponse:
    """Fetch, chunk, embed, and summarise a Wikipedia article."""
    url = str(request.url)
    store = _make_store()
    llm = _make_llm()

    try:
        state = await run_ingestion(url=url, store=store, llm=llm)
    except (ValidationError, DisambiguationError, EmptyArticleError) as exc:
        logger.warning("ingest_rejected", extra={"error": str(exc), "url": url})
        raise HTTPException(status_code=422, detail=str(exc))
    except FetchError as exc:
        logger.error("ingest_fetch_error", extra={"error": str(exc), "url": url})
        raise HTTPException(status_code=503, detail=str(exc))
    except httpx.ConnectError as exc:
        logger.error("ingest_ollama_unavailable", extra={"error": str(exc)})
        raise HTTPException(status_code=503, detail="Upstream service unavailable.")
    except Exception as exc:
        logger.exception("ingest_unexpected_error", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Internal server error.")

    return IngestResponse(
        article_title=state["article_title"],
        summary=state["summary"],
        chunk_count=state["chunk_count"],
        collection_id=state["collection_id"],
    )


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    responses={
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def chat(request: ChatRequest) -> StreamingResponse:
    """Stream an SSE response grounded in the ingested Wikipedia article."""
    settings = get_settings()

    # Verify the collection exists before streaming (→ 404 if unknown)
    qdrant_client = AsyncQdrantClient(
        url=f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
    )
    try:
        await qdrant_client.get_collection(request.collection_id)
    except (UnexpectedResponse, Exception) as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{request.collection_id}' not found. Ingest the article first.",
        ) from exc
    finally:
        await qdrant_client.close()

    store = _make_store()
    llm = _make_llm()

    async def _event_generator() -> AsyncIterator[str]:
        try:
            state = await prepare_rag(
                question=request.question,
                collection_id=request.collection_id,
                history=request.history,
                store=store,
                llm=llm,
                embed_model=settings.EMBED_MODEL,
                ollama_host=settings.OLLAMA_HOST,
                top_k=settings.TOP_K,
            )
            retrieved_docs = state.get("retrieved_docs", [])
            sources = list(
                {doc.metadata.get("section_title", "") for doc in retrieved_docs}
                - {""}
            )
            async for token in llm.stream(state["messages"]):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            logger.exception("chat_stream_error", extra={"error": str(exc)})
            yield f"data: {json.dumps({'error': 'Stream error. Please retry.'})}\n\n"
            return

        yield f"data: {json.dumps({'done': True, 'sources': sources})}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
