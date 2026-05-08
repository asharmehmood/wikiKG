"""LangGraph RagGraph state machine.

Node sequence:
    embed_question → retrieve → build_prompt → stream_answer

State definition: RagState (TypedDict below)

stream_answer yields tokens via LLMInterface.stream(); the FastAPI route
handler in routes.py consumes this async generator for SSE delivery.

The compiled graph is exported as `rag_graph`.
Routes.py calls:  async for token in rag_graph.astream(state): ...

Implemented in: T-15
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

from app.api.schemas import ChatMessage


class RagState(TypedDict, total=False):
    question: str
    collection_id: str
    history: list[ChatMessage]
    retrieved_docs: list[Document]
    messages: list[BaseMessage]


# rag_graph: CompiledGraph = _build_graph()  — assembled in T-15
