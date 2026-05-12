"""Unit tests for rag/graph.py — classify node and routing logic.

Test cases:
  - _node_classify: LLM returns "RAG" → needs_rag=True
  - _node_classify: LLM returns "CHAT" → needs_rag=False
  - _node_classify: case-insensitive ("chat" / "Chat" → False)
  - _route_after_classify: needs_rag=True → "embed_question"
  - _route_after_classify: needs_rag=False → "direct_prompt"
  - _route_after_classify: missing key defaults to RAG path
  - _node_direct_build_prompt: sets messages and empty retrieved_docs
  - prepare_rag: CHAT path skips retrieval, messages still set
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage

from app.api.schemas import ChatMessage
from app.core.interfaces import LLMInterface, VectorStoreInterface
from app.rag.graph import (
    _node_classify,
    _node_direct_build_prompt,
    _route_after_classify,
    prepare_rag,
)


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

class _MockLLM(LLMInterface):
    def __init__(self, answer: str = "RAG") -> None:
        self._answer = answer

    async def generate(self, messages: list[BaseMessage]) -> str:
        return self._answer

    async def stream(self, messages: list[BaseMessage]) -> AsyncIterator[str]:  # type: ignore[override]
        yield self._answer


class _MockStore(VectorStoreInterface):
    def __init__(self) -> None:
        self.searched = False

    async def upsert(self, chunks: list[Document], collection: str) -> None:
        pass

    async def search(self, query_vector: list[float], collection: str, k: int) -> list[Document]:
        self.searched = True
        return [Document(page_content="ctx", metadata={"section_title": "S1"})]

    async def delete_collection(self, collection: str) -> None:
        pass


def _base_state(llm: _MockLLM, store: _MockStore | None = None) -> dict:
    return {
        "question": "Hello there",
        "collection_id": "col1",
        "history": [],
        "_llm": llm,
        "_store": store or _MockStore(),
        "_embed_model": "mxbai-embed-large",
        "_ollama_host": "http://localhost:11434",
        "_top_k": 4,
    }


# ---------------------------------------------------------------------------
# _node_classify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_rag_response():
    state = _base_state(_MockLLM("RAG"))
    result = await _node_classify(state)  # type: ignore[arg-type]
    assert result["needs_rag"] is True


@pytest.mark.asyncio
async def test_classify_chat_response():
    state = _base_state(_MockLLM("CHAT"))
    result = await _node_classify(state)  # type: ignore[arg-type]
    assert result["needs_rag"] is False


@pytest.mark.asyncio
async def test_classify_lowercase_chat():
    state = _base_state(_MockLLM("chat"))
    result = await _node_classify(state)  # type: ignore[arg-type]
    assert result["needs_rag"] is False


@pytest.mark.asyncio
async def test_classify_mixed_case_rag():
    state = _base_state(_MockLLM("  RAG  "))
    result = await _node_classify(state)  # type: ignore[arg-type]
    assert result["needs_rag"] is True


# ---------------------------------------------------------------------------
# _route_after_classify
# ---------------------------------------------------------------------------

def test_route_rag_path():
    assert _route_after_classify({"needs_rag": True}) == "embed_question"  # type: ignore[arg-type]


def test_route_chat_path():
    assert _route_after_classify({"needs_rag": False}) == "direct_prompt"  # type: ignore[arg-type]


def test_route_missing_key_defaults_to_rag():
    """When needs_rag is absent, default to the safer RAG path."""
    assert _route_after_classify({}) == "embed_question"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _node_direct_build_prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_direct_build_prompt_sets_messages_and_empty_docs():
    state = _base_state(_MockLLM())
    state["history"] = [ChatMessage(role="human", content="Hi"), ChatMessage(role="ai", content="Hello!")]
    result = await _node_direct_build_prompt(state)  # type: ignore[arg-type]
    assert "messages" in result
    assert result["retrieved_docs"] == []
    assert len(result["messages"]) > 0


@pytest.mark.asyncio
async def test_direct_build_prompt_no_history():
    state = _base_state(_MockLLM())
    result = await _node_direct_build_prompt(state)  # type: ignore[arg-type]
    assert result["retrieved_docs"] == []
    # System + current question at minimum
    assert len(result["messages"]) >= 2


# ---------------------------------------------------------------------------
# prepare_rag — CHAT path (no retrieval)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prepare_rag_chat_path_skips_retrieval():
    store = _MockStore()
    llm = _MockLLM("CHAT")

    state = await prepare_rag(
        question="How are you?",
        collection_id="col1",
        history=[],
        store=store,
        llm=llm,
        embed_model="mxbai-embed-large",
        ollama_host="http://localhost:11434",
        top_k=4,
    )

    assert not store.searched, "Store.search should NOT be called on the CHAT path"
    assert state.get("retrieved_docs") == []
    assert state.get("messages") is not None


# ---------------------------------------------------------------------------
# prepare_rag — RAG path (retrieval happens)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prepare_rag_rag_path_calls_retrieval():
    store = _MockStore()
    llm = _MockLLM("RAG")

    # Patch embed_query so we don't need Ollama
    from unittest.mock import patch
    with patch("app.rag.graph.embed_query", AsyncMock(return_value=[0.1, 0.2, 0.3])):
        state = await prepare_rag(
            question="What is RAG?",
            collection_id="col1",
            history=[],
            store=store,
            llm=llm,
            embed_model="mxbai-embed-large",
            ollama_host="http://localhost:11434",
            top_k=4,
        )

    assert store.searched, "Store.search SHOULD be called on the RAG path"
    assert len(state.get("retrieved_docs", [])) > 0
