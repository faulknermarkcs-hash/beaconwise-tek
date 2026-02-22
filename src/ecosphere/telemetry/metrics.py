"""ecosphere.telemetry.metrics — Brick 9 metrics helpers.

These utilities are pure/deterministic and safe to include in EPACK payloads.
They do not do network IO.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class DisagreementMetrics:
    similarity: float
    disagreement: float
    method: str = "token_jaccard"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _tokenize(s: str) -> set[str]:
    toks = []
    for w in (s or "").lower().split():
        w = "".join(ch for ch in w if ch.isalnum())
        if w:
            toks.append(w)
    return set(toks)


def token_jaccard(a: str, b: str) -> DisagreementMetrics:
    A = _tokenize(a)
    B = _tokenize(b)
    if not A and not B:
        return DisagreementMetrics(similarity=1.0, disagreement=0.0)
    if not A or not B:
        return DisagreementMetrics(similarity=0.0, disagreement=1.0)
    inter = len(A & B)
    union = len(A | B)
    sim = inter / union if union else 0.0
    return DisagreementMetrics(similarity=float(sim), disagreement=float(1.0 - sim))


def summarize_latency(meta: Dict[str, Any]) -> Optional[int]:
    for k in ("latency_ms", "total_ms", "duration_ms"):
        v = meta.get(k) if isinstance(meta, dict) else None
        if isinstance(v, (int, float)):
            return int(v)
    return None
