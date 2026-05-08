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

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.interfaces import LLMInterface

# 8 000 chars ≈ 2 000 tokens — well within llama3.1:8b's 128 K window
# while leaving room for the system prompt and response.
MAX_SUMMARY_CHARS = 8_000

_SUMMARISE_SYSTEM = (
    "You are a factual summarisation assistant. "
    "Summarise the provided Wikipedia article text in 5 sentences or fewer. "
    "Be concise and factual. Do not add information not present in the text."
)


async def summarise(cleaned_text: str, llm: LLMInterface) -> str:
    """Return a ≤ 5-sentence factual summary of *cleaned_text*."""
    truncated = cleaned_text[:MAX_SUMMARY_CHARS]
    messages = [
        SystemMessage(content=_SUMMARISE_SYSTEM),
        HumanMessage(content=f"Article text:\n\n{truncated}"),
    ]
    return await llm.generate(messages)
