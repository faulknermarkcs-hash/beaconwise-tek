"""Resilience runtime integration tests."""
import time
import pytest

from ecosphere.meta_validation.recovery_engine import (
    RecoveryEngine, RecoveryBudgets, RecoveryPlan, RecoveryState, RecoveryTargets,
)
from ecosphere.meta_validation.damping_stabilizer import DampingStabilizer, PIDParams
from ecosphere.meta_validation.circuit_breaker import CircuitBreaker, BreakerConfig
from ecosphere.meta_validation.tsi_tracker import TSITracker
from ecosphere.meta_validation.resilience_runtime import ResilienceRuntime, TrustSnapshot


def _make_runtime(enabled=True, cooldown=0):
    engine = RecoveryEngine(
        budgets=RecoveryBudgets(latency_ms_max=500, cost_usd_max=0.10),
        targets=RecoveryTargets(tsi_target=0.75, tsi_min=0.70, tsi_critical=0.55),
    )
    plans = [
        RecoveryPlan(
            name="plan_a", tier=1, predicted_tsi_median=0.72, predicted_tsi_low=0.68,
            predicted_tsi_high=0.76, predicted_latency_ms=150, predicted_cost_usd=0.01,
            predicted_independence_gain=0.15, routing_patch={"validators": "add:claude"},
        ),
    ]
    damping = DampingStabilizer(pid=PIDParams(), cooldown_seconds=cooldown) if cooldown >= 0 else None
    return ResilienceRuntime(
        engine=engine, plans=plans, damping=damping,
        circuit_breaker=CircuitBreaker(BreakerConfig(failure_threshold=2)),
        tsi_tracker=TSITracker(window_size=20),
        enabled=enabled,
    )


def test_disabled_runtime_returns_none():
    rt = _make_runtime(enabled=False)
    snap = TrustSnapshot(tsi_current=0.50, tsi_forecast_15m=0.45, der_density=0.2, dep_concentration_index=0.5, degraded=True)
    assert rt.maybe_recover(snap) is None


def test_recovery_triggered_on_degraded():
    rt = _make_runtime(cooldown=0)
    snap = TrustSnapshot(tsi_current=0.60, tsi_forecast_15m=0.55, der_density=0.2, dep_concentration_index=0.5, degraded=True)
    decision = rt.maybe_recover(snap)
    assert decision is not None
    assert decision.chosen is not None
    assert decision.chosen.name == "plan_a"


def test_no_recovery_when_healthy():
    rt = _make_runtime(cooldown=0)
    snap = TrustSnapshot(tsi_current=0.85, tsi_forecast_15m=0.82, der_density=0.3, dep_concentration_index=0.3, degraded=False)
    decision = rt.maybe_recover(snap)
    assert decision is not None
    assert decision.chosen is None


def test_record_outcome_feeds_tracker():
    rt = _make_runtime()
    rt.record_outcome("PASS", validator_agreement=0.9)
    rt.record_outcome("PASS", validator_agreement=0.8)
    sig = rt.current_signal()
    assert sig.window_size == 2
    assert sig.pass_rate == 1.0


def test_verify_recovery_success():
    rt = _make_runtime(cooldown=0)
    snap = TrustSnapshot(tsi_current=0.60, tsi_forecast_15m=0.55, der_density=0.2, dep_concentration_index=0.5, degraded=True)
    rt.maybe_recover(snap)
    result = rt.verify_recovery(current_tsi=0.75)
    assert result is not None
    assert result.tsi_improved is True


def test_verify_recovery_failure_triggers_circuit_breaker():
    rt = _make_runtime(cooldown=0)
    snap = TrustSnapshot(tsi_current=0.60, tsi_forecast_15m=0.55, der_density=0.2, dep_concentration_index=0.5, degraded=True)

    # First recovery + failed verification
    rt.maybe_recover(snap)
    rt.verify_recovery(current_tsi=0.55)  # worse

    # Second recovery + failed verification
    rt.last_applied_plan = None
    rt.tsi_at_recovery = None
    rt.maybe_recover(snap)
    rt.verify_recovery(current_tsi=0.50)  # worse again

    # Plan should now be circuit-broken
    excluded = rt.circuit_breaker.excluded_plans()
    assert "plan_a" in excluded


def test_dependency_metrics():
    rt = _make_runtime()
    density, concentration = rt.dependency_metrics({"openai": 0.55, "groq": 0.25, "xai": 0.20})
    assert 0.0 <= density <= 1.0
    assert 0.0 <= concentration <= 1.0
    # 3 providers should have lower concentration than 1
    _, conc_single = rt.dependency_metrics({"openai": 1.0})
    assert concentration < conc_single
