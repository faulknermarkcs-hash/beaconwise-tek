# api/main.py
"""BeaconWise v1.9.0 API — FastAPI Production Backend.

Endpoints:
  GET  /              Health check
  POST /query         Governed query (two-stage consensus)
  GET  /constitution  Machine-readable constitution
  GET  /schema/{name} Governance schema by name
  GET  /schemas       List all governance schemas
  GET  /metrics       Governance dashboard metrics
  GET  /manifest      Build provenance manifest
  GET  /policy        Active policy + validation errors
  POST /verify-chain  Verify EPACK chain integrity
  POST /replay        Replay governance decision from EPACK
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

# Ensure src is on path (repo_root/src)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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

# ✅ two-stage consensus
from ecosphere.consensus.orchestrator.flow import run_two_stage_consensus

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

_metrics = GovernanceMetrics()


class QueryBody(BaseModel):
    text: str
    primary_model: Optional[str] = None
    challenger_model: Optional[str] = None
    arbiter_model: Optional[str] = None
    workspace_id: Optional[str] = None
    session_id: Optional[str] = None


@app.get("/")
def health():
    m = current_manifest()
    return {
        "status": "BeaconWise v1.9.0 running",
        "version": m.get("kernel_version"),
        "product": m.get("product_name"),
        "adapters": m.get("v8_adapter_count", 7),
    }


@app.get("/constitution")
def constitution():
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
    try:
        s = get_schema(name)
    except KeyError:
        s = None
    if s is None:
        raise HTTPException(status_code=404, detail=f"Schema '{name}' not found")
    return s


@app.get("/schemas")
def all_schemas():
    return {"schemas": get_all_schemas()}


@app.get("/metrics")
def metrics():
    return _metrics.dashboard()


@app.get("/manifest")
def manifest():
    return current_manifest()


@app.get("/policy")
def policy():
    policy_path = os.environ.get("BEACONWISE_POLICY", "policies/default.yaml")
    p = load_policy(policy_path)
    errors = validate_policy(p)
    return {"policy": p, "valid": len(errors) == 0, "errors": errors}


@app.post("/verify-chain")
def verify_chain(payload: Dict[str, Any]):
    return verify_epack_chain(payload)


@app.post("/replay")
def replay(payload: Dict[str, Any]):
    result = replay_governance_decision(payload)
    return {"result": result, "summary": replay_summary(result) if result is not None else None}


@app.post("/query")
def query(body: QueryBody):
    user_text = (body.text or "").strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="text is required")

    primary = body.primary_model or os.getenv("TEK_PRIMARY_MODEL", "gpt-4o")
    challenger = body.challenger_model or os.getenv("TEK_CHALLENGER_MODEL", "claude-sonnet-4-20250514")
    arbiter = body.arbiter_model or os.getenv("TEK_ARBITER_MODEL", "llama-3.3-70b-versatile")

    try:
        result = run_two_stage_consensus(
            user_text,
            primary_model=primary,
            challenger_model=challenger,
            arbiter_model=arbiter,
        )
        if isinstance(result, dict):
            final = result.get("final") or result.get("answer") or result.get("output")
        else:
            final = None

        return {
            "ok": True,
            "final": final if final is not None else str(result),
            "result": result,
            "models": {"primary": primary, "challenger": challenger, "arbiter": arbiter},
            "workspace_id": body.workspace_id,
            "session_id": body.session_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TEK consensus failed: {type(exc).__name__}: {exc}")
