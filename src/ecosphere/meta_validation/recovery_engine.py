"""Recovery Engine — deterministic plan selection for resilience recovery.

Selects the best recovery plan given DER/TSI state and resilience policy weights.
Intentionally standalone and deterministic: no network calls, no LLM invocations.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
import time
import uuid
import math


@dataclass(frozen=True)
class RecoveryTargets:
    tsi_target: float = 0.75
    tsi_min: float = 0.70
    tsi_critical: float = 0.55
    max_recovery_minutes: int = 15


@dataclass(frozen=True)
class RecoveryBudgets:
    latency_ms_max: int = 800
    cost_usd_max: float = 0.50


@dataclass
class RecoveryPlan:
    name: str
    tier: int
    predicted_tsi_median: float
    predicted_tsi_low: float
    predicted_tsi_high: float
    predicted_latency_ms: int
    predicted_cost_usd: float
    predicted_independence_gain: float = 0.0
    routing_patch: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryState:
    tsi_current: float
    tsi_forecast_15m: float
    der_density: float
    concentration_index: float
    system_status: str = "ok"          # ok | degraded | incident
    oscillation_index: float = 0.0     # recent TSI volatility


@dataclass
class RecoveryDecision:
    decision_id: str
    timestamp_ms: int
    reason: str
    tsi_before: float
    tsi_forecast: float
    evaluated: List[Dict[str, Any]]
    chosen: Optional[RecoveryPlan] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "timestamp_ms": self.timestamp_ms,
            "reason": self.reason,
            "tsi_before": self.tsi_before,
            "tsi_forecast": self.tsi_forecast,
            "evaluated": self.evaluated,
            "chosen": asdict(self.chosen) if self.chosen else None,
        }


class RecoveryEngine:
    """Selects a recovery plan given DER/TSI state and resilience policy weights."""

    def __init__(
        self,
        budgets: RecoveryBudgets,
        targets: RecoveryTargets,
        diversity_bonus_weight: float = 0.15,
        penalty_latency_weight: float = 0.0005,
        penalty_cost_weight: float = 0.25,
        confidence_low_penalty_weight: float = 0.30,
        tier_penalties: Optional[Dict[int, float]] = None,
    ) -> None:
        self.budgets = budgets
        self.targets = targets
        self.diversity_bonus_weight = diversity_bonus_weight
        self.penalty_latency_weight = penalty_latency_weight
        self.penalty_cost_weight = penalty_cost_weight
        self.confidence_low_penalty_weight = confidence_low_penalty_weight
        self.tier_penalties = tier_penalties or {1: 0.00, 2: 0.05, 3: 0.12}

    def should_trigger(self, state: RecoveryState) -> Tuple[bool, str]:
        if state.system_status in {"degraded", "incident"}:
            return True, f"triggered:system_status={state.system_status}"
        if state.tsi_forecast_15m < self.targets.tsi_min:
            return True, f"triggered:tsi_forecast_15m<{self.targets.tsi_min:.2f}"
        if state.concentration_index >= 0.70 and state.tsi_forecast_15m < self.targets.tsi_target:
            return True, "triggered:concentration_high+tsi_below_target"
        return False, "no_trigger"

    def decide(
        self,
        state: RecoveryState,
        plans: List[RecoveryPlan],
        *,
        now_ms: Optional[int] = None,
        excluded_plans: Optional[set] = None,
    ) -> RecoveryDecision:
        """Select best viable plan. excluded_plans (from circuit breaker) are skipped."""
        now_ms = now_ms or int(time.time() * 1000)
        excluded = excluded_plans or set()
        ok, reason = self.should_trigger(state)
        decision_id = str(uuid.uuid4())

        if not ok:
            return RecoveryDecision(
                decision_id=decision_id, timestamp_ms=now_ms, reason=reason,
                tsi_before=state.tsi_current, tsi_forecast=state.tsi_forecast_15m,
                evaluated=[], chosen=None,
            )

        viable: List[Tuple[float, RecoveryPlan, Dict[str, Any]]] = []
        evaluated: List[Dict[str, Any]] = []

        for p in plans:
            if p.name in excluded:
                evaluated.append(self._serialize_scored(p, score=-math.inf, rejected="circuit_breaker_open"))
                continue
            if p.predicted_latency_ms > self.budgets.latency_ms_max:
                evaluated.append(self._serialize_scored(p, score=-math.inf, rejected="latency_budget"))
                continue
            if p.predicted_cost_usd > self.budgets.cost_usd_max:
                evaluated.append(self._serialize_scored(p, score=-math.inf, rejected="cost_budget"))
                continue

            score = self._score_plan(state, p)
            payload = self._serialize_scored(p, score=score)
            evaluated.append(payload)
            viable.append((score, p, payload))

        if not viable:
            return RecoveryDecision(
                decision_id=decision_id, timestamp_ms=now_ms,
                reason=reason + "|no_viable_plans",
                tsi_before=state.tsi_current, tsi_forecast=state.tsi_forecast_15m,
                evaluated=evaluated, chosen=None,
            )

        viable.sort(key=lambda t: (t[0], t[1].predicted_independence_gain, -t[1].tier), reverse=True)
        chosen = viable[0][1]
        return RecoveryDecision(
            decision_id=decision_id, timestamp_ms=now_ms, reason=reason,
            tsi_before=state.tsi_current, tsi_forecast=state.tsi_forecast_15m,
            evaluated=evaluated, chosen=chosen,
        )

    def _score_plan(self, state: RecoveryState, p: RecoveryPlan) -> float:
        gain = max(0.0, p.predicted_tsi_median - state.tsi_current)
        low_risk = max(0.0, self.targets.tsi_min - p.predicted_tsi_low)
        confidence_pen = self.confidence_low_penalty_weight * low_risk
        latency_pen = self.penalty_latency_weight * float(p.predicted_latency_ms)
        cost_pen = self.penalty_cost_weight * float(p.predicted_cost_usd)
        tier_pen = self.tier_penalties.get(p.tier, 0.1)
        diversity_bonus = self.diversity_bonus_weight * float(p.predicted_independence_gain)
        osc_pen = 0.10 if (state.oscillation_index > 0.15 and p.tier >= 3) else 0.0
        return gain + diversity_bonus - (latency_pen + cost_pen + confidence_pen + tier_pen + osc_pen)

    @staticmethod
    def _serialize_scored(plan: RecoveryPlan, *, score: float, rejected: Optional[str] = None) -> Dict[str, Any]:
        d = asdict(plan)
        d["score"] = score
        if rejected:
            d["rejected"] = rejected
        return d
