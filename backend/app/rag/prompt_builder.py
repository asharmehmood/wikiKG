"""XML-delimited prompt assembly for the RAG pipeline.

Public API:
    build_messages(question, retrieved_docs, history) -> list[BaseMessage]

Security (OWASP LLM01 2025 / NFR-12 — do not soften):
  - Retrieved chunks are wrapped in <context>…</context> tags.
  - System prompt explicitly tells the model to ignore any instructions
    found inside that block.

Constants CONTEXT_OPEN / CONTEXT_CLOSE are the definitive delimiter
strings; test_prompt_builder.py asserts their exact presence.

Implemented in: T-12
"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

from app.api.schemas import ChatMessage

# Delimiter constants — referenced in test assertions; do not change.
CONTEXT_OPEN = "<context>"
CONTEXT_CLOSE = "</context>"
MAX_HISTORY_TURNS = 6


def build_messages(
    question: str,
    retrieved_docs: list[Document],
    history: list[ChatMessage],
) -> list[BaseMessage]:
    """Return the ordered message list ready to pass to the LLM."""
    raise NotImplementedError("Implemented in T-12")
