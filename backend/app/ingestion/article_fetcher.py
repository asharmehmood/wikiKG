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

# Wikipedia REST API base
_API_BASE = "https://en.wikipedia.org/api/rest_v1"

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


def _cleaned_text_from_sections(sections: list[dict]) -> tuple[str, list[str]]:
    """Return (full_cleaned_text, section_title_list) from mobile-sections payload."""
    parts: list[str] = []
    titles: list[str] = []
    for section in sections:
        heading = section.get("line", "Introduction")
        body_html = section.get("text", "")
        body = _strip_html(body_html).strip()
        if body:
            parts.append(f"{heading}\n{body}")
            titles.append(heading)
    return "\n\n".join(parts), titles


# ── Public function ───────────────────────────────────────────────────────────

async def fetch_article(url: str) -> ArticleData:
    """Validate *url*, fetch the Wikipedia article, and return cleaned text.

    Raises:
        ValidationError      — URL fails the allowlist.
        DisambiguationError  — URL is a disambiguation page.
        FetchError           — HTTP error (404, timeout, network failure).
        EmptyArticleError    — Cleaned text is shorter than MIN_ARTICLE_CHARS.
    """
    title = _validate_url(url)
    logger.info("Fetching article", extra={"title": title})

    headers = _build_headers()

    async with httpx.AsyncClient(
        follow_redirects=False,  # SSRF mitigation — must stay False
        timeout=_TIMEOUT,
        headers=headers,
    ) as client:
        # ── Sections (main body) ──────────────────────────────────────────
        sections_url = f"{_API_BASE}/page/mobile-sections/{title}"
        try:
            resp = await client.get(sections_url)
        except httpx.RequestError as exc:
            raise FetchError(f"Network error fetching {sections_url!r}: {exc}") from exc

        if resp.status_code == 302:
            raise FetchError(
                f"Wikipedia redirected {title!r} — possible page move. "
                "Re-submit with the canonical URL."
            )
        if resp.status_code == 404:
            raise FetchError(f"Wikipedia article not found: {title!r}")
        if resp.status_code != 200:
            raise FetchError(
                f"Wikipedia API returned {resp.status_code} for {title!r}"
            )

        payload = resp.json()
        # mobile-sections: {"lead": {...}, "remaining": {"sections": [...]}}
        lead_section = payload.get("lead", {})
        remaining_sections = payload.get("remaining", {}).get("sections", [])

        # Prepend the lead section (index 0) as "Introduction"
        all_sections = [
            {"line": lead_section.get("displaytitle", title), "text": lead_section.get("sections", [{}])[0].get("text", "")}
        ] + remaining_sections

        cleaned_text, section_titles = _cleaned_text_from_sections(all_sections)

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
