# REQUIREMENTS.md

## 1. My Interpretation of the Brief

Build a single-page web application that lets a user paste a Wikipedia URL, get an
AI-generated summary, and then interactively chat with the article content. All inference
must happen locally via Ollama. The evaluation prizes depth (planning, testability, clean
architecture) over breadth (features).

---

## 2. Functional Requirements

### FR-1 — URL Ingestion
- The user enters a Wikipedia article URL in a text input and submits the form.
- The backend fetches and parses the article: main text body, section headings, and
  references (as plain-text footnotes where available).
- Non-Wikipedia URLs must be rejected with a clear error message.
- Malformed or unreachable URLs must return a user-facing error; they must not crash the
  server.

### FR-2 — Summarisation
- After ingestion the backend calls the local LLM to produce a concise summary
  (≤ 5 sentences) of the article.
- The summary is displayed to the user before the chat box becomes active.
- Summarisation must complete within a reasonable time (~60 s timeout); a timeout error
  is surfaced gracefully.

### FR-3 — Chunking & Embedding
- The article text is split into overlapping chunks (target: ~400 tokens, 50-token overlap).
- Each chunk is embedded using a local embedding model.
- Chunk vectors and their source metadata (section title, chunk index, article URL) are
  stored in the vector database.
- Re-ingesting the same URL replaces the previous data for that article (idempotent).

### FR-4 — RAG Chat
- A chat box below the summary accepts user questions.
- Each question triggers a retrieval step: the top-k (k = 4) most similar chunks are
  fetched from the vector DB.
- The retrieved chunks are injected into a prompt template and the local LLM generates
  an answer grounded solely in those chunks.
- The system prompt explicitly forbids the model from answering from general knowledge
  if the retrieved context does not contain the answer.
- Retrieved context is wrapped in XML delimiters (`<context>...</context>`) in the
  prompt to structurally separate data from instructions (indirect prompt injection
  mitigation — OWASP LLM01).
- Chat history (within a single session) is passed back to the LLM for conversational
  coherence (last 6 turns maximum).
- Each answer includes a "Sources" section listing the section titles of the retrieved
  chunks used, so the user can verify grounding.
- Answers are streamed token-by-token to the frontend where technically feasible.

### FR-5 — Error Handling
- Bad URL (non-Wikipedia, 404, redirect loop) → HTTP 422 with a human-readable message.
- LLM unavailable (Ollama not running) → HTTP 503 with a retry suggestion.
- Vector DB unavailable → HTTP 503, operation aborted cleanly.
- Empty article (disambiguation page, redirect stub) → HTTP 422 explaining the issue.

---

## 3. Non-Functional Requirements

| ID    | Category        | Requirement |
|-------|-----------------|-------------|
| NFR-1 | Performance     | Ingestion + summarisation completes in < 90 s on a mid-range laptop (single Ollama call). |
| NFR-2 | Performance     | Chat response first-token latency < 10 s on the same hardware. |
| NFR-3 | Reliability     | All services restart automatically on failure (`restart: unless-stopped` in compose). |
| NFR-4 | Security        | No secrets committed to the repository. All config via `.env` (template in `.env.example`). |
| NFR-5 | Security        | Wikipedia URLs validated server-side against an allowlist pattern before any HTTP fetch. |
| NFR-6 | Portability     | Full stack starts with `docker compose up`. No manual setup steps beyond installing Docker. |
| NFR-7 | Testability     | Business logic is isolated from framework and I/O so it can be unit-tested without live services. |
| NFR-8 | Observability   | Structured JSON logs from the backend (level, timestamp, request-id, message). |
| NFR-9 | Coverage        | ≥ 85 % line coverage on application code (excluding entrypoints and generated boilerplate). |
| NFR-10| Maintainability | LLM client and vector-store client are behind thin interfaces so they can be swapped. |
| NFR-11| Security        | All requests to the Wikipedia REST API include a descriptive `User-Agent` header (required by Wikimedia ToS; max 200 req/s). |
| NFR-12| Security        | Prompt injection defence: retrieved chunks are structurally separated from instructions in every LLM prompt (XML delimiters + defensive system prompt language). |

---

## 4. In-Scope

- Single Wikipedia article per session (one URL at a time).
- Scraping via the Wikipedia REST API (`/api/rest_v1/page/summary` + `mobile-sections`)
  — more reliable than raw HTML scraping.
- Local LLM via Ollama (model: `llama3.2:3b` or `qwen2.5:3b` depending on RAM).
- Local embeddings via `nomic-embed-text` pulled through Ollama.
- Vector store: Qdrant running as a compose service.
- Frontend: minimal React SPA (Vite) — single page, no routing needed.
- Backend: Python / FastAPI.
- Unit tests + at least one integration test exercising the full wired-up stack.
- Coverage report committed to the repository.
- `docker-compose.yml` for the full stack.
- Planning artefacts: this file, DESIGN.md, TASKS.md.
- NOTES.md with post-mortems and what-I'd-change.

---

## 5. Out-of-Scope

- User authentication or accounts.
- Multi-article ingestion or a library of articles.
- Persistent chat history across browser sessions.
- Non-Wikipedia URLs (by design — explicit constraint).
- Image, table, or infobox extraction (text only).
- Hosted LLM APIs (OpenAI, Anthropic, Gemini) in the running application.
- Mobile-optimised UI or visual design polish.
- CI/CD pipelines (out of time budget).
- Horizontal scaling or production-grade deployment.

---

## 6. Assumptions

| # | Assumption | Rationale |
|---|-----------|-----------|
| A1 | The reviewer's machine has Ollama installed on the host (or inside Docker) with at least one 3B-class model pulled. | Bundling a multi-GB model inside a Docker image is impractical. The compose file will document which `ollama pull` commands are needed. |
| A2 | The Wikipedia article is English-language. | Multilingual chunking and embedding would require a different embedding model; that is a separate concern. |
| A3 | "References" means the citation list at the bottom of the article (where the REST API exposes them). | Inline hyperlinks in the body are not treated as references; the brief says "where reasonable". |
| A4 | Session state (chat history, current article) lives in the backend process memory for the duration of a browser session. | A Redis/DB-backed session store would be over-engineering for this scope. |
| A5 | A single Ollama instance handles both embedding and generation. | Simplifies the compose topology; both model types are served by the same Ollama endpoint. |
| A6 | The 85 % coverage threshold excludes: `main.py` entrypoints, `__init__.py` files, Alembic/migration scripts (none planned), and any auto-generated Pydantic schema files. | Consistent with the brief's note that "generated boilerplate" is excluded. |
| A7 | Streaming LLM responses is a "nice-to-have": implemented if SSE works cleanly with the chosen stack, documented as a known limitation otherwise. | Streaming adds complexity at the integration-test layer. |
| A8 | The Wikipedia REST API (`/api/rest_v1/`) is used instead of raw HTML scraping. Rate limit is 200 req/s (well within our single-request-per-ingestion pattern). A custom `User-Agent` header is set on all requests as required by Wikimedia Terms of Use. | The REST API returns clean, structured JSON (sections, references, summary) — far more reliable than parsing raw HTML. |

---

## 7. Open Questions — Decided Unilaterally

| Question | Decision | Why |
|----------|----------|-----|
| Which embedding model? | `nomic-embed-text` via Ollama | Free, local, good English quality, pulls cleanly via `ollama pull`. Avoids any hosted-API dependency. |
| Which vector DB? | Qdrant | First-class Docker image, good Python SDK, persistent-on-disk mode out of the box, well-documented for RAG use-cases. |
| Chunk size? | 400 tokens, 50-token overlap | Balances context window usage (3B models have limited context) vs. retrieval granularity. Overlap prevents information loss at boundaries. |
| Top-k retrieval? | k = 4 | Four chunks × ~400 tokens = ~1 600 tokens of context, well within a 3B model's practical context window alongside the system prompt and chat history. |
| Frontend framework? | React + Vite | Familiar, fast to scaffold, produces a small static bundle. No SSR needed for this scope. |
| Streaming? | SSE streaming implemented on the `/chat` endpoint, with a non-streaming fallback if the client does not support it. | Better UX for slow local models; not hard to add with FastAPI's `StreamingResponse`. |
| Re-ingestion behaviour? | Delete existing Qdrant collection for the URL, then re-insert. | Idempotent, predictable, no stale chunks. |

---

## 8. Constraints Summary

- **Must** use Ollama for all inference in the running application.
- **Must** start with `docker compose up`.
- **Must** not commit secrets.
- **Must** achieve ≥ 85 % line coverage.
- **Must** include REQUIREMENTS.md, DESIGN.md, TASKS.md at the repo root.
- **Must** include a screen recording or screenshots of the working app.
