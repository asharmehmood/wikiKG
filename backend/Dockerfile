# Stage 1 — Build frontend bundle
# ------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2 — Python runtime
# ------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY backend/app/ app/

# Copy built frontend bundle into the static directory that main.py serves
COPY --from=build /frontend/dist app/static/

# Startup script: waits for Qdrant, auto-pulls Ollama models, then starts uvicorn
COPY backend/entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
