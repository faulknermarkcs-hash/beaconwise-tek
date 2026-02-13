# src/ecosphere/consensus/adapters/retrieval_adapter.py
"""Retrieval Pipeline Adapter.

Governs RAG (Retrieval-Augmented Generation) pipelines and
document retrieval systems through BeaconWise governance.

Wraps any retrieval function that takes a query and returns
documents/passages, enabling governance over:
  - vector store queries
  - document retrieval systems
  - knowledge base lookups
  - search engine integrations
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from .base import ModelAdapter, AdapterError


class RetrievalAdapter(ModelAdapter):
    """Adapter for retrieval pipelines and RAG systems."""

    provider = "retrieval"

    def __init__(
        self,
        *,
        provider: str = "retrieval",
        model: str = "rag-pipeline-v1",
        retrieval_fn: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
    ):
        super().__init__(provider=provider, model=model)
        self._retrieval_fn = retrieval_fn

    async def _call_model(
        self,
        *,
        prompt: str,
        temperature: float,
        extra: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        if not self._retrieval_fn:
            raise AdapterError("No retrieval function configured")

        try:
            documents = self._retrieval_fn(prompt)
            # Wrap retrieval results in governance-compatible format
            result = {
                "documents": documents[:10],  # cap for safety
                "query": prompt[:500],
                "document_count": len(documents),
            }
            meta = {
                "adapter": "retrieval",
                "model": self.model,
                "document_count": len(documents),
                "provenance": "retrieval_pipeline",
            }
            return json.dumps(result), meta
        except Exception as e:
            raise AdapterError(f"Retrieval pipeline error: {e}") from e
