"""Structured JSON logging setup.

Public API:
    get_logger(name)         — return a named logger (call configure_logging first).
    configure_logging(level) — install JSON formatter on the root logger once at startup.
    request_id_var           — ContextVar; set in middleware, included in every log record.

JSON log record fields: level, timestamp, name, message, request_id.

Usage in middleware (main.py):
    from app.core.logging import request_id_var
    token = request_id_var.set(str(uuid.uuid4()))
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
"""
from __future__ import annotations

import logging
import logging.config
from contextvars import ContextVar

from pythonjsonlogger.json import JsonFormatter

# Holds the current request-id; empty string when outside a request context.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class _RequestIdFilter(logging.Filter):
    """Injects request_id from the ContextVar into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(log_level: str = "INFO") -> None:
    """Install the JSON formatter and request-id filter on the root logger.

    Safe to call more than once (subsequent calls are no-ops).
    """
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g. during tests or hot-reload).
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    )
    handler.addFilter(_RequestIdFilter())

    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    Modules should call this at module level:
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)

