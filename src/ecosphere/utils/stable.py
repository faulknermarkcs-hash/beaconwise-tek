"""Stable hashing utilities — deterministic, algorithm-agile.

Provides canonical JSON serialization and cryptographic hashing with
algorithm agility as required by SECURITY_MODEL.md §4.2.

Current default: SHA-256
Supported: SHA-256, SHA-384, SHA-512
Migration: Change HASH_ALGORITHM or set ECOSPHERE_HASH_ALGORITHM env var.
Chain continuity: Algorithm identifier is embedded in extended hashes
via stable_hash_tagged() for forward-compatible chains.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

# Algorithm registry — add new algorithms here
_ALGORITHMS = {
    "sha256": hashlib.sha256,
    "sha384": hashlib.sha384,
    "sha512": hashlib.sha512,
}

# Default algorithm (overridable via environment)
HASH_ALGORITHM: str = os.environ.get("ECOSPHERE_HASH_ALGORITHM", "sha256")


def _get_hasher(algorithm: str = ""):
    """Get hash function by name. Raises ValueError for unknown algorithms."""
    algo = algorithm or HASH_ALGORITHM
    if algo not in _ALGORITHMS:
        raise ValueError(
            f"Unsupported hash algorithm: {algo!r}. "
            f"Supported: {', '.join(sorted(_ALGORITHMS))}"
        )
    return _ALGORITHMS[algo]


def stable_json(obj: Any) -> str:
    """Canonical JSON: sorted keys, no whitespace, UTF-8 safe."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(obj: Any, *, algorithm: str = "") -> str:
    """Deterministic hash of any JSON-serializable object.

    Default algorithm: SHA-256 (backward compatible).
    Override per-call with algorithm= or globally via ECOSPHERE_HASH_ALGORITHM.
    """
    s = stable_json(obj)
    h = _get_hasher(algorithm)
    return h(s.encode("utf-8")).hexdigest()


def stable_hash_tagged(obj: Any, *, algorithm: str = "") -> str:
    """Hash with algorithm tag prefix for forward-compatible chains.

    Returns: "algo:hexdigest" (e.g., "sha256:a1b2c3...")

    Use this for new chain formats where algorithm migration must be
    detectable without out-of-band metadata.
    """
    algo = algorithm or HASH_ALGORITHM
    digest = stable_hash(obj, algorithm=algo)
    return f"{algo}:{digest}"


def verify_tagged_hash(obj: Any, tagged: str) -> bool:
    """Verify an algorithm-tagged hash."""
    if ":" not in tagged:
        # Legacy untagged hash — assume SHA-256
        return stable_hash(obj, algorithm="sha256") == tagged
    algo, expected = tagged.split(":", 1)
    return stable_hash(obj, algorithm=algo) == expected


def hash_suffix(h: str, n: int = 4) -> str:
    """Last n characters of a hash (for display)."""
    if not h:
        return ""
    # Handle tagged hashes
    if ":" in h:
        h = h.split(":", 1)[1]
    return h[-n:]


def supported_algorithms() -> list:
    """List supported hash algorithms."""
    return sorted(_ALGORITHMS.keys())
