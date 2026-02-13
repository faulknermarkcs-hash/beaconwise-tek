# src/ecosphere/consensus/adapters/factory.py
from __future__ import annotations

from typing import Dict, Type

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


def get_registered_providers() -> list:
    """Return list of registered adapter provider names."""
    return list(_ADAPTER_REGISTRY.keys())

def build_adapter(spec: ModelSpec) -> ModelAdapter:
    cls = _ADAPTER_REGISTRY.get(spec.provider)
    if not cls:
        raise ValueError(f"No adapter registered for provider={spec.provider}")
    return cls(provider=spec.provider, model=spec.model)
