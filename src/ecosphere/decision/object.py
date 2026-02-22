from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timezone
import hashlib
import json
import uuid


SCHEMA_ID = "beaconwise-governance/decision"
SCHEMA_VERSION = 1


def _canonical_dumps(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _hash_text(s: str) -> str:
    return _sha256_hex((s or "").encode("utf-8"))


def build_decision_object(
    *,
    session_id: str,
    payload: Dict[str, Any],
    assistant_text: str,
    build_manifest: Dict[str, Any],
    policy_snapshot: Optional[Dict[str, Any]] = None,
    profile: Optional[str] = None,
    prev_decision_hash: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Build Decision Object v1 for TEK.

    Canonical hash rule:
      sha256(canonical_json(decision with integrity.canonical_payload_hash="")).

    TEK doesn’t always have a workspace_id/user_id at this layer, so we keep context minimal.
    """
    decision: Dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "decision_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),

        "context": {
            "session_id": session_id,
            "workspace_id": None,
            "user_id": None,
            "profile": profile,
        },

        "input": {
            "prompt_hash": _hash_text(str(payload.get("prompt") or "")),
            "attachments": payload.get("attachments") or [],
        },

        "routing": payload.get("routing") or {
            "mode": payload.get("mode") or "Balanced",
            "strategy": payload.get("strategy") or "Balanced",
            "providers": payload.get("providers") or [],
        },

        "policy": payload.get("policy") or {
            "policy_id": payload.get("policy_id") or "tek",
            "policy_hash": _sha256_hex(_canonical_dumps(payload.get("policy") or {})),
            "profile": profile,
            "constraints_applied": payload.get("constraints_applied") or [],
        },

        "stages": payload.get("stages") or {},

        "output": {
            "final_text_hash": _hash_text(assistant_text),
            "final_format": payload.get("final_format"),
            "confidence": payload.get("confidence"),
            "dissent": payload.get("dissent") or {},
        },

        "integrity": {
            "canonical_payload_hash_alg": "sha256",
            "canonical_payload_hash": "",
            "prev_decision_hash": prev_decision_hash,
            "epack_block_hash": None,
        },

        "build": {
            "kernel": "tek-kernel",
            "kernel_version": str(build_manifest.get("kernel_version") or build_manifest.get("version") or "unknown"),
            "manifest_hash": _sha256_hex(_canonical_dumps(build_manifest)),
        },
    }

    decision_for_hash = json.loads(_canonical_dumps(decision).decode("utf-8"))
    decision_for_hash["integrity"]["canonical_payload_hash"] = ""
    decision_hash = _sha256_hex(_canonical_dumps(decision_for_hash))

    decision["integrity"]["canonical_payload_hash"] = decision_hash
    return decision, decision_hash
