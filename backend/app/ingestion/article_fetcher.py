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
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

# Minimum cleaned-text length before we abort (FR-5, DESIGN.md §4)
MIN_ARTICLE_CHARS = 200

# Regex allowlist applied before every HTTP call (NFR-5, DESIGN.md §4)
# Hand-reviewed — do not relax this pattern.
WIKIPEDIA_URL_PATTERN = re.compile(
    r"^https?://([\w-]+\.)?wikipedia\.org/wiki/[^\s]+$"
)

# Wikimedia ToS requires a descriptive User-Agent (NFR-11)
USER_AGENT = "wikiKG/0.1 (RAG demo; github.com/wikikg) python-httpx"

# Wikipedia MediaWiki API base (replaces the decommissioned mobile-sections endpoint)
_MEDIAWIKI_API = "https://en.wikipedia.org/w/api.php"

# HTTP timeout for all Wikipedia requests
_TIMEOUT = httpx.Timeout(30.0)


# ── Exception hierarchy ───────────────────────────────────────────────────────

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


# ── Data container ────────────────────────────────────────────────────────────

@dataclass
class ArticleData:
    title: str
    cleaned_text: str
    sections: list[str] = field(default_factory=list)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _validate_url(url: str) -> str:
    """Return the article title extracted from *url* or raise ValidationError."""
    if not WIKIPEDIA_URL_PATTERN.match(url):
        raise ValidationError(f"URL is not a valid Wikipedia article URL: {url!r}")
    path = urlparse(url).path  # e.g. /wiki/Retrieval-augmented_generation
    title = unquote(path.split("/wiki/", 1)[1])
    if "_(disambiguation)" in title:
        raise DisambiguationError(
            f"URL points to a disambiguation page: {title!r}"
        )
    return title


def _strip_html(html: str) -> str:
    """Return plain text with HTML tags removed."""
    return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)


def _build_headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _split_sections(extract: str) -> tuple[str, list[str]]:
    """Split a MediaWiki plain-text extract into (cleaned_text, section_titles).

    The MediaWiki API with exsectionformat=wiki embeds section headings as
    '== Heading ==' lines inside the extract text.
    """
    # Split on any level of heading (==, ===, ====, …)
    parts_raw = re.split(r"\n(==+\s*.+?\s*==+)\n", extract)

    parts: list[str] = []
    titles: list[str] = []

    # parts_raw = [intro_body, "== H1 ==", h1_body, "== H2 ==", h2_body, …]
    intro = parts_raw[0].strip()
    if intro:
        parts.append(f"Introduction\n{intro}")
        titles.append("Introduction")

    for i in range(1, len(parts_raw), 2):
        heading_raw = parts_raw[i]
        body = parts_raw[i + 1].strip() if i + 1 < len(parts_raw) else ""
        # Strip the == markers to get a clean heading string
        heading = re.sub(r"^=+\s*|\s*=+$", "", heading_raw).strip()
        if body:
            parts.append(f"{heading}\n{body}")
            titles.append(heading)

    return "\n\n".join(parts), titles


# ── Public function ───────────────────────────────────────────────────────────

async def fetch_article(url: str) -> ArticleData:
    """Validate *url*, fetch the Wikipedia article, and return cleaned text.

    Uses the MediaWiki action=query&prop=extracts API (the mobile-sections
    endpoint was decommissioned in 2024 per T328036).

    Raises:
        ValidationError      — URL fails the allowlist.
        DisambiguationError  — URL is a disambiguation page.
        FetchError           — HTTP error (404, timeout, network failure).
        EmptyArticleError    — Cleaned text is shorter than MIN_ARTICLE_CHARS.
    """
    title = _validate_url(url)
    logger.info("Fetching article", extra={"title": title})

    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": "1",        # Return plain text, not HTML
        "exsectionformat": "wiki", # Embed section headings as == Heading ==
        "format": "json",
        "formatversion": "2",
        "redirects": "1",          # Follow Wikipedia redirects automatically
    }

    async with httpx.AsyncClient(
        follow_redirects=False,  # SSRF mitigation — must stay False (applies to our requests, not wiki redirects handled server-side)
        timeout=_TIMEOUT,
        headers=_build_headers(),
    ) as client:
        try:
            resp = await client.get(_MEDIAWIKI_API, params=params)
        except httpx.RequestError as exc:
            raise FetchError(f"Network error fetching article {title!r}: {exc}") from exc

        if resp.status_code != 200:
            raise FetchError(
                f"MediaWiki API returned {resp.status_code} for {title!r}"
            )

    data = resp.json()
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        raise FetchError(f"No page data returned for {title!r}")

    page = pages[0]
    if page.get("missing"):
        raise FetchError(f"Wikipedia article not found: {title!r}")

    extract: str = page.get("extract", "")
    cleaned_text, section_titles = _split_sections(extract)

    if len(cleaned_text) < MIN_ARTICLE_CHARS:
        raise EmptyArticleError(
            f"Article {title!r} produced only {len(cleaned_text)} characters of "
            f"cleaned text (minimum {MIN_ARTICLE_CHARS})."
        )

    logger.info(
        "Article fetched",
        extra={"title": title, "chars": len(cleaned_text), "sections": len(section_titles)},
    )
    return ArticleData(title=title, cleaned_text=cleaned_text, sections=section_titles)
