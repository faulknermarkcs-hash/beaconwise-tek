from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ecosphere.utils.stable import stable_hash


@dataclass(frozen=True)
class EPACK:
    """Replayable audit record.

    Brick 3 alignment:
      - payload_hash is the cryptographic commitment to the governed Decision Object
        (Decision canonical sha256 hash), when available.
      - hash is the EPACK chain record hash (stable_hash over header + payload + payload_hash).
    """
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
    """Create a new EPACK record.

    If payload_hash_override is provided, it becomes `payload_hash`.
    Otherwise, we default to:
      - payload.get("decision_hash") when present
      - else stable_hash(payload)

    This allows TEK to interoperate with Commons Brick 3 semantics where the
    audit chain commits to the Decision Object hash.
    """
    ts = time.time()

    if payload_hash_override:
        payload_hash = str(payload_hash_override)
    else:
        payload_hash = str(payload.get("decision_hash") or stable_hash(payload))

    h = stable_hash(
        {
            "seq": seq,
            "ts": ts,
            "prev_hash": prev_hash,
            "payload_hash": payload_hash,
            "payload": payload,
        }
    )
    return EPACK(seq=seq, ts=ts, prev_hash=prev_hash, payload_hash=payload_hash, payload=payload, hash=h)
