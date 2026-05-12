"""Unit tests for rag/summariser.py.

Test cases:
  - Returns the LLM's output string unchanged
  - Truncates input to MAX_SUMMARY_CHARS before sending to LLM
  - Passes a SystemMessage and HumanMessage to the LLM
"""
from __future__ import annotations

import pytest
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.rag.summariser import MAX_SUMMARY_CHARS, summarise


class _CapturingLLM:
    """Captures the messages passed to generate() for assertion."""
    def __init__(self, answer: str = "A short summary.") -> None:
        self._answer = answer
        self.received: list[BaseMessage] = []

    async def generate(self, messages: list[BaseMessage]) -> str:
        self.received = list(messages)
        return self._answer

    async def stream(self, messages):  # pragma: no cover
        yield self._answer


# ---------------------------------------------------------------------------
# Returns LLM output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarise_returns_llm_output():
    llm = _CapturingLLM("A great summary.")
    result = await summarise("Some article text.", llm)  # type: ignore[arg-type]
    assert result == "A great summary."


# ---------------------------------------------------------------------------
# Truncates long text to MAX_SUMMARY_CHARS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarise_truncates_long_text():
    llm = _CapturingLLM()
    long_text = "x" * (MAX_SUMMARY_CHARS + 500)
    await summarise(long_text, llm)  # type: ignore[arg-type]

    # The HumanMessage content should contain at most MAX_SUMMARY_CHARS 'x' chars
    human_msg = next(m for m in llm.received if isinstance(m, HumanMessage))
    assert long_text[:MAX_SUMMARY_CHARS] in human_msg.content
    assert "x" * (MAX_SUMMARY_CHARS + 1) not in human_msg.content


# ---------------------------------------------------------------------------
# Passes SystemMessage + HumanMessage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarise_passes_system_and_human_messages():
    llm = _CapturingLLM()
    await summarise("Article body.", llm)  # type: ignore[arg-type]

    assert any(isinstance(m, SystemMessage) for m in llm.received)
    assert any(isinstance(m, HumanMessage) for m in llm.received)


# ---------------------------------------------------------------------------
# Short text is not padded / altered
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summarise_short_text_unchanged():
    llm = _CapturingLLM()
    await summarise("Short.", llm)  # type: ignore[arg-type]
    human_msg = next(m for m in llm.received if isinstance(m, HumanMessage))
    assert "Short." in human_msg.content
