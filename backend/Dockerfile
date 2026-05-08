# Stage 1 — Build frontend bundle
# ------------------------------------------------------------------
FROM node:20-alpine AS frontend-build
# TODO T-27: COPY package files, npm ci, npm run build

# Stage 2 — Python runtime
# ------------------------------------------------------------------
FROM python:3.11-slim AS runtime
# TODO T-27: COPY requirements.txt + pip install, COPY app + dist,
#            EXPOSE 8000, CMD uvicorn app.main:app
