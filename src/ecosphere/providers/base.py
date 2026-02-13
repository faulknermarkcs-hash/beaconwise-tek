from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class GenerationConfig:
    model: str
    temperature: float = 0.0
    max_tokens: int = 800


@dataclass(frozen=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    usage: Dict[str, Any]


class LLMProvider:
    def generate(self, prompt: str, cfg: GenerationConfig) -> GenerationResult:
        raise NotImplementedError
