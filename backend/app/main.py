"""FastAPI application factory.

create_app() wires together:
  - Structured JSON logging (core/logging.py) configured on startup
  - Request-id middleware — injects a UUID into ContextVar for every request
  - API router         (api/routes.py)
  - StaticFiles mount  for the built frontend bundle at "app/static/"
  - CORS middleware    (localhost:5173 for Vite dev; same origin in prod)
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, request_id_var

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    logger.info("wikiKG starting up", extra={"gen_model": settings.GEN_MODEL})
    yield
    logger.info("wikiKG shutting down")


def create_app() -> FastAPI:
    """Return a fully configured FastAPI application instance."""
    app = FastAPI(title="wikiKG", version="0.1.0", lifespan=_lifespan)

    # ── CORS ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:8000",  # production (same container)
        ],
        allow_methods=["POST", "GET"],
        allow_headers=["*"],
    )

    # ── Request-id middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def _inject_request_id(request: Request, call_next) -> Response:
        token = request_id_var.set(request.headers.get("X-Request-Id", str(uuid.uuid4())))
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)
        return response

    # ── API routes ────────────────────────────────────────────────────────
    app.include_router(router)

    # ── Static frontend bundle ────────────────────────────────────────────
    # Built by the Docker multi-stage build and copied here.
    # Only mounted when the directory exists so `uvicorn` still works during
    # backend-only development without a built frontend.
    import pathlib
    static_dir = pathlib.Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()

