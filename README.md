# wikiKG — Wikipedia RAG Chat

Paste a Wikipedia URL, get an AI-generated summary, then chat with the article using retrieval-augmented generation. Everything runs locally: no OpenAI keys, no cloud calls. Inference is handled by a local [Ollama](https://ollama.com) instance; vectors are stored in [Qdrant](https://qdrant.tech); the backend is a FastAPI + LangGraph pipeline served from a single Docker image that also bundles the React frontend.

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2
- [Ollama](https://ollama.com/download) running on your host machine

Pull the required models before starting:

```bash
ollama pull llama3.1:8b
ollama pull mxbai-embed-large
```

### Start the stack

```bash
git clone <repo-url>
cd wikiKG
docker compose up --build
```

Open **http://localhost:8000** in your browser.

> **Linux users:** The compose file already sets `extra_hosts: host-gateway` so the backend container can reach Ollama at `http://host.docker.internal:11434`. No additional config needed.
>
> **Docker Desktop (macOS / Windows):** `host.docker.internal` resolves automatically.

---

## Architecture

The backend exposes two API endpoints (`POST /api/ingest`, `POST /api/chat`) backed by two LangGraph pipelines — one for ingestion (fetch → chunk → embed → store → summarise) and one for RAG chat (embed query → retrieve → build prompt → stream tokens). The built React frontend is served as static files from the same FastAPI process, so there is only one container to expose. See [DESIGN.md](DESIGN.md) for full architecture diagrams, technology decision tables, and the interface contracts.

```
Browser  ──►  FastAPI (port 8000)
                 │  POST /api/ingest  ──►  Ingestion LangGraph  ──►  Qdrant
                 │  POST /api/chat    ──►  RAG LangGraph  ──►  Qdrant + Ollama (SSE)
                 └  GET /            ──►  React SPA (static files)
```

---

## Running Tests

```bash
docker compose run --rm backend pytest
```

Or locally (with a running Qdrant instance on port 6333):

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

Coverage threshold: **85 %** (achieved: 86.42 %).

---

## Configuration

All settings are read from environment variables. Copy `.env.example` and adjust if needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama base URL |
| `QDRANT_HOST` | `qdrant` (in compose) / `localhost` (local) | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant gRPC/HTTP port |
| `GEN_MODEL` | `llama3.1:8b` | Generation model |
| `EMBED_MODEL` | `mxbai-embed-large` | Embedding model |
| `LOG_LEVEL` | `INFO` | Python log level |

---

## Assumptions & Known Limitations

- **English Wikipedia only.** The URL allowlist accepts `en.wikipedia.org` exclusively.
- **Single article at a time.** Each chat session is scoped to one ingested article. Re-ingesting the same URL replaces the previous data (idempotent).
- **No session persistence.** Chat history lives in the browser; refreshing the page starts fresh.
- **Ollama must be running on the host.** The stack does not start Ollama by default. To run Ollama inside Docker instead, start the optional service: `docker compose --profile gpu up`.
- **First-token latency.** On a mid-range laptop with no GPU, expect 3–10 s first-token latency and up to 90 s for the initial ingestion + summarisation step (llama3.1:8b on CPU).
- **Disambiguation pages** are rejected with HTTP 422 — the user must choose a specific article.

---

## Screenshot

<!-- Add screenshot or screen recording here after T-31 smoke test -->

