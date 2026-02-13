from __future__ import annotations

import hashlib
from typing import List

from ecosphere.embeddings.base import Embedder


class LocalDeterministicEmbedder(Embedder):
    """
    Deterministic pseudo-embeddings for reproducible tests.
    IMPORTANT: emit signed, roughly zero-mean values to prevent
    cosine similarity from being artificially high.
    """
    def embed(self, texts: List[str], model: str) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            # map bytes -> [-0.5, +0.5] approximately
            vec = [(b / 255.0) - 0.5 for b in h[:64]]  # 64 dims helps stability
            out.append(vec)
        return out
