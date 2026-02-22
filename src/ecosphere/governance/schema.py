from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

# -----------------------------------------------------------------------------
# Governance schema registry
#
# This module is used by TEK's API to expose governance/policy schemas for:
# - UI validation
# - auditor-facing schema versioning
# - policy runtime compatibility checks
#
# Brick 7+ requires these public functions:
#   - get_all_schemas()
#   - get_schema(name)
#   - get_schema_version(name)
# -----------------------------------------------------------------------------

# NOTE:
# We keep an in-memory registry so this works in Render without needing
# filesystem access or packaging data configuration. You can expand these
# schemas later or load from YAML resources, but this is a stable baseline.


@dataclass(frozen=True)
class SchemaInfo:
    name: str
    version: str
    schema: Dict[str, Any]


# -----------------------------------------------------------------------------
# Built-in baseline schemas
# -----------------------------------------------------------------------------

_POLICY_SCHEMA_V1: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TEK Governance Policy Schema",
    "type": "object",
    "required": ["policy_id", "policy_version"],
    "properties": {
        "policy_id": {"type": "string"},
        "policy_version": {"type": ["string", "number"]},

        "consensus": {"type": "object"},
        "resilience": {"type": "object"},
        "replay": {"type": "object"},
        "telemetry": {"type": "object"},
        "oversight": {"type": "object"},
        "deployment": {"type": "object"},
        "liability": {"type": "object"},
        "evidence": {"type": "object"},
        "risk_tests": {"type": "object"},
    },
    "additionalProperties": True,
}

_SCHEMA_REGISTRY: Dict[str, SchemaInfo] = {
    "policy": SchemaInfo(name="policy", version="1.0", schema=_POLICY_SCHEMA_V1),
}

# -----------------------------------------------------------------------------
# Backwards-compatible public API expected by api/main.py
# -----------------------------------------------------------------------------

def get_all_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Returns:
        dict: { schema_name: { "name":..., "version":..., "schema": {...} } }
    """
    out: Dict[str, Dict[str, Any]] = {}
    for k, info in _SCHEMA_REGISTRY.items():
        out[k] = {"name": info.name, "version": info.version, "schema": info.schema}
    return out


def get_schema(name: str) -> Dict[str, Any]:
    """
    Returns the JSON schema object for `name`.
    Raises KeyError if not found.
    """
    info = _SCHEMA_REGISTRY.get(name)
    if not info:
        raise KeyError(f"Unknown schema: {name}")
    return info.schema


def get_schema_version(name: str) -> str:
    """
    Returns the schema version string for `name`.
    Raises KeyError if not found.
    """
    info = _SCHEMA_REGISTRY.get(name)
    if not info:
        raise KeyError(f"Unknown schema: {name}")
    return info.version


# -----------------------------------------------------------------------------
# Convenience helpers (safe)
# -----------------------------------------------------------------------------

def register_schema(name: str, version: str, schema: Dict[str, Any]) -> None:
    """
    Optional helper to add schemas at runtime (dev/debug).
    """
    _SCHEMA_REGISTRY[name] = SchemaInfo(name=name, version=version, schema=schema)


def dumps_schema(name: str) -> str:
    """
    Pretty JSON dump for debugging.
    """
    return json.dumps(get_schema(name), indent=2, ensure_ascii=False)
