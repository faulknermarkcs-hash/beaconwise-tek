"""Post-recovery verifier and MVI tests."""
import pytest

from ecosphere.meta_validation.recovery_engine import RecoveryPlan, RecoveryTargets
from ecosphere.meta_validation.post_recovery_verifier import (
    PostRecoveryVerifier, VerificationConfig, VerificationResult,
)
from ecosphere.meta_validation.mvi import MetaValidationIndex, MVIResult
from ecosphere.meta_validation.recovery_engine import (
    RecoveryEngine, RecoveryBudgets, RecoveryState,
)


def _plan(name="test_plan"):
    return RecoveryPlan(
        name=name, tier=1, predicted_tsi_median=0.72, predicted_tsi_low=0.68,
        predicted_tsi_high=0.76, predicted_latency_ms=150, predicted_cost_usd=0.01,
        predicted_independence_gain=0.15, routing_patch={},
    )


# --- PostRecoveryVerifier ---

def test_verify_improvement():
    v = PostRecoveryVerifier(targets=RecoveryTargets())
    result = v.verify(_plan(), tsi_before=0.60, tsi_after=0.75)
    assert result.tsi_improved is True
    assert result.recommend_rollback is False


def test_verify_degradation_recommends_rollback():
    v = PostRecoveryVerifier(config=VerificationConfig(max_tsi_degradation=0.03), targets=RecoveryTargets())
    result = v.verify(_plan(), tsi_before=0.65, tsi_after=0.60)
    assert result.tsi_improved is False
    assert result.recommend_rollback is True


def test_verify_flat_no_rollback():
    v = PostRecoveryVerifier(targets=RecoveryTargets())
    result = v.verify(_plan(), tsi_before=0.70, tsi_after=0.71)
    assert result.tsi_improved is False
    assert result.recommend_rollback is False


def test_verify_critical_tsi_recommends_rollback():
    v = PostRecoveryVerifier(targets=RecoveryTargets(tsi_critical=0.55))
    result = v.verify(_plan(), tsi_before=0.50, tsi_after=0.52)
    assert result.recommend_rollback is True
    assert any("tsi_still_critical" in r for r in result.reasons)


def test_verify_mvi_governance_mismatch():
    v = PostRecoveryVerifier(config=VerificationConfig(mvi_check=True), targets=RecoveryTargets())
    replays = [
        {"governance_match": True, "determinism_index": 100.0},
        {"governance_match": False, "determinism_index": 80.0},
    ]
    result = v.verify(_plan(), tsi_before=0.60, tsi_after=0.70, replay_results=replays)
    assert result.mvi_passed is False
    assert result.recommend_rollback is True


def test_verify_to_dict():
    v = PostRecoveryVerifier(targets=RecoveryTargets())
    result = v.verify(_plan(), tsi_before=0.60, tsi_after=0.75)
    d = result.to_dict()
    assert "plan_name" in d
    assert d["tsi_improved"] is True


# --- MetaValidationIndex ---

def test_mvi_perfect_scores():
    mvi = MetaValidationIndex()
    replays = [{"governance_match": True, "determinism_index": 100.0}]
    result = mvi.compute(
        replay_results_a=replays,
        replay_results_b=replays,
        tsi_values=[0.80, 0.82, 0.81, 0.83],
    )
    assert result.passed is True
    assert result.mvi_score >= 0.80


def test_mvi_replay_divergence():
    mvi = MetaValidationIndex()
    a = [{"governance_match": True, "determinism_index": 100.0}]
    b = [{"governance_match": False, "determinism_index": 50.0}]
    result = mvi.compute(replay_results_a=a, replay_results_b=b)
    assert result.replay_stability < 1.0


def test_mvi_recovery_consistency():
    mvi = MetaValidationIndex()
    engine = RecoveryEngine(budgets=RecoveryBudgets(), targets=RecoveryTargets())
    state = RecoveryState(
        tsi_current=0.60, tsi_forecast_15m=0.55, der_density=0.2,
        concentration_index=0.5, system_status="degraded",
    )
    plans = [_plan()]
    result = mvi.compute(engine=engine, state=state, plans=plans)
    assert result.recovery_consistency == 1.0, "Deterministic engine should be consistent"


def test_mvi_tsi_coherence_clean():
    mvi = MetaValidationIndex()
    result = mvi.compute(tsi_values=[0.80, 0.81, 0.79, 0.82])
    assert result.tsi_coherence == 1.0


def test_mvi_tsi_coherence_impossible_jump():
    mvi = MetaValidationIndex()
    result = mvi.compute(tsi_values=[0.80, 0.30])  # 0.5 jump
    assert result.tsi_coherence < 1.0


def test_mvi_tsi_out_of_bounds():
    mvi = MetaValidationIndex()
    result = mvi.compute(tsi_values=[0.80, 1.5, 0.82])
    assert result.tsi_coherence < 1.0


def test_mvi_to_dict():
    mvi = MetaValidationIndex()
    result = mvi.compute(tsi_values=[0.80])
    d = result.to_dict()
    assert "mvi_score" in d
    assert "details" in d
