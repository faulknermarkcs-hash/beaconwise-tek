# src/ecosphere/providers/factory.py
from __future__ import annotations

from functools import lru_cache
import os

from ecosphere.config import Settings
from ecosphere.providers.base import GenerationConfig, GenerationResult, LLMProvider
from ecosphere.providers.mock import MockProvider


def _require_env(key: str) -> str:
    v = os.getenv(key, "").strip()
    if not v:
        raise RuntimeError(
            f"Missing required environment variable: {key}. "
            f"Set it in Render -> Service -> Environment."
        )
    return v


_SYSTEM_PROMPT = "You are the Transparency Ecosphere Kernel. Follow the prompt rules exactly."


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str):
        try:
            from groq import Groq  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Groq provider selected but 'groq' package is not installed. "
                "Add 'groq' to requirements.txt."
            ) from e

        self._client = Groq(api_key=api_key)

    def generate(self, prompt: str, cfg: GenerationConfig) -> GenerationResult:
        resp = self._client.chat.completions.create(
            model=str(cfg.model),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": str(prompt)},
            ],
            temperature=float(cfg.temperature),
            max_tokens=int(cfg.max_tokens),
        )

        text = ""
        try:
            text = resp.choices[0].message.content or ""
        except Exception:
            text = ""

        usage: dict = {}
        u = getattr(resp, "usage", None)
        if u is not None:
            usage = {
                "prompt_tokens": getattr(u, "prompt_tokens", None),
                "completion_tokens": getattr(u, "completion_tokens", None),
                "total_tokens": getattr(u, "total_tokens", None),
            }

        return GenerationResult(text=text, provider="groq", model=str(cfg.model), usage=usage)


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str):
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "OpenAI provider selected but 'openai' package is not installed. "
                "Add 'openai' to requirements.txt."
            ) from e

        self._client = OpenAI(api_key=api_key)

    def generate(self, prompt: str, cfg: GenerationConfig) -> GenerationResult:
        resp = self._client.chat.completions.create(
            model=str(cfg.model),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": str(prompt)},
            ],
            temperature=float(cfg.temperature),
            max_tokens=int(cfg.max_tokens),
        )

        text = ""
        try:
            text = resp.choices[0].message.content or ""
        except Exception:
            text = ""

        usage: dict = {}
        u = getattr(resp, "usage", None)
        if u is not None:
            usage = {
                "prompt_tokens": getattr(u, "prompt_tokens", None),
                "completion_tokens": getattr(u, "completion_tokens", None),
                "total_tokens": getattr(u, "total_tokens", None),
            }

        return GenerationResult(text=text, provider="openai", model=str(cfg.model), usage=usage)


@lru_cache(maxsize=1)
def make_llm_provider() -> LLMProvider:
    """
    Provider selection via Settings.PROVIDER (ECOSPHERE_PROVIDER):
      - mock   (default)
      - groq   (requires GROQ_API_KEY, pip install groq)
      - openai (requires OPENAI_API_KEY, pip install openai)
    """
    p = (Settings.PROVIDER or "mock").lower().strip()

    if p == "mock":
        return MockProvider()

    if p == "groq":
        api_key = _require_env("GROQ_API_KEY")
        return GroqProvider(api_key=api_key)

    if p == "openai":
        api_key = _require_env("OPENAI_API_KEY")
        return OpenAIProvider(api_key=api_key)

    raise RuntimeError(f"Unknown ECOSPHERE_PROVIDER='{p}'. Use: mock | groq | openai")