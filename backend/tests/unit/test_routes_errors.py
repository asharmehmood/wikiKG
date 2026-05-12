"""Targeted tests for routes.py error-handling branches and logging.py.

Covers:
  - /api/ingest route: FetchError → 503, httpx.ConnectError → 503, generic → 500
  - configure_logging idempotency
  - _RequestIdFilter populates request_id field

These are pure unit tests — no real network or DB required.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.ingestion.article_fetcher import FetchError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_client(mock_store, mock_llm) -> AsyncClient:
    """Return an AsyncClient with mocked store + LLM."""
    import app.api.routes as routes_module
    from app.main import create_app

    application = create_app()
    routes_module._make_store = lambda: mock_store  # type: ignore[assignment]
    routes_module._make_llm = lambda: mock_llm  # type: ignore[assignment]
    return AsyncClient(transport=ASGITransport(app=application), base_url="http://test")


# ---------------------------------------------------------------------------
# Routes error-handling branches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_fetch_error_returns_503(in_memory_store, mock_llm):
    """FetchError (e.g. Wikipedia 404) → HTTP 503."""
    import app.api.routes as routes_module
    from app.main import create_app

    original_make_store = routes_module._make_store
    original_make_llm = routes_module._make_llm
    routes_module._make_store = lambda: in_memory_store  # type: ignore[assignment]
    routes_module._make_llm = lambda: mock_llm  # type: ignore[assignment]

    with patch(
        "app.api.routes.run_ingestion",
        new=AsyncMock(side_effect=FetchError("Wikipedia returned 404")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/ingest",
                json={"url": "https://en.wikipedia.org/wiki/Some_Article"},
            )
    routes_module._make_store = original_make_store
    routes_module._make_llm = original_make_llm

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ingest_connect_error_returns_503(in_memory_store, mock_llm):
    """httpx.ConnectError (Ollama down) → HTTP 503."""
    import app.api.routes as routes_module
    from app.main import create_app

    original_make_store = routes_module._make_store
    original_make_llm = routes_module._make_llm
    routes_module._make_store = lambda: in_memory_store  # type: ignore[assignment]
    routes_module._make_llm = lambda: mock_llm  # type: ignore[assignment]

    with patch(
        "app.api.routes.run_ingestion",
        new=AsyncMock(side_effect=httpx.ConnectError("connection refused")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/ingest",
                json={"url": "https://en.wikipedia.org/wiki/Some_Article"},
            )

    routes_module._make_store = original_make_store
    routes_module._make_llm = original_make_llm

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ingest_unexpected_error_returns_500(in_memory_store, mock_llm):
    """Unexpected exception → HTTP 500."""
    import app.api.routes as routes_module
    from app.main import create_app

    original_make_store = routes_module._make_store
    original_make_llm = routes_module._make_llm
    routes_module._make_store = lambda: in_memory_store  # type: ignore[assignment]
    routes_module._make_llm = lambda: mock_llm  # type: ignore[assignment]

    with patch(
        "app.api.routes.run_ingestion",
        new=AsyncMock(side_effect=RuntimeError("unexpected boom")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/ingest",
                json={"url": "https://en.wikipedia.org/wiki/Some_Article"},
            )

    routes_module._make_store = original_make_store
    routes_module._make_llm = original_make_llm

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# configure_logging idempotency
# ---------------------------------------------------------------------------

def test_configure_logging_idempotent():
    """Calling configure_logging twice must not add duplicate handlers."""
    from app.core.logging import configure_logging

    root = logging.getLogger()
    count_before = len(root.handlers)

    # Fresh call (may add handlers if none exist, or no-op)
    configure_logging("INFO")
    configure_logging("DEBUG")  # second call — must be a no-op

    # Handler count must not have increased by more than 1 total
    assert len(root.handlers) <= count_before + 1


# ---------------------------------------------------------------------------
# _RequestIdFilter injects request_id into log records
# ---------------------------------------------------------------------------

def test_request_id_filter_injects_field():
    from app.core.logging import _RequestIdFilter, request_id_var

    filt = _RequestIdFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    token = request_id_var.set("test-uuid-1234")
    try:
        filt.filter(record)
    finally:
        request_id_var.reset(token)

    assert record.request_id == "test-uuid-1234"  # type: ignore[attr-defined]
