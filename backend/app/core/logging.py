"""Structured JSON logging setup.

get_logger(name)         — return a named logger; call configure_logging() first.
configure_logging(level) — install JSON formatter on the root logger.
                           Called once from main.py lifespan on startup.

JSON log record fields: level, timestamp, name, message, request_id (when set).

Implemented in: T-08
"""
from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.  Call configure_logging() before first use."""
    return logging.getLogger(name)


def configure_logging(log_level: str = "INFO") -> None:
    """Install JSON formatter on the root logger.

    Call once at application startup (from main.py lifespan).
    """
    raise NotImplementedError("Implemented in T-08")
