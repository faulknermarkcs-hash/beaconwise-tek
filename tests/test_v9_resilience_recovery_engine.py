"""Recovery engine integration tests — trigger, select, circuit break."""
import pytest

from ecosphere.meta_validation.recovery_engine import (
    RecoveryEngine, RecoveryBudgets, RecoveryTargets, RecoveryPlan, RecoveryState
)
from ecosphere.meta_validation.damping_stabilizer import DampingStabilizer, PIDParams


def _make_engine(**kw):
    return RecoveryEngine(
        budgets=kw.get("budgets", RecoveryBudgets(latency_ms_max=500, cost_usd_max=0.10)),
        targets=kw.get("targets", RecoveryTargets(tsi_target=0.75, tsi_min=0.70, tsi_critical=0.55)),
        diversity_bonus_weight=0.15,
    )


def _make_plans():
    return [
        RecoveryPlan(
            name="diversify_validator_plane", tier=1,
            predicted_tsi_median=0.72, predicted_tsi_low=0.68, predicted_tsi_high=0.76,
            predicted_latency_ms=150, predicted_cost_usd=0.01, predicted_independence_gain=0.15,
            routing_patch={"validators": "add:claude"},
        ),
        RecoveryPlan(
            name="activate_hot_standby_primary", tier=2,
            predicted_tsi_median=0.78, predicted_tsi_low=0.60, predicted_tsi_high=0.90,
            predicted_latency_ms=250, predicted_cost_usd=0.06, predicted_independence_gain=0.05,
            routing_patch={"primary": "grok"},
        ),
        RecoveryPlan(
            name="increase_consensus_depth", tier=3,
            predicted_tsi_median=0.80, predicted_tsi_low=0.62, predicted_tsi_high=0.95,
            predicted_latency_ms=600, predicted_cost_usd=0.08, predicted_independence_gain=0.20,
            routing_patch={"min_validators": 5},
        ),
    ]


def test_recovery_trigger_and_decision_selects_best_plan():
    engine = _make_engine()
    state = RecoveryState(
        tsi_current=0.65, tsi_forecast_15m=0.58, der_density=0.17,
        concentration_index=0.72, system_status="ok", oscillation_index=0.02,
    )
    decision = engine.decide(state, _make_plans())
    assert decision.chosen is not None
    assert decision.chosen.name == "diversify_validator_plane"
    assert "triggered:tsi_forecast_15m" in decision.reason
    rej = [e for e in decision.evaluated if e["name"] == "increase_consensus_depth"][0]
    assert rej.get("rejected") == "latency_budget"


def test_no_trigger_when_healthy():
    engine = _make_engine()
    state = RecoveryState(
        tsi_current=0.85, tsi_forecast_15m=0.82, der_density=0.3,
        concentration_index=0.3, system_status="ok",
    )
    decision = engine.decide(state, _make_plans())
    assert decision.chosen is None
    assert decision.reason == "no_trigger"


def test_trigger_on_degraded_status():
    engine = _make_engine()
    state = RecoveryState(
        tsi_current=0.80, tsi_forecast_15m=0.80, der_density=0.3,
        concentration_index=0.3, system_status="degraded",
    )
    decision = engine.decide(state, _make_plans())
    assert decision.chosen is not None
    assert "system_status=degraded" in decision.reason


def test_excluded_plans_respected():
    engine = _make_engine()
    state = RecoveryState(
        tsi_current=0.65, tsi_forecast_15m=0.58, der_density=0.17,
        concentration_index=0.72, system_status="degraded",
    )
    decision = engine.decide(state, _make_plans(), excluded_plans={"diversify_validator_plane"})
    assert decision.chosen is not None
    assert decision.chosen.name == "activate_hot_standby_primary"
    excluded_eval = [e for e in decision.evaluated if e["name"] == "diversify_validator_plane"][0]
    assert excluded_eval["rejected"] == "circuit_breaker_open"


def test_damping_stabilizer_attaches_rds_hints():
    pid = PIDParams(kp=0.5, ki=0.2, kd=0.1)
    rds = DampingStabilizer(pid=pid, max_oscillation=0.15, cooldown_seconds=60)
    state = RecoveryState(
        tsi_current=0.65, tsi_forecast_15m=0.58, der_density=0.17,
        concentration_index=0.72, oscillation_index=0.02,
    )
    plan = RecoveryPlan(
        name="diversify_validator_plane", tier=1,
        predicted_tsi_median=0.72, predicted_tsi_low=0.68, predicted_tsi_high=0.76,
        predicted_latency_ms=150, predicted_cost_usd=0.01, predicted_independence_gain=0.15,
        routing_patch={"validators": "add:claude"},
    )
    damped = rds.damp_plan(state, plan, targets=RecoveryTargets(0.75, 0.70, 0.55, 15))
    assert "rds" in damped.routing_patch
    assert 0.15 <= damped.routing_patch["rds"]["canary_pct"] <= 1.0


def test_oscillation_reduces_tier3_score():
    engine = _make_engine(budgets=RecoveryBudgets(latency_ms_max=1000, cost_usd_max=1.0))
    state_calm = RecoveryState(
        tsi_current=0.60, tsi_forecast_15m=0.55, der_density=0.2,
        concentration_index=0.5, system_status="degraded", oscillation_index=0.05,
    )
    state_osc = RecoveryState(
        tsi_current=0.60, tsi_forecast_15m=0.55, der_density=0.2,
        concentration_index=0.5, system_status="degraded", oscillation_index=0.25,
    )
    plan_t3 = RecoveryPlan(
        name="big_move", tier=3, predicted_tsi_median=0.80, predicted_tsi_low=0.70,
        predicted_tsi_high=0.90, predicted_latency_ms=300, predicted_cost_usd=0.05,
        predicted_independence_gain=0.2, routing_patch={},
    )
    score_calm = engine._score_plan(state_calm, plan_t3)
    score_osc = engine._score_plan(state_osc, plan_t3)
    assert score_osc < score_calm, "High oscillation should penalize tier 3 plans"
