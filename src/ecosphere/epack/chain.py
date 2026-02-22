from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ecosphere.utils.stable import stable_hash


@dataclass(frozen=True)
class EPACK:
    seq: int
    ts: float
    prev_hash: str
    payload_hash: str
    payload: Dict[str, Any]
    hash: str


def new_epack(
    seq: int,
    prev_hash: str,
    payload: Dict[str, Any],
    *,
    payload_hash_override: Optional[str] = None,
) -> EPACK:
    """Create a new EPACK block.

    Brick 3+ semantics:
      - payload_hash is the stable hash of the payload (or an override)
      - epack hash chains {seq, ts, prev_hash, payload_hash} (not full payload)
        to avoid replay brittleness and keep the chain deterministic even if
        payload includes large nested structures.

    Back-compat:
      - callers who don't care can keep calling new_epack(seq, prev_hash, payload)
    """
    ts = time.time()
    payload_hash = payload_hash_override or stable_hash(payload)

    h = stable_hash(
        {
            "seq": seq,
            "ts": ts,
            "prev_hash": prev_hash,
            "payload_hash": payload_hash,
        }
    )
    return EPACK(seq=seq, ts=ts, prev_hash=prev_hash, payload_hash=payload_hash, payload=payload, hash=h)
