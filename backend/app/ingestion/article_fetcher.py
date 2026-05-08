"""Fetch and clean a Wikipedia article via the REST API.

Public API:
    fetch_article(url: str) -> ArticleData

Security constraints (must not be softened):
  - URL validated against regex allowlist BEFORE any HTTP call (SSRF)
  - httpx configured with follow_redirects=False (SSRF mitigation)
  - User-Agent header set on every request (Wikimedia ToS / NFR-11)

Error hierarchy (must match exception handlers in routes.py):
  WikipediaError
    ├─ ValidationError        URL did not pass the allowlist
    ├─ DisambiguationError    URL points to a disambiguation page
    ├─ EmptyArticleError      Cleaned text shorter than MIN_ARTICLE_CHARS
    └─ FetchError             HTTP error (404, timeout, etc.)

Implemented in: T-09
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Minimum cleaned-text length before we abort (FR-5, DESIGN.md §4)
MIN_ARTICLE_CHARS = 200

# Regex allowlist applied before every HTTP call (NFR-5, DESIGN.md §4)
WIKIPEDIA_URL_PATTERN = r"^https?://([\w-]+\.)?wikipedia\.org/wiki/[^\s]+$"


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class WikipediaError(Exception):
    """Base class for all article-fetcher errors."""


class ValidationError(WikipediaError):
    """URL did not pass the allowlist check."""


class DisambiguationError(WikipediaError):
    """URL points to a Wikipedia disambiguation page."""


class EmptyArticleError(WikipediaError):
    """Cleaned article text is shorter than MIN_ARTICLE_CHARS."""


class FetchError(WikipediaError):
    """HTTP error while fetching the article (e.g. 404, timeout)."""


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class ArticleData:
    title: str
    cleaned_text: str
    sections: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

async def fetch_article(url: str) -> ArticleData:
    """Validate *url*, fetch the Wikipedia article, and return cleaned text.

    Raises ValidationError, DisambiguationError, EmptyArticleError, or
    FetchError on failure.
    """
    raise NotImplementedError("Implemented in T-09")
