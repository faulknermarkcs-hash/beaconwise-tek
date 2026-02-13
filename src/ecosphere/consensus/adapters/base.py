# src/ecosphere/consensus/adapters/base.py
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Tuple


class AdapterError(RuntimeError):
    pass

class AdapterAuth(AdapterError):
    pass

class AdapterTimeout(AdapterError):
    pass

class AdapterRateLimit(AdapterError):
    pass

class AdapterTransient(AdapterError):
    pass


class ModelAdapter:
    provider: str = "base"

    def __init__(self, *, provider: str, model: str):
        self.provider = provider
        self.model = model

    async def _call_model(
        self,
        *,
        prompt: str,
        temperature: float,
        extra: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        raise NotImplementedError

    async def generate_text(
        self,
        *,
        prompt: str,
        temperature: float = 0.0,
        timeout_s: int = 60,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        extra = extra or {}
        try:
            return await asyncio.wait_for(
                self._call_model(prompt=prompt, temperature=temperature, extra=extra),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as e:
            raise AdapterTimeout(f"Adapter call timed out after {timeout_s}s") from e

    def try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except Exception:
            # try to extract first JSON object
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    return None
        return None
