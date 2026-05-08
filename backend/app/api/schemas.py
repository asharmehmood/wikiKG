"""Pydantic v2 request and response models for the API layer.

These models are intentionally thin — no business logic lives here.
Import them in routes.py, test files, and wherever type-safe data
exchange is needed between layers.

Note: ChatMessage.role values ("human" / "ai") map directly to
LangChain's HumanMessage / AIMessage in prompt_builder.py.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, HttpUrl


class IngestRequest(BaseModel):
    url: HttpUrl


class IngestResponse(BaseModel):
    article_title: str
    summary: str
    chunk_count: int
    collection_id: str


class ChatMessage(BaseModel):
    """A single turn of conversation history."""

    role: Literal["human", "ai"]
    content: str


class ChatRequest(BaseModel):
    question: str
    collection_id: str
    history: list[ChatMessage] = []


class ErrorResponse(BaseModel):
    detail: str
