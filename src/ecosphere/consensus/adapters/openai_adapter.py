# src/ecosphere/consensus/adapters/openai_adapter.py
from __future__ import annotations

import os
from typing import Any, Dict, Tuple, Optional

from .base import ModelAdapter, AdapterError, AdapterTimeout, AdapterRateLimit, AdapterAuth, AdapterTransient


class OpenAIAdapter(ModelAdapter):
    provider = "openai"

    def __init__(self, *, provider: str, model: str):
        super().__init__(provider=provider, model=model)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise AdapterAuth("OPENAI_API_KEY not set in environment")
        self._api_key = api_key
        self._client = None  # lazy init

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import AsyncOpenAI
        except Exception as e:
            raise AdapterError("openai SDK not installed (pip install openai)") from e
        self._client = AsyncOpenAI(api_key=self._api_key)
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
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=extra.get("max_tokens", 2048),
                **extra.get("kwargs", {}),
            )
            content = response.choices[0].message.content or ""
            meta = {
                "request_id": getattr(response, "id", None),
                "usage": response.usage.model_dump() if getattr(response, "usage", None) else None,
            }
            return content, meta
        except Exception as e:
            # Avoid importing exception types to keep CI light.
            msg = str(e).lower()
            if "rate" in msg and "limit" in msg:
                raise AdapterRateLimit(str(e)) from e
            if "auth" in msg or "api key" in msg or "unauthorized" in msg:
                raise AdapterAuth(str(e)) from e
            if "timeout" in msg:
                raise AdapterTimeout(str(e)) from e
            raise AdapterTransient(str(e)) from e
