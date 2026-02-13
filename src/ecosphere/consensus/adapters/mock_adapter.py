# src/ecosphere/consensus/adapters/mock_adapter.py
"""Mock adapter for offline testing of the consensus orchestrator.

Returns configurable JSON responses matching PrimaryOutput schema.
Supports: normal output, malformed JSON, anchor mismatch, scope violations.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from .base import ModelAdapter


class MockAdapter(ModelAdapter):
    """Test adapter that returns pre-configured responses."""

    provider = "mock"

    def __init__(
        self,
        *,
        provider: str = "mock",
        model: str = "mock-v1",
        responses: Optional[List[str]] = None,
        default_answer: str = "Mock response for testing.",
    ):
        super().__init__(provider=provider, model=model)
        self._responses = list(responses or [])
        self._call_count = 0
        self._default_answer = default_answer

    def _next_response(self, prompt: str) -> str:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            # Extract RUN_ID and EPACK from prompt for anchor matching
            rid = _extract(prompt, "RUN_ID=")
            epack = _extract(prompt, "EPACK=")
            aru = _extract(prompt, "ARU=") or "ANSWER"
            resp = json.dumps({
                "run_id": rid,
                "epack": epack,
                "aru": aru,
                "answer": self._default_answer,
                "reasoning_trace": ["mock_step_1"],
                "claims": [],
                "overall_confidence": 0.8,
                "uncertainty_flags": [],
                "next_step": None,
            })
        self._call_count += 1
        return resp

    async def _call_model(
        self,
        *,
        prompt: str,
        temperature: float,
        extra: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        text = self._next_response(prompt)
        meta = {"mock": True, "call_number": self._call_count, "model": self.model}
        return text, meta


def _extract(text: str, prefix: str) -> str:
    """Extract value after prefix= from prompt text.

    Stops at the first whitespace character (space or newline).
    """
    idx = text.find(prefix)
    if idx == -1:
        return ""
    start = idx + len(prefix)
    # Find the earliest whitespace boundary
    end = len(text)
    for ch in (" ", "\n", "\r", "\t"):
        pos = text.find(ch, start)
        if pos != -1 and pos < end:
            end = pos
    return text[start:end].strip()


def mock_primary_json(
    *,
    run_id: str,
    epack: str,
    aru: str = "ANSWER",
    answer: str = "Safe general response.",
    confidence: float = 0.8,
) -> str:
    """Helper to build a valid PrimaryOutput JSON string."""
    return json.dumps({
        "run_id": run_id,
        "epack": epack,
        "aru": aru,
        "answer": answer,
        "reasoning_trace": ["step1"],
        "claims": [],
        "overall_confidence": confidence,
        "uncertainty_flags": [],
        "next_step": None,
    })
