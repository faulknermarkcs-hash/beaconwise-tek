# src/ecosphere/consensus/adapters/anthropic_adapter.py
from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from .base import ModelAdapter, AdapterError, AdapterTimeout, AdapterRateLimit, AdapterAuth, AdapterTransient


class AnthropicAdapter(ModelAdapter):
    provider = "anthropic"

    def __init__(self, *, provider: str, model: str):
        super().__init__(provider=provider, model=model)
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise AdapterAuth("ANTHROPIC_API_KEY not set in environment")
        self._api_key = api_key
        self._client = None  # lazy init

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from anthropic import AsyncAnthropic
        except Exception as e:
            raise AdapterError("anthropic SDK not installed (pip install anthropic)") from e
        self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def _call_model(
        self,
        *,
        prompt: str,
        temperature: float,
        extra: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        client = self._get_client()
        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=extra.get("max_tokens", 2048),
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                **extra.get("kwargs", {}),
            )
            # anthropic content blocks
            content = ""
            if getattr(response, "content", None):
                try:
                    content = response.content[0].text
                except Exception:
                    content = str(response.content)
            meta = {
                "request_id": getattr(response, "id", None),
                "usage": {
                    "prompt_tokens": getattr(getattr(response, "usage", None), "input_tokens", None),
                    "completion_tokens": getattr(getattr(response, "usage", None), "output_tokens", None),
                },
            }
            return content, meta
        except Exception as e:
            msg = str(e).lower()
            if "rate" in msg and "limit" in msg:
                raise AdapterRateLimit(str(e)) from e
            if "auth" in msg or "api key" in msg or "unauthorized" in msg:
                raise AdapterAuth(str(e)) from e
            if "timeout" in msg:
                raise AdapterTimeout(str(e)) from e
            raise AdapterTransient(str(e)) from e
