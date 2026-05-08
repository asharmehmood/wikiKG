"""LangGraph IngestionGraph state machine.

Node sequence:
    validate_url → fetch_article → chunk → delete_old_collection
    → embed_store → summarise → done

Conditional edges:
    validate_url  — raises ValidationError / DisambiguationError (caught in routes.py)
    fetch_article — raises FetchError / EmptyArticleError (caught in routes.py)

The graph propagates errors by re-raising from node functions; LangGraph
surfaces them to the caller of ainvoke() so routes.py can map them to HTTP codes.

Public API:
    ingestion_graph   — compiled LangGraph; call with ainvoke({"url": url})
    run_ingestion(url, store, llm, settings) -> IngestionState
"""
from __future__ import annotations

import hashlib
from typing import TypedDict

from langchain_core.documents import Document
from langgraph.graph import END, StateGraph

from app.core.interfaces import LLMInterface, VectorStoreInterface
from app.core.logging import get_logger
from app.ingestion.article_fetcher import fetch_article
from app.ingestion.chunker import chunk_article
from app.rag.summariser import summarise

logger = get_logger(__name__)


# ── State ────────────────────────────────────────────────────────────────────

class IngestionState(TypedDict, total=False):
    url: str
    cleaned_text: str
    article_title: str
    sections: list[str]
    chunks: list[Document]
    collection_id: str
    summary: str
    chunk_count: int
    # Injected dependencies (not serialised — passed via closure over builder)
    _store: VectorStoreInterface
    _llm: LLMInterface


# ── Node functions ────────────────────────────────────────────────────────────

async def _node_fetch(state: IngestionState) -> IngestionState:
    article = await fetch_article(state["url"])
    return {
        **state,
        "cleaned_text": article.cleaned_text,
        "article_title": article.title,
        "sections": article.sections,
    }


async def _node_chunk(state: IngestionState) -> IngestionState:
    chunks = chunk_article(
        cleaned_text=state["cleaned_text"],
        source_url=state["url"],
        article_title=state["article_title"],
    )
    collection_id = hashlib.md5(state["url"].encode()).hexdigest()
    return {**state, "chunks": chunks, "collection_id": collection_id}


async def _node_delete_old(state: IngestionState) -> IngestionState:
    store: VectorStoreInterface = state["_store"]
    await store.delete_collection(state["collection_id"])
    logger.info("Old collection deleted", extra={"collection_id": state["collection_id"]})
    return state


async def _node_embed_store(state: IngestionState) -> IngestionState:
    store: VectorStoreInterface = state["_store"]
    await store.upsert(state["chunks"], state["collection_id"])
    logger.info(
        "Chunks stored",
        extra={"collection_id": state["collection_id"], "count": len(state["chunks"])},
    )
    return {**state, "chunk_count": len(state["chunks"])}


async def _node_summarise(state: IngestionState) -> IngestionState:
    llm: LLMInterface = state["_llm"]
    summary = await summarise(state["cleaned_text"], llm)
    return {**state, "summary": summary}


# ── Graph builder ─────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    g = StateGraph(IngestionState)
    g.add_node("fetch_article",       _node_fetch)
    g.add_node("chunk",               _node_chunk)
    g.add_node("delete_old_collection", _node_delete_old)
    g.add_node("embed_store",         _node_embed_store)
    g.add_node("summarise",           _node_summarise)

    g.set_entry_point("fetch_article")
    g.add_edge("fetch_article",       "chunk")
    g.add_edge("chunk",               "delete_old_collection")
    g.add_edge("delete_old_collection", "embed_store")
    g.add_edge("embed_store",         "summarise")
    g.add_edge("summarise",           END)
    return g


ingestion_graph = _build_graph().compile()


# ── Convenience wrapper (used by routes.py) ───────────────────────────────────

async def run_ingestion(
    url: str,
    store: VectorStoreInterface,
    llm: LLMInterface,
) -> IngestionState:
    """Run the full ingestion pipeline and return the final state."""
    initial: IngestionState = {"url": url, "_store": store, "_llm": llm}
    result: IngestionState = await ingestion_graph.ainvoke(initial)
    return result
