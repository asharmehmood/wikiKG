"""FastAPI application factory.

create_app() wires together:
  - API router        (api/routes.py)
  - StaticFiles mount for the built frontend bundle
  - CORS middleware
  - Structured JSON logging on startup

Implemented in: T-18
"""
from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Return a configured FastAPI application instance."""
    app = FastAPI(title="wikiKG", version="0.1.0")
    # T-18: include router, StaticFiles, CORS, lifespan logging
    return app


app = create_app()
