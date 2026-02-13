from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional

from ecosphere.consensus.ledger.reader import append_event


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def emit_stage_event(
    *,
    epack: str,
    run_id: str,
    stage: str,
    payload: Dict[str, Any],
    prev_hash: Optional[str] = None,
) -> str:
    """Append a stage event to the (dev) EPACK store and return event hash.

    Production note: replace reader.append_event with your immutable ledger sink.
    """
    ts_ms = int(time.time() * 1000)
    core = {
        "run_id": run_id,
        "epack": epack,
        "stage": stage,
        "ts_ms": ts_ms,
        "payload": payload,
    }
    event_hash = hashlib.sha256(_canonical_json(core).encode("utf-8")).hexdigest()
    event = {**core, "event_hash": event_hash, "prev_hash": prev_hash}
    append_event(epack, event)
    return event_hash
