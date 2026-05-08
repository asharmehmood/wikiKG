"""LangGraph IngestionGraph state machine.

Node sequence:
    validate_url → fetch_article → chunk → delete_old_collection
    → embed_store → summarise → done

Conditional edges:
    validate_url  — abort (ValidationError)  if URL fails allowlist
    fetch_article — abort (EmptyArticleError) if cleaned text < 200 chars

State definition: IngestionState (TypedDict below)

The compiled graph is exported as `ingestion_graph`.
Routes.py calls:  result = await ingestion_graph.ainvoke({"url": url})

Implemented in: T-11
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.documents import Document


class IngestionState(TypedDict, total=False):
    url: str
    cleaned_text: str
    chunks: list[Document]
    collection_id: str
    summary: str
    article_title: str
    chunk_count: int
    error: str | None


# ingestion_graph: CompiledGraph = _build_graph()  — assembled in T-11
