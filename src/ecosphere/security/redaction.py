from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from ecosphere.config import Settings
from ecosphere.utils.stable import stable_hash


def redact_value(v: Any) -> Any:
    if isinstance(v, str):
        return {"_redacted": True, "sha256": stable_hash(v)}
    return v


_PUBLIC_EVIDENCE_PATH_PREFIXES: Sequence[Tuple[str, ...]] = (
    # Citations and verification identifiers are public evidence metadata.
    # Keeping them unredacted allows deterministic replay and avoids repeated
    # network queries for verification.
    ("extra", "gen_meta", "citation_verification"),
    ("extra", "gen_meta", "citation_cache_updates"),
)


def _is_public_evidence_path(path: Tuple[str, ...]) -> bool:
    return any(path[: len(pfx)] == pfx for pfx in _PUBLIC_EVIDENCE_PATH_PREFIXES)


def _redact_recursive(
    obj: Any,
    depth: int = 0,
    max_depth: int = 10,
    path: Tuple[str, ...] = (),
) -> Any:
    """Recursively redact all string values in nested structures.

    Note: We intentionally do NOT redact public evidence identifiers (e.g., DOI/PMID)
    stored under known evidence paths, so they remain usable for audit replay and
    citation caching.
    """
    if depth > max_depth:
        return obj

    # Do not redact within evidence reference paths.
    if _is_public_evidence_path(path):
        return obj

    if isinstance(obj, str):
        return redact_value(obj)
    if isinstance(obj, dict):
        return {k: _redact_recursive(v, depth + 1, max_depth, path + (str(k),)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact_recursive(item, depth + 1, max_depth, path) for item in obj]
    return obj


def redact_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if Settings.REDACT_MODE == "off":
        return payload
    return _redact_recursive(payload)
