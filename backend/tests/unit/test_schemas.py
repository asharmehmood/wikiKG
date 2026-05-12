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


# ---------------------------------------------------------------------------
# T-22.1 — IngestRequest accepts a valid Wikipedia URL
# ---------------------------------------------------------------------------

def test_ingest_request_valid_url():
    req = IngestRequest(url="https://en.wikipedia.org/wiki/Python_(programming_language)")
    assert req.url is not None


# ---------------------------------------------------------------------------
# T-22.2 — IngestRequest rejects non-HTTP schemes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_url", [
    "ftp://en.wikipedia.org/wiki/Python",
    "file:///etc/passwd",
    "javascript:alert(1)",
])
def test_ingest_request_rejects_bad_scheme(bad_url):
    with pytest.raises(ValidationError):
        IngestRequest(url=bad_url)


# ---------------------------------------------------------------------------
# T-22.3 — IngestRequest rejects a missing URL
# ---------------------------------------------------------------------------

def test_ingest_request_missing_url():
    with pytest.raises(ValidationError):
        IngestRequest()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# T-22.4 — ChatMessage valid roles
# ---------------------------------------------------------------------------

def test_chat_message_human_role():
    msg = ChatMessage(role="human", content="Hello")
    assert msg.role == "human"


def test_chat_message_ai_role():
    msg = ChatMessage(role="ai", content="Hello back")
    assert msg.role == "ai"


# ---------------------------------------------------------------------------
# T-22.5 — ChatMessage rejects invalid role
# ---------------------------------------------------------------------------

def test_chat_message_invalid_role():
    with pytest.raises(ValidationError):
        ChatMessage(role="assistant", content="Hi")  # type: ignore[arg-type]


def test_chat_message_invalid_role_user():
    with pytest.raises(ValidationError):
        ChatMessage(role="user", content="Hi")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T-22.6 — ChatMessage round-trips through model_dump / model_validate
# ---------------------------------------------------------------------------

def test_chat_message_round_trip():
    original = ChatMessage(role="human", content="What is RAG?")
    data = original.model_dump()
    restored = ChatMessage.model_validate(data)
    assert restored.role == original.role
    assert restored.content == original.content


# ---------------------------------------------------------------------------
# T-22.7 — ChatRequest.history defaults to empty list
# ---------------------------------------------------------------------------

def test_chat_request_history_defaults_empty():
    req = ChatRequest(question="What is RAG?", collection_id="abc123")
    assert req.history == []


# ---------------------------------------------------------------------------
# T-22.8 — ChatRequest.history rejects invalid role values
# ---------------------------------------------------------------------------

def test_chat_request_rejects_invalid_history_role():
    with pytest.raises(ValidationError):
        ChatRequest(
            question="Q",
            collection_id="abc",
            history=[{"role": "system", "content": "You are helpful"}],
        )
