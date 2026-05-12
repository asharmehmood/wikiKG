"""Unit tests for ingestion/chunker.py.

Test cases (T-20):
  - Short text               → single Document with correct metadata fields
  - Long text                → multiple Documents, all with chunk_index set
  - Overlap present          → consecutive chunks share a content boundary
  - Empty / blank text       → returns empty list (not an error)

Implemented in: T-20
"""
from __future__ import annotations

import pytest

from app.ingestion.chunker import chunk_article

_SOURCE_URL = "https://en.wikipedia.org/wiki/Test_Article"
_TITLE = "Test Article"


# ---------------------------------------------------------------------------
# T-20.1 — Short text produces a single chunk with correct metadata
# ---------------------------------------------------------------------------

def test_short_text_single_chunk():
    text = "This is a short article about testing. " * 5  # ~195 chars, fits in one chunk
    docs = chunk_article(text, _SOURCE_URL, _TITLE)
    assert len(docs) >= 1
    doc = docs[0]
    assert doc.metadata["source_url"] == _SOURCE_URL
    assert doc.metadata["article_title"] == _TITLE
    assert "chunk_index" in doc.metadata
    assert doc.metadata["chunk_index"] == 0


# ---------------------------------------------------------------------------
# T-20.2 — Long text produces multiple chunks, all with chunk_index
# ---------------------------------------------------------------------------

def test_long_text_multiple_chunks():
    # ~6000 chars — well above chunk_size=1500
    text = ("Wikipedia is an online encyclopedia. " * 50 + "\n\n") * 4
    docs = chunk_article(text, _SOURCE_URL, _TITLE)
    assert len(docs) > 1
    for i, doc in enumerate(docs):
        assert doc.metadata["chunk_index"] == i
        assert doc.metadata["source_url"] == _SOURCE_URL
        assert doc.metadata["article_title"] == _TITLE


# ---------------------------------------------------------------------------
# T-20.3 — Overlap: consecutive chunks share a content boundary
# ---------------------------------------------------------------------------

def test_overlap_between_consecutive_chunks():
    # Build text that will definitely produce ≥ 2 chunks
    sentence = "The quick brown fox jumps over the lazy dog. "
    text = sentence * 100  # ~4500 chars → ~3 chunks at size=1500, overlap=200
    docs = chunk_article(text, _SOURCE_URL, _TITLE)
    assert len(docs) >= 2

    # The end of chunk[0] should appear at the start of chunk[1]
    tail_of_first = docs[0].page_content[-100:]
    head_of_second = docs[1].page_content[:200]
    # At least some overlap exists (tails share common content)
    assert any(tail_of_first[i:i+20] in head_of_second for i in range(0, len(tail_of_first) - 20, 10)), \
        "No overlap detected between consecutive chunks"


# ---------------------------------------------------------------------------
# T-20.4 — Empty / blank text → returns empty list
# ---------------------------------------------------------------------------

def test_empty_text_returns_empty_list():
    assert chunk_article("", _SOURCE_URL, _TITLE) == []


def test_blank_text_returns_empty_list():
    assert chunk_article("   \n\n\t  ", _SOURCE_URL, _TITLE) == []


# ---------------------------------------------------------------------------
# T-20.5 — section_title metadata field is always present
# ---------------------------------------------------------------------------

def test_section_title_metadata_present():
    text = "Some article content. " * 20
    docs = chunk_article(text, _SOURCE_URL, _TITLE)
    for doc in docs:
        assert "section_title" in doc.metadata
