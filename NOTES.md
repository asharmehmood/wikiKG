# NOTES.md — Post-mortem & Retrospective

---

## What Worked Well

**LangGraph as the orchestration layer** was the right call. Representing both the ingestion and the RAG pipeline as explicit state machines made the data flow auditable — every intermediate value (chunks, query vector, retrieved docs, messages) is named and visible in the state dict rather than buried in call stacks. Debugging the `_query_vector` bug (see below) was straightforward precisely because the state dict made the missing field obvious.

**Pydantic v2 + FastAPI** removed an entire class of bugs. The `IngestRequest(url: HttpUrl)` model rejected bad input before any application code ran, and the `ChatMessage(role: Literal["human","ai"])` constraint meant the prompt builder could trust its inputs without defensive checks.

**respx for HTTP mocking** was much cleaner than monkeypatching `httpx.AsyncClient`. The `@respx.mock` decorator intercepts at the transport layer, so the test exercises the real `article_fetcher` code path including header assertions (`User-Agent`, `follow_redirects`).

**Interface seams (`LLMInterface`, `VectorStoreInterface`)** paid off immediately in tests. Swapping in `MockLLM` and `InMemoryStore` required zero change to business logic. This is the single most important structural decision in the codebase.

---

## Decisions That Diverged from DESIGN.md

**`RagState` missing `_query_vector`:** DESIGN.md described the RAG state dict as `{ question, collection_id, history, retrieved_docs, messages, token_stream }`. In practice, LangGraph's `StateGraph` drops any key that is not declared in the `TypedDict`. The embedded query vector was computed in the `embed_question` node and then silently discarded before the `retrieve` node could use it, causing a `KeyError`. The fix was adding `_query_vector: list[float]` to the TypedDict — a constraint that DESIGN.md's informal dict notation didn't surface.

**`stream_answer` as a separate generator, not a LangGraph node:** The original design had `stream_answer` as the fourth node in the RAG graph. In practice, streaming tokens through LangGraph's state machine requires the entire graph invocation to complete before any token is yielded, which defeats SSE. The implementation splits this into `prepare_rag()` (runs the graph up through `build_prompt`) and `stream_rag()` (async generator that streams directly from `llm.stream()`), bypassing the graph for the streaming step.

**Qdrant image version pinned to `v1.9.1`:** The stub compose file used `v1.13.3`. The integration tests and retriever were built against the `qdrant-client` SDK targeting `v1.9.x` collection creation API. Pinned to `v1.9.1` to avoid SDK/server version skew.

**OllamaEmbeddings in integration tests:** DESIGN.md assumed a `MockEmbedder` injected via dependency override would be sufficient. In practice, `OllamaEmbeddings` is instantiated inside `QdrantStore` and `rag/graph.py` at call time, not at import time, so there was no single injection point. The fix was an autouse `monkeypatch` fixture that patches `OllamaEmbeddings.aembed_documents` and `aembed_query` at the class level, plus a separate patch on `app.rag.graph.embed_query` for the RAG path.

---

## Top 3 Improvements for a Production Version

1. **Re-ranker after retrieval.** The current pipeline retrieves the top-4 chunks by cosine similarity and passes them all to the LLM. A cross-encoder re-ranker (e.g. `ms-marco-MiniLM-L-6-v2` via `sentence-transformers`) would re-score the candidates and drop low-relevance chunks before they enter the prompt, reducing hallucination on borderline queries without increasing the context window.

2. **Persistent chat sessions with a session store.** Chat history currently lives in the browser and is sent back on every request. For multi-tab or multi-device use, sessions should be stored server-side (Redis or a lightweight SQLite table keyed by `session_id`). This also enables conversation history to survive page reload and makes the `collection_id` + `session_id` pair the natural unit of a "reading session".

3. **Metadata filtering and multi-article support.** The vector store currently holds one collection per article (keyed by `md5(url)`). A production system would store all chunks in a single collection with a `source_url` metadata field and use Qdrant's payload filtering to scope retrieval per article. This removes the per-article collection overhead and enables cross-article queries (e.g. "compare what both articles say about X").

---

## How GitHub Copilot Was Used

The project used three distinct Copilot modes, each matched to task type:

- **Ask mode** — technology selection at each decision point: choosing Qdrant over Chroma/FAISS (persistent, async-native, Docker-friendly), selecting `mxbai-embed-large` over `nomic-embed-text` (MTEB score, 1024-dim output), deciding on `RecursiveCharacterTextSplitter` parameters. Back-and-forth clarification without committing to a plan.

- **Plan mode** — component design before writing any code: the ingestion LangGraph node sequence, the prompt builder message structure, the `LLMInterface`/`VectorStoreInterface` ABC contracts, the Dockerfile multi-stage topology. Producing a structured breakdown that could then be reviewed and adjusted.

- **Agent mode** — multi-step implementation: scaffolding the full `backend/` + `frontend/` directory tree, writing all test files (unit + integration), implementing the FastAPI routes and SSE generator, building all four React components, and generating the `Dockerfile` + `docker-compose.yml`. Each agent run was scoped to a single TASKS.md task with a concrete prompt (see TASKS.md for all prompts).

The split was deliberate: Copilot's agent mode is fast for boilerplate and wiring but needs a well-scoped prompt to avoid over-engineering. Ask/Plan modes front-loaded the thinking so each agent invocation had a clear spec.
