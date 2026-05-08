"""Thin wrapper around RecursiveCharacterTextSplitter.

Public API:
    chunk_article(cleaned_text, source_url, article_title) -> list[Document]

Chunk parameters (DESIGN.md §4 / FR-3):
    chunk_size    = 1500 chars  (~400 tokens)
    chunk_overlap = 200  chars  (~50 tokens)
    separators    = ["\\n\\n", "\\n", ". ", " "]

Each returned Document carries metadata:
    source_url, article_title, section_title, chunk_index

Implemented in: T-10
"""
from __future__ import annotations

from langchain_core.documents import Document

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
SEPARATORS = ["\n\n", "\n", ". ", " "]


def chunk_article(
    cleaned_text: str,
    source_url: str,
    article_title: str,
) -> list[Document]:
    """Split *cleaned_text* into overlapping chunks with metadata attached.

    Returns an empty list when *cleaned_text* is empty or blank.
    """
    raise NotImplementedError("Implemented in T-10")
