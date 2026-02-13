from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

from ecosphere.utils.stable import stable_hash


@dataclass(frozen=True)
class EPACK:
    seq: int
    ts: float
    prev_hash: str
    payload: Dict[str, Any]
    hash: str


def new_epack(seq: int, prev_hash: str, payload: Dict[str, Any]) -> EPACK:
    ts = time.time()
    h = stable_hash({"seq": seq, "ts": ts, "prev_hash": prev_hash, "payload": payload})
    return EPACK(seq=seq, ts=ts, prev_hash=prev_hash, payload=payload, hash=h)
