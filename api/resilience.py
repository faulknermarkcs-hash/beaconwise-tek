# api/resilience.py
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional

router = APIRouter()

class DerState(BaseModel):
    density: float = Field(..., ge=0.0, le=1.0)
    concentration_index: float = Field(..., ge=0.0, le=1.0)
    top_risk: Optional[str] = None

class RecoveryStateIn(BaseModel):
    tsi_current: float = Field(..., ge=-10.0, le=10.0)
    tsi_forecast_15m: float = Field(..., ge=-10.0, le=10.0)
    status: Literal["ok", "degraded", "outage"] = "ok"
    der: Optional[DerState] = None

class RecoveryPlanIn(BaseModel):
    name: str
    tier: int = Field(..., ge=1, le=3)
    predicted_tsi_median: float
    predicted_tsi_low: float
    predicted_tsi_high: float
    predicted_latency_ms: int = Field(..., ge=0)
    predicted_cost_usd: float = Field(..., ge=0.0)
    predicted_independence_gain: float = Field(..., ge=0.0)
    routing_patch: Dict[str, Any] = Field(default_factory=dict)

class RecoveryBudgetsIn(BaseModel):
    latency_ms_max: int = Field(..., ge=0)
    cost_usd_max: float = Field(..., ge=0.0)

class RecoveryTargetsIn(BaseModel):
    tsi_target: float
    tsi_min: float
    tsi_critical: float
    max_recovery_minutes: int = Field(..., ge=0)

class ResilienceDecideRequest(BaseModel):
    state: RecoveryStateIn
    plans: List[RecoveryPlanIn]
    budgets: RecoveryBudgetsIn
    targets: RecoveryTargetsIn

@router.post("/decide", tags=["resilience"])
def decide(req: ResilienceDecideRequest) -> Dict[str, Any]:
    """
    Minimal decide endpoint (wire to RecoveryEngine later).
    Exists so Swagger shows the route and you can test payload shape.
    """
    return {
        "ok": True,
        "received": {
            "tsi_current": req.state.tsi_current,
            "tsi_forecast_15m": req.state.tsi_forecast_15m,
            "plan_count": len(req.plans),
        },
    }
