#!/usr/bin/env bash
# backend/entrypoint.sh
# Runs before uvicorn starts:
#   1. Waits for Qdrant to accept connections.
#   2. Checks whether each required Ollama model is already present; pulls it if not.
#   3. Execs uvicorn.
set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://host.docker.internal:11434}"
QDRANT_HOST="${QDRANT_HOST:-qdrant}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
GEN_MODEL="${GEN_MODEL:-llama3.1:8b}"
EMBED_MODEL="${EMBED_MODEL:-mxbai-embed-large}"

# ── 1. Wait for Qdrant ────────────────────────────────────────────────────────
echo "[entrypoint] Waiting for Qdrant at ${QDRANT_HOST}:${QDRANT_PORT}…"
until python3 - <<PYEOF 2>/dev/null
import socket, sys
try:
    s = socket.create_connection(("${QDRANT_HOST}", int("${QDRANT_PORT}")), timeout=2)
    s.close(); sys.exit(0)
except Exception:
    sys.exit(1)
PYEOF
do
    echo "[entrypoint]   not ready — retrying in 2 s…"
    sleep 2
done
echo "[entrypoint] Qdrant is up."

# ── 2. Check / pull Ollama models ─────────────────────────────────────────────
_model_present() {
    local model="$1"
    python3 - <<PYEOF 2>/dev/null
import urllib.request, json, sys
try:
    resp = urllib.request.urlopen("${OLLAMA_HOST}/api/tags", timeout=5)
    data = json.load(resp)
    names = {m["name"] for m in data.get("models", [])}
    # Bare name (no tag) implies :latest
    want = "${model}" if ":" in "${model}" else "${model}:latest"
    sys.exit(0 if (want in names or "${model}" in names) else 1)
except Exception:
    sys.exit(2)  # Ollama unreachable — distinct from "not present"
PYEOF
}

_pull_model() {
    local model="$1"
    echo "[entrypoint] Pulling ${model} — this may take several minutes on first run…"
    python3 - <<PYEOF
import urllib.request, json, sys

req = urllib.request.Request(
    "${OLLAMA_HOST}/api/pull",
    data=json.dumps({"model": "${model}", "stream": True}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            try:
                obj = json.loads(raw)
                status    = obj.get("status", "")
                completed = obj.get("completed")
                total     = obj.get("total")
                if completed and total:
                    pct = int(completed / total * 100)
                    print(f"\r[entrypoint]   {status} {pct}%", end="", flush=True)
                elif status:
                    print(f"[entrypoint]   {status}", flush=True)
            except Exception:
                pass
    print()
except Exception as e:
    print(f"[entrypoint] Warning: pull failed ({e}). Continuing.", flush=True)
PYEOF
}

for MODEL in "${GEN_MODEL}" "${EMBED_MODEL}"; do
    rc=0; _model_present "${MODEL}" || rc=$?
    if [[ $rc -eq 2 ]]; then
        echo "[entrypoint] WARNING: Ollama unreachable at ${OLLAMA_HOST} — skipping pull of ${MODEL}."
    elif [[ $rc -eq 0 ]]; then
        echo "[entrypoint] Model ${MODEL} already present — skipping pull."
    else
        _pull_model "${MODEL}"
    fi
done

# ── 3. Start the application ──────────────────────────────────────────────────
HOST_PORT="${HOST_PORT:-9000}"
echo "[entrypoint] Starting uvicorn…"
echo "[entrypoint] ──────────────────────────────────────────"
echo "[entrypoint]  wikiKG is ready at http://localhost:${HOST_PORT}"
echo "[entrypoint] ──────────────────────────────────────────"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
