"""Unit tests for api/schemas.py.

Test cases (T-22):
  - IngestRequest rejects non-HTTP schemes (ftp://, file://, etc.)
  - IngestRequest accepts valid Wikipedia HttpUrl
  - ChatRequest rejects history with invalid role values
  - ChatMessage round-trips through model_dump / model_validate
  - history defaults to empty list when omitted from ChatRequest

Implemented in: T-22
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.schemas import ChatMessage, ChatRequest, IngestRequest

# T-22: implement test cases
