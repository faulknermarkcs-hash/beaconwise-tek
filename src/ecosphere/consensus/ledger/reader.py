# src/ecosphere/consensus/ledger/reader.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


"""EPACK event reader/writer for TE-CL.

This module is intentionally lightweight:
  - It keeps a small in-memory cache for Streamlit + tests.
  - It also persists events as JSONL on disk for demo realism.

Production deployments should replace this with a durable store
(SQLite/Postgres/S3/WORM logs) and proper concurrency controls.
"""


# In-memory store: epack_id -> list of events
_EPACK_EVENTS: Dict[str, List[Dict[str, Any]]] = {}


def _base_dir() -> Path:
    """Directory for persisted TE-CL EPACK JSONL logs."""
    # Allow override; default is a local hidden folder.
    base = os.getenv("TECL_EPACK_DIR", ".ecosphere_tecl_epacks")
    return Path(base)


def _epack_file(epack_id: str) -> Path:
    safe = "".join(ch for ch in epack_id if ch.isalnum() or ch in ("-", "_"))[:120]
    return _base_dir() / f"{safe}.jsonl"


def append_event(epack_id: str, event: Dict[str, Any]) -> None:
    """Append an event to in-memory cache and persist to disk (best-effort)."""
    _EPACK_EVENTS.setdefault(epack_id, []).append(event)

    # Best-effort persistence (never fail the caller).
    try:
        base = _base_dir()
        base.mkdir(parents=True, exist_ok=True)
        path = _epack_file(epack_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        # Ignore persistence failures in dev/demo.
        return


def clear_epack(epack_id: str) -> None:
    """Clear in-memory and on-disk events for a given EPACK id (test helper)."""
    _EPACK_EVENTS.pop(epack_id, None)
    try:
        path = _epack_file(epack_id)
        if path.exists():
            path.unlink()
    except Exception:
        return


def clear_epack_events_for_test() -> None:
    """Test helper: clear all in-memory events and purge on-disk files.

    This keeps tests deterministic when EPACK persistence is enabled.
    """
    _EPACK_EVENTS.clear()
    try:
        base = _base_dir()
        if base.exists():
            for p in base.glob("*.jsonl"):
                try:
                    p.unlink()
                except Exception:
                    pass
    except Exception:
        pass


# Backwards-compatible aliases (older test bundles)
def clear_events() -> None:  # pragma: no cover
    clear_epack_events_for_test()


def _reset_events_for_test() -> None:  # pragma: no cover
    clear_epack_events_for_test()



def _read_last_jsonl(path: Path, limit: int) -> List[Dict[str, Any]]:
    """Read up to last `limit` JSONL records from file."""
    if limit <= 0 or not path.exists():
        return []

    # For small demo files it's fine to read all lines.
    # If this grows, swap for a tail implementation.
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


def get_recent_events(
    epack_id: str,
    stage_prefix: str = "tecl.",
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Return most recent events matching a stage prefix.

    Prefers on-disk JSONL (for Streamlit realism), falls back to in-memory.
    Returned events are ordered newest-first.
    """
    if limit <= 0:
        return []

    path = _epack_file(epack_id)
    events: List[Dict[str, Any]]
    if path.exists():
        events = _read_last_jsonl(path, limit=200)  # read a bit more to allow filtering
    else:
        events = list(reversed(_EPACK_EVENTS.get(epack_id, [])))

    matching = [e for e in events if str(e.get("stage", "")).startswith(stage_prefix)]
    return matching[:limit]
