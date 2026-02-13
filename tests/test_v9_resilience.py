"""V9 resilience tests — policy compiler, recovery engine, damping."""
import pytest

from ecosphere.meta_validation.recovery_engine import (
    RecoveryBudgets, RecoveryEngine, RecoveryPlan, RecoveryState, RecoveryTargets,
)
from ecosphere.meta_validation.damping_stabilizer import DampingStabilizer, PIDParams
from ecosphere.meta_validation.policy_compiler import compile_resilience_policy


def test_policy_compiler_disabled_returns_disabled():
    compiled = compile_resilience_policy({"resilience_policy": {"enabled": False}})
    assert compiled.enabled is False
    assert compiled.runtime is None


def test_policy_compiler_enabled_builds_objects():
    policy = {
        "resilience_policy": {
            "enabled": True,
            "targets": {"tsi": {"target": 0.75, "min": 0.70, "critical": 0.55}, "recovery": {"max_minutes": 15}},
            "budgets": {"latency_ms_max": 800, "cost_usd_max": 0.5},
            "scoring": {"weights": {"diversity_bonus": 0.15}},
            "damping": {"enabled": True, "pid": {"kp": 0.5, "ki": 0.2, "kd": 0.1}, "max_oscillation": 0.15, "cooldown_seconds": 60},
            "plans": {
                "tier_1": [{"id": "test_plan", "name": "Test Plan", "predicted": {
                    "tsi_median": 0.72, "tsi_low": 0.68, "tsi_high": 0.76,
                    "latency_ms": 150, "cost_usd": 0.01, "independence_gain": 0.15,
                }, "routing_patch": {"validators": "add:claude"}}],
            },
        }
    }
    compiled = compile_resilience_policy(policy)
    assert compiled.enabled is True
    assert compiled.runtime is not None
    assert compiled.runtime.engine is not None
    assert compiled.runtime.damping is not None
    assert len(compiled.runtime.plans) == 1


def test_policy_compiler_empty_policy():
    compiled = compile_resilience_policy({})
    assert compiled.enabled is False


def test_policy_compiler_none_policy():
    compiled = compile_resilience_policy(None)
    assert compiled.enabled is False


def test_recovery_engine_budget_rejects_over_budget_plan():
    targets = RecoveryTargets(tsi_target=0.75, tsi_min=0.70, tsi_critical=0.55, max_recovery_minutes=15)
    budgets = RecoveryBudgets(latency_ms_max=100, cost_usd_max=0.01)
    engine = RecoveryEngine(budgets=budgets, targets=targets)

    state = RecoveryState(tsi_current=0.65, tsi_forecast_15m=0.58, der_density=0.2, concentration_index=0.7, system_status="degraded")
    plans = [
        RecoveryPlan(
            name="too_slow", tier=1, predicted_tsi_median=0.8, predicted_tsi_low=0.75,
            predicted_tsi_high=0.85, predicted_latency_ms=500, predicted_cost_usd=0.02,
            predicted_independence_gain=0.2, routing_patch={"x": "y"},
        )
    ]
    decision = engine.decide(state=state, plans=plans)
    assert decision.chosen is None
    assert "no_viable_plans" in decision.reason


def test_recovery_engine_to_dict():
    targets = RecoveryTargets()
    budgets = RecoveryBudgets()
    engine = RecoveryEngine(budgets=budgets, targets=targets)
    state = RecoveryState(tsi_current=0.80, tsi_forecast_15m=0.78, der_density=0.2, concentration_index=0.3)
    decision = engine.decide(state, [])
    d = decision.to_dict()
    assert "decision_id" in d
    assert d["reason"] == "no_trigger"


def test_damping_stabilizer_canary_bounds():
    pid = PIDParams(kp=0.5, ki=0.2, kd=0.1)
    rds = DampingStabilizer(pid=pid, max_oscillation=0.15, cooldown_seconds=60)
    state = RecoveryState(tsi_current=0.65, tsi_forecast_15m=0.58, der_density=0.2, concentration_index=0.8)
    plan = RecoveryPlan(
        name="p", tier=1, predicted_tsi_median=0.72, predicted_tsi_low=0.68,
        predicted_tsi_high=0.76, predicted_latency_ms=50, predicted_cost_usd=0.0,
        predicted_independence_gain=0.1, routing_patch={},
    )
    damped = rds.damp_plan(state=state, plan=plan, targets=RecoveryTargets(0.75, 0.70, 0.55, 15))
    assert "rds" in damped.routing_patch
    assert 0.15 <= damped.routing_patch["rds"]["canary_pct"] <= 1.0


def test_damping_cooldown():
    pid = PIDParams(kp=0.5, ki=0.2, kd=0.1)
    rds = DampingStabilizer(pid=pid, cooldown_seconds=60)
    state = RecoveryState(tsi_current=0.65, tsi_forecast_15m=0.58, der_density=0.2, concentration_index=0.5)
    plan = RecoveryPlan(
        name="p", tier=1, predicted_tsi_median=0.72, predicted_tsi_low=0.68,
        predicted_tsi_high=0.76, predicted_latency_ms=50, predicted_cost_usd=0.0,
        predicted_independence_gain=0.1, routing_patch={},
    )
    rds.damp_plan(state, plan, targets=RecoveryTargets())
    assert rds.in_cooldown() is True


def test_damping_reset():
    pid = PIDParams()
    rds = DampingStabilizer(pid=pid)
    state = RecoveryState(tsi_current=0.65, tsi_forecast_15m=0.58, der_density=0.2, concentration_index=0.5)
    plan = RecoveryPlan(
        name="p", tier=1, predicted_tsi_median=0.72, predicted_tsi_low=0.68,
        predicted_tsi_high=0.76, predicted_latency_ms=50, predicted_cost_usd=0.0,
        predicted_independence_gain=0.1, routing_patch={},
    )
    rds.damp_plan(state, plan, targets=RecoveryTargets())
    rds.reset()
    assert rds.in_cooldown() is False
    assert rds._integral == 0.0
