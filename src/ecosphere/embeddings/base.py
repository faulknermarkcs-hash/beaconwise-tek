from __future__ import annotations

from typing import List


class Embedder:
    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        raise NotImplementedError
