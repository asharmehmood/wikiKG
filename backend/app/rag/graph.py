"""LangGraph RagGraph state machine.

Node sequence:
    embed_question → retrieve → build_prompt → stream_answer

State definition: RagState (TypedDict below)

stream_answer yields tokens via LLMInterface.stream(); the FastAPI route
handler in routes.py consumes this async generator for SSE delivery.
The compiled graph is exported as `rag_graph`.

Usage in routes.py:
    state = await run_rag(question, collection_id, history, store, llm)
    async for token in llm.stream(state["messages"]):
        yield token          # → SSE

Implemented in: T-15
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph

from app.api.schemas import ChatMessage
from app.core.interfaces import LLMInterface, VectorStoreInterface
from app.core.logging import get_logger
from app.rag.prompt_builder import build_messages
from app.rag.retriever import embed_query

logger = get_logger(__name__)


class RagState(TypedDict, total=False):
    # Public fields (flow data)
    question: str
    collection_id: str
    history: list[ChatMessage]
    retrieved_docs: list[Document]
    messages: list[BaseMessage]
    # Dependencies injected by run_rag(); prefixed with _ by convention.
    _store: VectorStoreInterface
    _llm: LLMInterface
    _embed_model: str
    _ollama_host: str
    _top_k: int


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def _node_embed_question(state: RagState) -> dict[str, Any]:
    """Embed the user question with the retrieval prefix."""
    vector = await embed_query(
        question=state["question"],
        embed_model=state["_embed_model"],
        ollama_host=state["_ollama_host"],
    )
    # Store vector temporarily in state for the retrieve node
    return {"_query_vector": vector}


async def _node_retrieve(state: RagState) -> dict[str, Any]:
    """Retrieve the top-k chunks from Qdrant."""
    store: VectorStoreInterface = state["_store"]
    vector: list[float] = state["_query_vector"]  # type: ignore[index]
    docs = await store.search(
        query_vector=vector,
        collection=state["collection_id"],
        k=state.get("_top_k", 4),
    )
    logger.info("rag_retrieve_done", extra={"chunk_count": len(docs)})
    return {"retrieved_docs": docs}


async def _node_build_prompt(state: RagState) -> dict[str, Any]:
    """Assemble the final message list using the prompt builder."""
    messages = build_messages(
        question=state["question"],
        retrieved_docs=state.get("retrieved_docs", []),
        history=state.get("history", []),
    )
    return {"messages": messages}


async def _node_stream_answer(state: RagState) -> dict[str, Any]:
    """Call the LLM (non-streaming) to populate `answer` in state.

    For token-by-token SSE the route handler should call llm.stream(messages)
    directly on state["messages"] — this node exists for batch/test scenarios.
    """
    llm: LLMInterface = state["_llm"]
    answer = await llm.generate(state["messages"])
    logger.info("rag_answer_generated")
    return {"answer": answer}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    g: StateGraph = StateGraph(RagState)  # type: ignore[arg-type]
    g.add_node("embed_question", _node_embed_question)
    g.add_node("retrieve", _node_retrieve)
    g.add_node("build_prompt", _node_build_prompt)
    g.add_node("stream_answer", _node_stream_answer)

    g.set_entry_point("embed_question")
    g.add_edge("embed_question", "retrieve")
    g.add_edge("retrieve", "build_prompt")
    g.add_edge("build_prompt", "stream_answer")
    g.add_edge("stream_answer", END)
    return g


rag_graph = _build_graph().compile()


# ---------------------------------------------------------------------------
# Public convenience wrapper
# ---------------------------------------------------------------------------

async def run_rag(
    question: str,
    collection_id: str,
    history: list[ChatMessage],
    store: VectorStoreInterface,
    llm: LLMInterface,
    embed_model: str = "mxbai-embed-large",
    ollama_host: str = "http://localhost:11434",
    top_k: int = 4,
) -> RagState:
    """Run the full RAG graph and return the final state.

    The returned state contains:
      - ``retrieved_docs`` — chunks used as context
      - ``messages``       — final message list (for SSE streaming in routes.py)
      - ``answer``         — full response string (for batch use)
    """
    initial: RagState = {
        "question": question,
        "collection_id": collection_id,
        "history": history,
        "_store": store,
        "_llm": llm,
        "_embed_model": embed_model,
        "_ollama_host": ollama_host,
        "_top_k": top_k,
    }
    final_state: RagState = await rag_graph.ainvoke(initial)  # type: ignore[assignment]
    return final_state


async def stream_rag(
    question: str,
    collection_id: str,
    history: list[ChatMessage],
    store: VectorStoreInterface,
    llm: LLMInterface,
    embed_model: str = "mxbai-embed-large",
    ollama_host: str = "http://localhost:11434",
    top_k: int = 4,
) -> AsyncIterator[str]:
    """Run embed → retrieve → build_prompt, then stream LLM tokens.

    Yields individual token strings for SSE delivery. This is the primary
    entry point used by routes.py for the /api/chat endpoint.
    """
    initial: RagState = {
        "question": question,
        "collection_id": collection_id,
        "history": history,
        "_store": store,
        "_llm": llm,
        "_embed_model": embed_model,
        "_ollama_host": ollama_host,
        "_top_k": top_k,
    }
    # Run only the first 3 nodes (embed → retrieve → build_prompt)
    setup_graph = _build_setup_graph().compile()
    state: RagState = await setup_graph.ainvoke(initial)  # type: ignore[assignment]
    return llm.stream(state["messages"])


async def prepare_rag(
    question: str,
    collection_id: str,
    history: list[ChatMessage],
    store: VectorStoreInterface,
    llm: LLMInterface,
    embed_model: str = "mxbai-embed-large",
    ollama_host: str = "http://localhost:11434",
    top_k: int = 4,
) -> RagState:
    """Run embed → retrieve → build_prompt and return intermediate state.

    Returns state with ``messages`` (ready for LLM) and ``retrieved_docs``
    (used to populate SSE sources).  Routes.py streams from ``messages`` via
    ``llm.stream()`` after calling this function.
    """
    initial: RagState = {
        "question": question,
        "collection_id": collection_id,
        "history": history,
        "_store": store,
        "_llm": llm,
        "_embed_model": embed_model,
        "_ollama_host": ollama_host,
        "_top_k": top_k,
    }
    setup_graph = _build_setup_graph().compile()
    state: RagState = await setup_graph.ainvoke(initial)  # type: ignore[assignment]
    return state


def _build_setup_graph() -> StateGraph:
    """Graph that stops after build_prompt (used for SSE streaming)."""
    g: StateGraph = StateGraph(RagState)  # type: ignore[arg-type]
    g.add_node("embed_question", _node_embed_question)
    g.add_node("retrieve", _node_retrieve)
    g.add_node("build_prompt", _node_build_prompt)

    g.set_entry_point("embed_question")
    g.add_edge("embed_question", "retrieve")
    g.add_edge("retrieve", "build_prompt")
    g.add_edge("build_prompt", END)
    return g
