# src/ecosphere/consensus/adapters/factory.py
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Type, Tuple

from ecosphere.consensus.config import ModelSpec
from .base import ModelAdapter
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .mock_adapter import MockAdapter
from .symbolic_adapter import SymbolicAdapter
from .retrieval_adapter import RetrievalAdapter
from .grok_adapter import GrokAdapter
from .groq_adapter import GroqAdapter

_ADAPTER_REGISTRY: Dict[str, Type[ModelAdapter]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "mock": MockAdapter,
    "symbolic": SymbolicAdapter,
    "retrieval": RetrievalAdapter,
    "grok": GrokAdapter,
    "groq": GroqAdapter,
}


def get_registered_providers() -> list[str]:
    """Return list of registered adapter provider names."""
    return list(_ADAPTER_REGISTRY.keys())


@lru_cache(maxsize=64)
def _build_cached(provider: str, model: str) -> ModelAdapter:
    cls = _ADAPTER_REGISTRY.get(provider)
    if not cls:
        raise ValueError(f"No adapter registered for provider={provider}")
    return cls(provider=provider, model=model)


def build_adapter(spec: ModelSpec) -> ModelAdapter:
    """Build (and cache) an adapter for the given ModelSpec.

    Caching reduces per-turn latency by avoiding repeated client init /
    auth / TLS setup where adapters hold SDK clients.
    """
    return _build_cached(spec.provider, spec.model)
