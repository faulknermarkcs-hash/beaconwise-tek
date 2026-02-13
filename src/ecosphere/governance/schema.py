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
        "prev_hash": {"type": "string", "required": True, "description": "SHA-256 hash of previous record (GENESIS for first)"},
        "hash": {"type": "string", "required": True, "description": "SHA-256 hash of {seq, ts, prev_hash, payload}"},
        "payload": {"type": "object", "required": True, "description": "Governed interaction data"},
    },
    "payload_fields": {
        "interaction": {"type": "integer", "required": True},
        "profile": {"type": "string", "required": True, "enum": ["A_FAST", "A_STANDARD", "A_HIGH_ASSURANCE"]},
        "user_text_hash": {"type": "string", "required": True},
        "assistant_text_hash": {"type": "string", "required": True},
        "pending_gate": {"type": "object", "required": True},
        "traces_tail": {"type": "array", "required": True},
        "tsv_snapshot": {"type": "object", "required": True},
        "build_manifest": {"type": "object", "required": True},
        "extra": {"type": "object", "required": False},
    },
    "hash_algorithm": "sha256",
    "serialization": "canonical-json-sorted-keys-no-whitespace",
}


# ── Governance Telemetry Schema ───────────────────────────────────

TELEMETRY_SCHEMA = {
    "schema": f"{SCHEMA_FAMILY}/telemetry",
    "version": SCHEMA_VERSION,
    "event_fields": {
        "event_type": {"type": "string", "required": True},
        "timestamp": {"type": "float", "required": True},
        "session_id": {"type": "string", "required": True},
        "epack_seq": {"type": "integer", "required": True},
        "route": {"type": "string", "required": False},
        "profile": {"type": "string", "required": False},
        "safety_stage1_ok": {"type": "boolean", "required": False},
        "safety_stage2_ok": {"type": "boolean", "required": False},
        "scope_gate_decision": {"type": "string", "required": False},
        "validation_ok": {"type": "boolean", "required": False},
        "latency_ms": {"type": "float", "required": False},
    },
}


# ── Routing Proof Metadata Schema ─────────────────────────────────

ROUTING_PROOF_SCHEMA = {
    "schema": f"{SCHEMA_FAMILY}/routing-proof",
    "version": SCHEMA_VERSION,
    "fields": {
        "input_hash": {"type": "string", "required": True},
        "route_sequence": {"type": "array", "required": True},
        "route_reason": {"type": "string", "required": True},
        "safety_stage1_ok": {"type": "boolean", "required": True},
        "safety_stage2_ok": {"type": "boolean", "required": True},
        "safety_stage2_score": {"type": "float", "required": True},
        "domain": {"type": "string", "required": True},
        "complexity": {"type": "integer", "required": True},
        "profile": {"type": "string", "required": True},
        "timestamp": {"type": "float", "required": True},
    },
}


# ── Governance Receipt Schema ─────────────────────────────────────

RECEIPT_SCHEMA = {
    "schema": f"{SCHEMA_FAMILY}/receipt",
    "version": SCHEMA_VERSION,
    "fields": {
        "receipt_id": {"type": "string", "required": True},
        "epack_hash": {"type": "string", "required": True},
        "routing_proof_hash": {"type": "string", "required": True},
        "manifest_hash": {"type": "string", "required": True},
        "tsv_snapshot_hash": {"type": "string", "required": True},
        "scope_gate_decision": {"type": "string", "required": True},
        "profile": {"type": "string", "required": True},
        "mode": {"type": "string", "required": True, "enum": ["lightweight", "standard", "forensic"]},
        "timestamp": {"type": "float", "required": True},
        "signature": {"type": "string", "required": True, "algorithm": "hmac-sha256"},
    },
}


# ── Schema Registry ───────────────────────────────────────────────

SCHEMA_REGISTRY: Dict[str, Dict[str, Any]] = {
    "epack": EPACK_SCHEMA,
    "telemetry": TELEMETRY_SCHEMA,
    "routing-proof": ROUTING_PROOF_SCHEMA,
    "receipt": RECEIPT_SCHEMA,
}


def get_schema(name: str) -> Optional[Dict[str, Any]]:
    """Get a schema by name."""
    return SCHEMA_REGISTRY.get(name)


def get_all_schemas() -> Dict[str, Dict[str, Any]]:
    """Get all registered schemas."""
    return dict(SCHEMA_REGISTRY)


def get_schema_version() -> str:
    return SCHEMA_VERSION


def get_schema_hash() -> str:
    """Compute hash over all schemas for compatibility checking."""
    return stable_hash(SCHEMA_REGISTRY)


# ── Validation ────────────────────────────────────────────────────

def validate_epack_record(record: Dict[str, Any]) -> List[str]:
    """Validate an EPACK record against the schema. Returns list of errors."""
    errors: List[str] = []
    for field_name, spec in EPACK_SCHEMA["fields"].items():
        if spec.get("required") and field_name not in record:
            errors.append(f"Missing required field: {field_name}")
    if "payload" in record and isinstance(record["payload"], dict):
        for field_name, spec in EPACK_SCHEMA["payload_fields"].items():
            if spec.get("required") and field_name not in record["payload"]:
                errors.append(f"Missing required payload field: {field_name}")
    return errors


def validate_telemetry_event(event: Dict[str, Any]) -> List[str]:
    """Validate a telemetry event against the schema."""
    errors: List[str] = []
    for field_name, spec in TELEMETRY_SCHEMA["event_fields"].items():
        if spec.get("required") and field_name not in event:
            errors.append(f"Missing required field: {field_name}")
    return errors


# ── Backward Compatibility ────────────────────────────────────────

COMPATIBLE_VERSIONS = ["1.0.0"]  # Versions this schema can read

def is_compatible(version: str) -> bool:
    """Check if a given schema version is backward-compatible."""
    return version in COMPATIBLE_VERSIONS
