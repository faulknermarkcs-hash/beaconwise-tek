# src/ecosphere/consensus/adapters/groq_adapter.py
"""Groq Compound Beta Adapter — V8 Challenger role.

Uses Groq's OpenAI-compatible endpoint with JSON response mode.
Compound Beta is Groq's multi-model routing — fast + cost-effective
for structured adversarial critique (ChallengePack).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from .base import ModelAdapter, AdapterError, AdapterAuth


class GroqAdapter(ModelAdapter):
    """Adapter for Groq models (default: challenger role)."""

    provider = "groq"

    def __init__(self, *, provider: str = "groq", model: str = "compound-beta"):
        super().__init__(provider=provider, model=model)
        self._api_key = os.environ.get("GROQ_API_KEY", "")
        self._base_url = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1")

    async def _call_model(
        self, *, prompt: str, temperature: float, extra: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        if not self._api_key:
            raise AdapterAuth("GROQ_API_KEY not set")

        try:
            import httpx
        except ImportError:
            raise AdapterError("httpx required for Groq adapter: pip install httpx")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": extra.get("max_tokens", 400),
            "response_format": {"type": "json_object"},
        }
        if "system" in extra:
            payload["messages"].insert(0, {"role": "system", "content": extra["system"]})

        timeout = extra.get("timeout_s", 10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload,
            )

        if resp.status_code == 401:
            raise AdapterAuth("Groq API authentication failed")
        if resp.status_code != 200:
            raise AdapterError(f"Groq API error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        meta = {
            "adapter": "groq", "model": self.model,
            "usage": data.get("usage", {}), "role": "challenger",
        }
        return text, meta
