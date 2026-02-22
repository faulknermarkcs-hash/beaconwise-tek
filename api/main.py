# api/main.py
"""BeaconWise v1.9.0 API — FastAPI Production Backend.

Endpoints:
  GET  /              Health check
  GET  /constitution  Machine-readable constitution
  GET  /schema/{name} Governance schema by name
  GET  /schemas       List all governance schemas
  GET  /metrics       Governance dashboard metrics
  GET  /manifest      Build provenance manifest
  GET  /policy        Active policy + validation errors
  POST /verify-chain  Verify EPACK chain integrity
  POST /replay        Replay governance decision from EPACK

Optional:
  POST /resilience/decide  Recovery decision (if api/resilience.py is present)
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict

# Ensure src is on path (repo_root/src)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi import FastAPI, HTTPException

# ----------------------------
# Optional routers
# ----------------------------
try:
    from api.resilience import router as resilience_router  # type: ignore
except Exception as e:
    resilience_router = None
    print("RESILIENCE IMPORT FAILED:", repr(e))

# ----------------------------
# Core imports (src/ecosphere)
# ----------------------------
from ecosphere.governance.constitution import get_constitution, get_constitution_hash
from ecosphere.governance.schema import get_all_schemas, get_schema
from ecosphere.governance.metrics import GovernanceMetrics
from ecosphere.governance.proof import verify_epack_chain
from ecosphere.governance.dsl_loader import load_policy, validate_policy
from ecosphere.replay.engine import replay_governance_decision, replay_summary
from ecosphere.kernel.provenance import current_manifest

# ----------------------------
# App
# ----------------------------
app = FastAPI(
    title="BeaconWise v1.9.0 API",
    description="Deterministic governance infrastructure for intelligence systems",
    version="1.9.0",
)

if resilience_router is not None:
    app.include_router(resilience_router, prefix="/resilience", tags=["resilience"])

# Global metrics instance
_metrics = GovernanceMetrics()

# ----------------------------
# Routes
# ----------------------------
@app.get("/")
def health():
    """Health check + version info."""
    m = current_manifest()
    return {
        "status": "BeaconWise v1.9.0 running",
        "version": m.get("kernel_version"),
        "product": m.get("product_name"),
        "adapters": m.get("v8_adapter_count", 7),
    }


@app.get("/constitution")
def constitution():
    """Machine-readable governance constitution."""
    inv_list = get_constitution()
    return {
        "constitution_hash": get_constitution_hash(),
        "invariant_count": len(inv_list),
        "invariants": [
            {
                "id": inv.id,
                "name": inv.name,
                "category": inv.category,
                "severity": inv.severity.value if hasattr(inv.severity, "value") else str(inv.severity),
                "description": inv.description,
            }
            for inv in inv_list
        ],
    }


@app.get("/schema/{name}")
def schema(name: str):
    """Retrieve governance schema by name."""
    try:
        s = get_schema(name)
    except KeyError:
        s = None

    if s is None:
        raise HTTPException(status_code=404, detail=f"Schema '{name}' not found")
    return s


@app.get("/schemas")
def all_schemas():
    """List all governance schemas (name + version + schema)."""
    return {
        "schemas": get_all_schemas(),
    }


@app.get("/metrics")
def metrics():
    """Current governance metrics dashboard."""
    return _metrics.dashboard()


@app.get("/manifest")
def manifest():
    """Build provenance manifest."""
    return current_manifest()


@app.get("/policy")
def policy():
    """Current active governance policy (plus validation)."""
    policy_path = os.environ.get("BEACONWISE_POLICY", "policies/default.yaml")
    p = load_policy(policy_path)
    errors = validate_policy(p)
    return {
        "policy": p,
        "valid": len(errors) == 0,
        "errors": errors,
    }


@app.post("/verify-chain")
def verify_chain(payload: Dict[str, Any]):
    """
    Verify EPACK chain integrity.

    Expected payload example:
      {"epack_path": "path/to/epacks.jsonl"}   OR
      {"epack_id": "abc123", "store": "postgres"}  (depending on your implementation)
    """
    return verify_epack_chain(payload)


@app.post("/replay")
def replay(payload: Dict[str, Any]):
    """
    Replay governance decision from EPACK.

    Expected payload example:
      {"epack_id": "abc123", "mode": "strict"}
    """
    result = replay_governance_decision(payload)
    return {
        "result": result,
        "summary": replay_summary(result) if result is not None else None,
    }


@app.post("/query")
def query(_: Dict[str, Any]):
    """
    Governed query (full pipeline).
    """
    raise HTTPException(
        status_code=501,
        detail="POST /query not wired in this build. Wire to kernel pipeline entrypoint.",
    )
