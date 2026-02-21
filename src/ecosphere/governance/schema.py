# src/ecosphere/governance/schema.py
"""BeaconWise Interoperable Governance Schema Standard (V7 Capability 4).

Defines the open, versioned governance data standard:
  - EPACK interoperability schema
  - audit chain data format
  - governance telemetry standard
  - routing proof metadata specification
  - backward compatibility rules

Principle: Standards spread through interoperability.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ecosphere.utils.stable import stable_hash


# ── Schema Version ────────────────────────────────────────────────

SCHEMA_VERSION = "1.0.0"
SCHEMA_FAMILY = "beaconwise-governance"


# ── EPACK Interoperability Schema ─────────────────────────────────

EPACK_SCHEMA = {
    "schema": f"{SCHEMA_FAMILY}/epack",
    "version": SCHEMA_VERSION,
    "fields": {
        "seq": {"type": "integer", "required": True, "description": "Monotonic sequence number"},
        "ts": {"type": "float", "required": True, "description": "Unix timestamp"},
        "prev_hash": {"type": "string", "required": True, "description": "Hash of previous record (GENESIS for first)"},
        "payload_hash": {
            "type": "string",
            "required": True,
            "description": "Brick 3: commitment hash (Decision canonical sha256) when available; otherwise payload-derived hash"
        },
        "hash": {"type": "string", "required": True, "description": "EPACK chain hash (stable_hash over header + payload + payload_hash)"},
        "payload": {"type": "object", "required": True, "description": "Replayable payload (may include decision_hash + decision_object)"},
    },
}


def validate_epack_record(rec: Dict[str, Any]) -> List[str]:
    """Lightweight schema validator. Returns list of errors."""
    errors: List[str] = []
    for k, spec in EPACK_SCHEMA["fields"].items():
        if spec.get("required") and k not in rec:
            errors.append(f"missing required field: {k}")
    return errors


def epack_record_hash(rec: Dict[str, Any]) -> str:
    """Compute EPACK chain hash for an EPACK dict record."""
    return stable_hash(rec)
