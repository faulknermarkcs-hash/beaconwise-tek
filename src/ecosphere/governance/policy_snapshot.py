from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def current_policy_snapshot() -> Dict[str, Any]:
    """
    Brick 7: Policy version pinning.

    Returns a deterministic snapshot suitable for EPACK payloads and Decision Objects:
      - policy_id
      - policy_version
      - policy_sha256
      - policy_path

    If the policy file is missing/unreadable, returns unknown fields with error.
    """
    path = os.getenv("BW_POLICY_PATH") or os.getenv("COMMONS_POLICY_PATH") or "policies/default.yaml"
    p = Path(path)
    try:
        raw = p.read_bytes()
        sha = _sha256_bytes(raw)
        obj = yaml.safe_load(raw.decode("utf-8")) or {}
        if not isinstance(obj, dict):
            raise ValueError("policy YAML must be a mapping")
        pid = str(obj.get("policy_id") or p.stem)
        pver = str(obj.get("policy_version") or obj.get("version") or "0")
        return {
            "policy_id": pid,
            "policy_version": pver,
            "policy_sha256": sha,
            "policy_path": str(p),
        }
    except Exception as e:
        return {
            "policy_id": "unknown",
            "policy_version": "unknown",
            "policy_sha256": None,
            "policy_path": str(p),
            "policy_error": f"{type(e).__name__}: {e}",
        }
