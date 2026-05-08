"""Integration tests — full pipeline against a real Qdrant instance.

Ollama is replaced by MockLLM + MockEmbedder via FastAPI dependency_overrides.
Qdrant runs as a real Docker container (pytest-docker fixture from conftest.py).

Test cases (T-23):
  - POST /api/ingest (valid URL)     → 200, IngestResponse with chunk_count > 0
  - POST /api/chat  (valid id)       → 200, SSE ends with {"done": true, "sources": […]}
  - POST /api/ingest (same URL ×2)   → idempotent; chunk_count matches on second call
  - POST /api/ingest (non-Wikipedia) → 422
  - POST /api/chat  (unknown id)     → 404

Implemented in: T-23
"""
from __future__ import annotations

import pytest

# T-23: implement test cases
