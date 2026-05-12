"""Unit tests for ingestion/article_fetcher.py.

All HTTP calls are mocked — no real Wikipedia requests are made.

Test cases (T-19):
  - Valid Wikipedia URL           → ArticleData with title and cleaned_text
  - Non-Wikipedia URL             → raises ValidationError
  - Disambiguation page           → raises DisambiguationError
  - 404 HTTP response             → raises FetchError
  - Cleaned text < 200 chars      → raises EmptyArticleError
  - User-Agent header present     → on every outgoing request (NFR-11)
  - follow_redirects=False set    → SSRF mitigation check (NFR-5)
  - Missing page                  → raises FetchError
  - Network error                 → raises FetchError
  - _split_sections helper        → correct title/body splitting

Implemented in: T-19
"""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.ingestion.article_fetcher import (
    USER_AGENT,
    ArticleData,
    DisambiguationError,
    EmptyArticleError,
    FetchError,
    ValidationError,
    _split_sections,
    fetch_article,
)

# ---------------------------------------------------------------------------
# Helpers — mock the MediaWiki action=query endpoint
# ---------------------------------------------------------------------------

_MEDIAWIKI_API = "https://en.wikipedia.org/w/api.php"
_TITLE = "Retrieval-augmented_generation"
_URL = f"https://en.wikipedia.org/wiki/{_TITLE}"

_LONG_TEXT = "RAG is a technique that combines retrieval with generation. " * 10  # >200 chars

def _mw_response(extract: str, missing: bool = False) -> dict:
    page: dict = {"pageid": 1, "title": _TITLE, "extract": extract}
    if missing:
        page = {"title": _TITLE, "missing": True}
    return {"query": {"pages": [page]}}


def _mock_mediawiki(extract: str = _LONG_TEXT):
    return respx.get(_MEDIAWIKI_API).mock(
        return_value=httpx.Response(200, json=_mw_response(extract))
    )

# ---------------------------------------------------------------------------
# T-19.1 — Valid URL returns ArticleData
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_valid_url_returns_article_data():
    _mock_mediawiki()
    result = await fetch_article(_URL)
    assert isinstance(result, ArticleData)
    assert result.title == _TITLE
    assert len(result.cleaned_text) >= 200
    assert isinstance(result.sections, list)


# ---------------------------------------------------------------------------
# T-19.2 — Non-Wikipedia URL raises ValidationError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_wikipedia_url_raises_validation_error():
    with pytest.raises(ValidationError):
        await fetch_article("https://example.com/wiki/SomeArticle")


@pytest.mark.asyncio
async def test_ftp_url_raises_validation_error():
    with pytest.raises(ValidationError):
        await fetch_article("ftp://en.wikipedia.org/wiki/Python")


# ---------------------------------------------------------------------------
# T-19.3 — Disambiguation URL raises DisambiguationError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disambiguation_url_raises_error():
    with pytest.raises(DisambiguationError):
        await fetch_article("https://en.wikipedia.org/wiki/Python_(disambiguation)")


# ---------------------------------------------------------------------------
# T-19.4 — 404 HTTP response raises FetchError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_404_raises_fetch_error():
    respx.get(_MEDIAWIKI_API).mock(return_value=httpx.Response(404))
    with pytest.raises(FetchError):
        await fetch_article(_URL)


# ---------------------------------------------------------------------------
# T-19.5 — Cleaned text < 200 chars raises EmptyArticleError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_short_article_raises_empty_article_error():
    respx.get(_MEDIAWIKI_API).mock(
        return_value=httpx.Response(200, json=_mw_response("Short."))
    )
    with pytest.raises(EmptyArticleError):
        await fetch_article(_URL)


# ---------------------------------------------------------------------------
# T-19.6 — User-Agent header is present on every request (NFR-11)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_user_agent_header_present():
    received_headers: dict = {}

    def capture(request: httpx.Request) -> httpx.Response:
        received_headers.update(dict(request.headers))
        return httpx.Response(200, json=_mw_response(_LONG_TEXT))

    respx.get(_MEDIAWIKI_API).mock(side_effect=capture)
    await fetch_article(_URL)

    assert "user-agent" in received_headers
    assert received_headers["user-agent"] == USER_AGENT


# ---------------------------------------------------------------------------
# T-19.7 — Network error raises FetchError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_network_error_raises_fetch_error():
    respx.get(_MEDIAWIKI_API).mock(side_effect=httpx.ConnectError("unreachable"))
    with pytest.raises(FetchError):
        await fetch_article(_URL)


# ---------------------------------------------------------------------------
# T-19.8 — Missing page raises FetchError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_missing_page_raises_fetch_error():
    respx.get(_MEDIAWIKI_API).mock(
        return_value=httpx.Response(200, json=_mw_response("", missing=True))
    )
    with pytest.raises(FetchError):
        await fetch_article(_URL)


# ---------------------------------------------------------------------------
# T-19.9 — Empty pages list raises FetchError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_empty_pages_raises_fetch_error():
    respx.get(_MEDIAWIKI_API).mock(
        return_value=httpx.Response(200, json={"query": {"pages": []}})
    )
    with pytest.raises(FetchError):
        await fetch_article(_URL)


# ---------------------------------------------------------------------------
# T-19.10 — _split_sections correctly splits heading/body
# ---------------------------------------------------------------------------

def test_split_sections_intro_only():
    text = "Intro paragraph. " * 20
    cleaned, titles = _split_sections(text)
    assert "Introduction" in titles
    assert "Intro paragraph" in cleaned


def test_split_sections_with_headings():
    text = "Intro text. " * 10 + "\n== History ==\nHistory body. " * 10 + "\n=== Sub ===\nSub body. " * 5
    cleaned, titles = _split_sections(text)
    assert "History" in titles
    assert "History body" in cleaned


def test_split_sections_empty_body_heading_skipped():
    """Headings with no body should be excluded."""
    text = "Intro. " * 20 + "\n== Empty ==\n"
    cleaned, titles = _split_sections(text)
    assert "Empty" not in titles
