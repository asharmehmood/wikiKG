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

Implemented in: T-19
"""
from __future__ import annotations

import pytest

# T-19: implement test cases using respx or httpx.MockTransport
