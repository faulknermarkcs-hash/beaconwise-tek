# src/ecosphere/consensus/adapters/symbolic_adapter.py
"""Symbolic AI Engine Adapter.

Governs rule-based, logic programming, and expert system outputs
through the same deterministic governance pipeline as LLMs.

This adapter wraps any callable that takes a prompt string and
returns a structured result, enabling governance over:
  - expert systems
  - rule engines
  - constraint solvers
  - decision trees
  - knowledge graph queries
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional, Tuple

from .base import ModelAdapter, AdapterError


class SymbolicAdapter(ModelAdapter):
    """Adapter for symbolic AI / rule-based engines."""

    provider = "symbolic"

    def __init__(
        self,
        *,
        provider: str = "symbolic",
        model: str = "rule-engine-v1",
        engine_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        super().__init__(provider=provider, model=model)
        self._engine_fn = engine_fn

    async def _call_model(
        self,
        *,
        prompt: str,
        temperature: float,
        extra: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        if not self._engine_fn:
            raise AdapterError("No symbolic engine function configured")

        try:
            result = self._engine_fn(prompt)
            if isinstance(result, dict):
                text = json.dumps(result)
            else:
                text = str(result)
            meta = {
                "adapter": "symbolic",
                "model": self.model,
                "deterministic": True,
            }
            return text, meta
        except Exception as e:
            raise AdapterError(f"Symbolic engine error: {e}") from e
