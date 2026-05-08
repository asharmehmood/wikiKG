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

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["wikiKG"])

# T-17: implement POST /api/ingest and POST /api/chat
