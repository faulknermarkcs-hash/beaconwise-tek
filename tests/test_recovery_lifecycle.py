"""Recovery Lifecycle — full closed-loop resilience scenario.

Proves the complete recovery story end-to-end:
  Healthy → TSI degrades → trigger fires → engine selects plan →
  damping controls rollout → plan applied → verification checks →
  success resets breaker / failure trips breaker → cooldown →
  half-open probe → eventual recovery or escalation.

No mocks of resilience internals. Every component is real.
"""
import time
import pytest

from ecosphere.meta_validation.recovery_engine import (
    RecoveryEngine, RecoveryBudgets, RecoveryPlan, RecoveryState, RecoveryTargets,
)
from ecosphere.meta_validation.damping_stabilizer import DampingStabilizer, PIDParams
from ecosphere.meta_validation.circuit_breaker import CircuitBreaker, BreakerConfig
from ecosphere.meta_validation.tsi_tracker import TSITracker, InteractionOutcome
from ecosphere.meta_validation.post_recovery_verifier import PostRecoveryVerifier, VerificationConfig
from ecosphere.meta_validation.resilience_runtime import ResilienceRuntime, TrustSnapshot
from ecosphere.meta_validation.mvi import MetaValidationIndex


# --------------- fixtures ---------------

def _plans():
    return [
        RecoveryPlan(
            name="add_validator", tier=1,
            predicted_tsi_median=0.73, predicted_tsi_low=0.69, predicted_tsi_high=0.77,
            predicted_latency_ms=120, predicted_cost_usd=0.01,
            predicted_independence_gain=0.15, routing_patch={"validators": "+claude"},
        ),
        RecoveryPlan(
            name="swap_primary", tier=2,
            predicted_tsi_median=0.78, predicted_tsi_low=0.62, predicted_tsi_high=0.88,
            predicted_latency_ms=200, predicted_cost_usd=0.05,
            predicted_independence_gain=0.10, routing_patch={"primary": "grok"},
        ),
    ]


def _runtime(cooldown=0, breaker_threshold=2, breaker_cooldown=0.02):
    targets = RecoveryTargets(tsi_target=0.75, tsi_min=0.70, tsi_critical=0.55)
    return ResilienceRuntime(
        engine=RecoveryEngine(
            budgets=RecoveryBudgets(latency_ms_max=500, cost_usd_max=0.10),
            targets=targets,
        ),
        plans=_plans(),
        damping=DampingStabilizer(pid=PIDParams(), cooldown_seconds=cooldown),
        circuit_breaker=CircuitBreaker(BreakerConfig(
            failure_threshold=breaker_threshold,
            cooldown_seconds=breaker_cooldown,
        )),
        tsi_tracker=TSITracker(window_size=20),
        verifier=PostRecoveryVerifier(
            config=VerificationConfig(min_tsi_improvement=0.02, max_tsi_degradation=0.03),
            targets=targets,
        ),
        enabled=True,
    )


def _healthy():
    return TrustSnapshot(tsi_current=0.85, tsi_forecast_15m=0.83, der_density=0.3,
                         dep_concentration_index=0.3, degraded=False)

def _degraded():
    return TrustSnapshot(tsi_current=0.62, tsi_forecast_15m=0.55, der_density=0.15,
                         dep_concentration_index=0.70, degraded=True)

def _critical():
    return TrustSnapshot(tsi_current=0.48, tsi_forecast_15m=0.40, der_density=0.10,
                         dep_concentration_index=0.85, degraded=True)


# --------------- Scenario 1: Happy path ---------------

def test_lifecycle_healthy_no_action():
    """Healthy system → no recovery triggered."""
    rt = _runtime()
    decision = rt.maybe_recover(_healthy())
    assert decision.chosen is None
    assert rt.last_applied_plan is None


def test_lifecycle_degrade_trigger_recover_verify():
    """TSI drops → trigger → plan selected → verification succeeds."""
    rt = _runtime()

    # System degrades
    decision = rt.maybe_recover(_degraded())
    assert decision is not None
    assert decision.chosen is not None
    plan_name = decision.chosen.name
    assert rt.last_applied_plan is not None

    # Verification: TSI improved
    result = rt.verify_recovery(current_tsi=0.76)
    assert result.tsi_improved is True
    assert result.recommend_rollback is False

    # Circuit breaker recorded success
    b = rt.circuit_breaker._get(plan_name)
    assert b.state == "CLOSED"
    assert b.total_successes == 1


# --------------- Scenario 2: Failed recovery → circuit breaker ---------------

def test_lifecycle_failed_recovery_trips_breaker():
    """Recovery fails twice → circuit breaker trips → plan excluded."""
    rt = _runtime(breaker_threshold=2, breaker_cooldown=100)

    # First failure
    rt.maybe_recover(_degraded())
    plan_name = rt.last_applied_plan.name
    rt.verify_recovery(current_tsi=0.58)  # worse
    assert rt.circuit_breaker._get(plan_name).consecutive_failures == 1

    # Second attempt (clear recovery state so we can trigger again)
    rt.last_applied_plan = None
    rt.tsi_at_recovery = None
    rt.maybe_recover(_degraded())
    rt.verify_recovery(current_tsi=0.55)  # still bad
    assert rt.circuit_breaker._get(plan_name).state == "OPEN"

    # Third attempt — original plan should be excluded
    rt.last_applied_plan = None
    rt.tsi_at_recovery = None
    decision = rt.maybe_recover(_degraded())
    assert decision.chosen is not None
    assert decision.chosen.name != plan_name  # fell through to tier 2


def test_lifecycle_all_plans_circuit_broken():
    """Both plans fail → no viable recovery."""
    rt = _runtime(breaker_threshold=1, breaker_cooldown=100)

    for plan in _plans():
        rt.circuit_breaker.record_failure(plan.name)

    decision = rt.maybe_recover(_degraded())
    # Both plans excluded, engine returns no_viable_plans
    assert decision.chosen is None
    assert "no_viable_plans" in decision.reason


# --------------- Scenario 3: Circuit breaker cooldown + half-open probe ---------------

def test_lifecycle_breaker_cooldown_allows_retry():
    """After cooldown, breaker transitions to HALF_OPEN and allows a probe."""
    rt = _runtime(breaker_threshold=1, breaker_cooldown=0.01)

    # Trip the breaker
    rt.maybe_recover(_degraded())
    plan_name = rt.last_applied_plan.name
    rt.verify_recovery(current_tsi=0.55)
    assert rt.circuit_breaker._get(plan_name).state == "OPEN"

    # Wait for cooldown
    time.sleep(0.02)

    # Breaker should transition to HALF_OPEN
    excluded = rt.circuit_breaker.excluded_plans()
    assert plan_name not in excluded
    assert rt.circuit_breaker._get(plan_name).state == "HALF_OPEN"

    # Retry succeeds
    rt.last_applied_plan = None
    rt.tsi_at_recovery = None
    rt.maybe_recover(_degraded())
    rt.verify_recovery(current_tsi=0.76)  # success
    assert rt.circuit_breaker._get(plan_name).state == "CLOSED"
    assert rt.circuit_breaker._get(plan_name).consecutive_failures == 0


def test_lifecycle_half_open_failure_reopens():
    """Half-open probe fails → breaker snaps back to OPEN."""
    rt = _runtime(breaker_threshold=1, breaker_cooldown=0.01)

    rt.maybe_recover(_degraded())
    plan_name = rt.last_applied_plan.name
    rt.verify_recovery(current_tsi=0.55)
    time.sleep(0.02)
    rt.circuit_breaker.excluded_plans()  # trigger HALF_OPEN transition

    rt.last_applied_plan = None
    rt.tsi_at_recovery = None
    rt.maybe_recover(_degraded())
    rt.verify_recovery(current_tsi=0.50)  # probe fails
    assert rt.circuit_breaker._get(plan_name).state == "OPEN"


# --------------- Scenario 4: TSI tracker feeds recovery decisions ---------------

def test_lifecycle_tracker_feeds_signal():
    """TSI tracker aggregates outcomes that inform recovery."""
    rt = _runtime()
    now = time.time()

    # Feed good outcomes
    for i in range(10):
        rt.record_outcome("PASS", validator_agreement=0.9)
    sig = rt.current_signal()
    assert sig.tsi_current > 0.80
    assert sig.pass_rate == 1.0

    # Feed bad outcomes
    for i in range(10):
        rt.record_outcome("ERROR", validator_agreement=0.1)
    sig = rt.current_signal()
    assert sig.tsi_current < 0.70
    assert sig.error_rate == 0.5  # 10 good + 10 bad in window of 20


def test_lifecycle_tracker_drives_snapshot():
    """Signal from tracker can be used to build TrustSnapshot for recovery."""
    rt = _runtime()
    for _ in range(15):
        rt.record_outcome("REFUSE", validator_agreement=0.2)
    sig = rt.current_signal()

    snapshot = TrustSnapshot(
        tsi_current=sig.tsi_current,
        tsi_forecast_15m=sig.tsi_forecast_15m,
        der_density=0.15,
        dep_concentration_index=0.70,
        degraded=True,
    )
    decision = rt.maybe_recover(snapshot)
    assert decision is not None
    assert decision.chosen is not None


# --------------- Scenario 5: Damping controls rollout ---------------

def test_lifecycle_damping_attaches_canary():
    """Damping stabilizer injects RDS hints into chosen plan."""
    rt = _runtime(cooldown=0)
    decision = rt.maybe_recover(_degraded())
    assert decision.chosen is not None
    assert "rds" in decision.chosen.routing_patch
    canary = decision.chosen.routing_patch["rds"]["canary_pct"]
    assert 0.15 <= canary <= 1.0


def test_lifecycle_damping_cooldown_blocks_rapid_fire():
    """Damping cooldown prevents back-to-back recovery actions."""
    rt = _runtime(cooldown=60)  # 60 second cooldown
    d1 = rt.maybe_recover(_degraded())
    assert d1 is not None and d1.chosen is not None

    # Immediately try again — should be blocked by damping cooldown
    rt.last_applied_plan = None
    rt.tsi_at_recovery = None
    d2 = rt.maybe_recover(_degraded())
    assert d2 is None  # blocked


# --------------- Scenario 6: Verification rollback ---------------

def test_lifecycle_verification_rollback_clears_state():
    """Failed verification recommends rollback and clears recovery state."""
    rt = _runtime()
    rt.maybe_recover(_degraded())
    assert rt.last_applied_plan is not None

    result = rt.verify_recovery(current_tsi=0.50)  # much worse
    assert result.recommend_rollback is True
    assert rt.last_applied_plan is None
    assert rt.tsi_at_recovery is None


def test_lifecycle_verification_mvi_failure():
    """Governance mismatch in replay samples triggers rollback."""
    rt = _runtime()
    rt.maybe_recover(_degraded())

    replays = [
        {"governance_match": True, "determinism_index": 100.0},
        {"governance_match": False, "determinism_index": 60.0},  # divergence
    ]
    result = rt.verify_recovery(current_tsi=0.73, replay_results=replays)
    assert result.mvi_passed is False
    assert result.recommend_rollback is True


# --------------- Scenario 7: MVI validates the whole pipeline ---------------

def test_lifecycle_mvi_validates_engine_determinism():
    """MVI confirms recovery engine is deterministic across N trials."""
    mvi = MetaValidationIndex()
    engine = RecoveryEngine(
        budgets=RecoveryBudgets(latency_ms_max=500, cost_usd_max=0.10),
        targets=RecoveryTargets(),
    )
    state = RecoveryState(
        tsi_current=0.60, tsi_forecast_15m=0.55, der_density=0.2,
        concentration_index=0.5, system_status="degraded",
    )
    result = mvi.compute(
        engine=engine, state=state, plans=_plans(),
        tsi_values=[0.80, 0.78, 0.75, 0.72, 0.68, 0.62, 0.55],
    )
    assert result.recovery_consistency == 1.0
    assert result.passed is True


# --------------- Scenario 8: Dependency metrics ---------------

def test_lifecycle_concentration_detection():
    """High provider concentration is detectable."""
    rt = _runtime()
    # Single provider dominance
    _, conc_mono = rt.dependency_metrics({"openai": 1.0})
    assert conc_mono == 1.0

    # Balanced providers
    _, conc_balanced = rt.dependency_metrics({"openai": 0.33, "groq": 0.33, "xai": 0.34})
    assert conc_balanced < 0.5

    assert conc_balanced < conc_mono


# --------------- Scenario 9: Critical TSI escalation ---------------

def test_lifecycle_critical_tsi_selects_aggressive_plan():
    """Under critical TSI, engine still triggers and selects best available."""
    rt = _runtime(cooldown=0)
    decision = rt.maybe_recover(_critical())
    assert decision is not None
    assert decision.chosen is not None
    assert "triggered" in decision.reason
