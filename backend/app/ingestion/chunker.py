"""Thin wrapper around RecursiveCharacterTextSplitter.

Public API:
    chunk_article(cleaned_text, source_url, article_title) -> list[Document]

Chunk parameters (DESIGN.md §4 / FR-3):
    chunk_size    = 1500 chars  (~400 tokens)
    chunk_overlap = 200  chars  (~50 tokens)
    separators    = ["\\n\\n", "\\n", ". ", " "]

Each returned Document carries metadata:
    source_url, article_title, section_title (inferred from heading lines), chunk_index
"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.logging import get_logger

logger = get_logger(__name__)

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
SEPARATORS = ["\n\n", "\n", ". ", " "]

# Heading detection: lines whose next character is a newline and look like a
# section heading (short, no trailing period). Used to annotate chunk metadata.
_MAX_HEADING_LEN = 80


def _infer_section(chunk_text: str, headings: list[str]) -> str:
    """Return the last heading that appears before the chunk's first word."""
    first_line = chunk_text.split("\n", 1)[0].strip()
    # Walk backwards through known headings to find the closest preceding one
    best = headings[0] if headings else "Introduction"
    for h in headings:
        if h in chunk_text:
            best = h
            break
    return best


def chunk_article(
    cleaned_text: str,
    source_url: str,
    article_title: str,
) -> list[Document]:
    """Split *cleaned_text* into overlapping chunks with metadata attached.

    Returns an empty list when *cleaned_text* is empty or blank.
    """
    if not cleaned_text or not cleaned_text.strip():
        return []

    # Extract section headings (lines followed by body text separated by \\n)
    headings: list[str] = []
    for line in cleaned_text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped) <= _MAX_HEADING_LEN and not stripped.endswith("."):
            headings.append(stripped)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS,
    )

    raw_chunks: list[str] = splitter.split_text(cleaned_text)

    documents: list[Document] = []
    for idx, text in enumerate(raw_chunks):
        section_title = _infer_section(text, headings)
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "source_url": source_url,
                    "article_title": article_title,
                    "section_title": section_title,
                    "chunk_index": idx,
                },
            )
        )

    logger.debug(
        "Article chunked",
        extra={"chunks": len(documents), "article": article_title},
    )
    return documents
