# src/ecosphere/consensus/adapters/grok_adapter.py
"""Grok (xAI) Adapter — V8 Validator role.

Uses xAI's OpenAI-compatible chat/completions endpoint.
Default role: independent validator for consensus.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from .base import ModelAdapter, AdapterError, AdapterAuth


class GrokAdapter(ModelAdapter):
    """Adapter for xAI Grok models."""

    provider = "grok"

    def __init__(self, *, provider: str = "grok", model: str = "grok-2"):
        super().__init__(provider=provider, model=model)
        self._api_key = os.environ.get("XAI_API_KEY", "")
        self._base_url = os.environ.get("XAI_API_URL", "https://api.x.ai/v1")

    async def _call_model(
        self, *, prompt: str, temperature: float, extra: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        if not self._api_key:
            raise AdapterAuth("XAI_API_KEY not set")

        try:
            import httpx
        except ImportError:
            raise AdapterError("httpx required for Grok adapter: pip install httpx")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": extra.get("max_tokens", 1024),
        }
        if "system" in extra:
            payload["messages"].insert(0, {"role": "system", "content": extra["system"]})

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload,
            )

        if resp.status_code == 401:
            raise AdapterAuth("Grok API authentication failed")
        if resp.status_code != 200:
            raise AdapterError(f"Grok API error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        meta = {
            "adapter": "grok", "model": self.model,
            "usage": data.get("usage", {}), "role": "validator",
        }
        return text, meta
