"""One-shot article summarisation.

Public API:
    summarise(cleaned_text, llm) -> str

Behaviour:
  - Truncates *cleaned_text* to MAX_SUMMARY_CHARS before the LLM call
    (avoids context-window overflow for very long articles).
  - Prompt: "Summarise this Wikipedia article in ≤ 5 sentences. Be factual."
  - Uses LLMInterface.generate() (non-streaming, single call).

Implemented in: T-13
"""
from __future__ import annotations

from app.core.interfaces import LLMInterface

# 8 000 chars ≈ 2 000 tokens — well within llama3.1:8b's 128 K window
# while leaving room for the system prompt and response.
MAX_SUMMARY_CHARS = 8_000


async def summarise(cleaned_text: str, llm: LLMInterface) -> str:
    """Return a ≤ 5-sentence factual summary of *cleaned_text*."""
    raise NotImplementedError("Implemented in T-13")
