from __future__ import annotations

import json

from ecosphere.providers.base import GenerationConfig, GenerationResult, LLMProvider


class MockProvider(LLMProvider):
    def generate(self, prompt: str, cfg: GenerationConfig) -> GenerationResult:
        # PR6: Mock returns strict JSON to satisfy schema validation.
        user_text = prompt.split("USER:\n", 1)[-1].strip()

        obj = {
            "text": f"TDM: (mock) {user_text[:400]}",
            "disclosure": "mock_provider",
            "citations": [],
            "assumptions": [],
        }
        text = json.dumps(obj, ensure_ascii=False)
        return GenerationResult(text=text, provider="mock", model=cfg.model, usage={"tokens": 0})
