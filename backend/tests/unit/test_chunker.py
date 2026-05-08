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

# T-20: implement test cases
