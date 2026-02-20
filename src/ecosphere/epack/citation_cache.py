"""
Replayable citation cache for TEK/EPACK.

Store resolved citations as EPACK events with deterministic keys so:
- first run hits network (via Commons citation resolver)
- future replays do NOT hit network; they read the same resolved metadata
- audit artifacts can prove exactly what was cited and when

This is intentionally storage-agnostic: you can back it with postgres_store or a file store.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import hashlib
import json
import time

def citation_key(kind: str, identifier: str) -> str:
    h = hashlib.sha256(f"{kind}:{identifier}".encode("utf-8")).hexdigest()
    return h[:16]

def cache_citation(store, citation: Dict[str, Any]) -> str:
    """
    store: object with append(event: dict) and get_by_key(key: str) -> Optional[dict]
    citation: dict from Commons (id/kind/identifier/title/authors/year/venue/url/raw)
    """
    key = citation.get("id") or citation_key(citation.get("kind",""), citation.get("identifier",""))
    event = {
        "type": "citation_cache",
        "key": key,
        "ts": int(time.time()),
        "citation": citation,
        "meta_hash": hashlib.sha256(json.dumps(citation, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
    }
    # idempotent write: if exists, don't duplicate
    if hasattr(store, "get_by_key"):
        existing = store.get_by_key(key)
        if existing:
            return key
    store.append(event)
    return key

def get_cached_citation(store, key: str) -> Optional[Dict[str, Any]]:
    if not hasattr(store, "get_by_key"):
        return None
    ev = store.get_by_key(key)
    if not ev:
        return None
    return ev.get("citation")
