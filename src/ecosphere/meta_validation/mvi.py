"""Meta-Validation Index (MVI).

"Validate the validator" — checks whether the governance pipeline itself
is behaving deterministically and consistently.

Three checks:
  1. Replay Stability: are replay results consistent for repeated runs
     of the same EPACK records?
  2. Recovery Consistency: given the same RecoveryState, does the engine
     always pick the same plan?
  3. TSI Coherence: is the TSI signal internally consistent (no impossible
     jumps, no NaN, bounded 0–1)?

Produces a single MVI score (0.0–1.0) that the post-recovery verifier
and enterprise audit can consume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .recovery_engine import RecoveryEngine, RecoveryPlan, RecoveryState


@dataclass(frozen=True)
class MVIResult:
    """Outcome of meta-validation."""
    mvi_score: float                    # 0.0–1.0
    replay_stability: float             # 0.0–1.0
    recovery_consistency: float         # 0.0–1.0
    tsi_coherence: float                # 0.0–1.0
    passed: bool
    details: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mvi_score": self.mvi_score,
            "replay_stability": self.replay_stability,
            "recovery_consistency": self.recovery_consistency,
            "tsi_coherence": self.tsi_coherence,
            "passed": self.passed,
            "details": self.details,
        }


class MetaValidationIndex:
    """Compute MVI from replay results, recovery engine, and TSI signals."""

    def __init__(
        self,
        pass_threshold: float = 0.80,
        replay_weight: float = 0.40,
        recovery_weight: float = 0.35,
        coherence_weight: float = 0.25,
    ) -> None:
        self.pass_threshold = pass_threshold
        self.replay_weight = replay_weight
        self.recovery_weight = recovery_weight
        self.coherence_weight = coherence_weight

    def check_replay_stability(
        self,
        replay_results_a: List[Dict[str, Any]],
        replay_results_b: List[Dict[str, Any]],
    ) -> Tuple[float, List[str]]:
        """Compare two replay runs of the same EPACK chain.

        Returns (stability_score, details).
        Score is 1.0 if both runs agree on all governance_match values.
        """
        details: List[str] = []
        if not replay_results_a or not replay_results_b:
            details.append("replay_stability:insufficient_data")
            return 0.5, details

        n = min(len(replay_results_a), len(replay_results_b))
        matches = 0
        for i in range(n):
            a_match = replay_results_a[i].get("governance_match", True)
            b_match = replay_results_b[i].get("governance_match", True)
            a_di = replay_results_a[i].get("determinism_index", 100.0)
            b_di = replay_results_b[i].get("determinism_index", 100.0)
            if a_match == b_match and abs(a_di - b_di) < 0.01:
                matches += 1
            else:
                details.append(f"replay_stability:divergence_at_record_{i}")

        score = matches / n if n > 0 else 0.0
        if score >= 1.0:
            details.append("replay_stability:perfect")
        return round(score, 4), details

    def check_recovery_consistency(
        self,
        engine: RecoveryEngine,
        state: RecoveryState,
        plans: List[RecoveryPlan],
        num_trials: int = 5,
    ) -> Tuple[float, List[str]]:
        """Run the engine N times with the same inputs.

        Deterministic engine should always pick the same plan.
        """
        details: List[str] = []
        if not plans:
            details.append("recovery_consistency:no_plans")
            return 1.0, details

        chosen_names: List[Optional[str]] = []
        for _ in range(num_trials):
            decision = engine.decide(state, plans, now_ms=1000000)
            name = decision.chosen.name if decision.chosen else None
            chosen_names.append(name)

        unique = set(chosen_names)
        if len(unique) == 1:
            score = 1.0
            details.append(f"recovery_consistency:deterministic:always={chosen_names[0]}")
        else:
            score = 1.0 / len(unique)
            details.append(f"recovery_consistency:NON_DETERMINISTIC:choices={unique}")

        return round(score, 4), details

    def check_tsi_coherence(
        self,
        tsi_values: List[float],
    ) -> Tuple[float, List[str]]:
        """Check TSI signal is internally consistent."""
        details: List[str] = []
        if not tsi_values:
            details.append("tsi_coherence:no_data")
            return 0.5, details

        issues = 0
        for i, v in enumerate(tsi_values):
            # Must be bounded 0–1
            if not (0.0 <= v <= 1.0):
                issues += 1
                details.append(f"tsi_coherence:out_of_bounds_at_{i}:{v}")
            # No NaN/inf
            if v != v or abs(v) == float("inf"):  # NaN or inf check
                issues += 1
                details.append(f"tsi_coherence:nan_or_inf_at_{i}")

        # Check for impossible jumps (>0.4 in one step)
        for i in range(1, len(tsi_values)):
            if abs(tsi_values[i] - tsi_values[i - 1]) > 0.40:
                issues += 1
                details.append(
                    f"tsi_coherence:impossible_jump_at_{i}:"
                    f"{tsi_values[i-1]:.3f}->{tsi_values[i]:.3f}"
                )

        n = len(tsi_values) + max(0, len(tsi_values) - 1)  # data points + transitions
        score = max(0.0, 1.0 - (issues / max(1, n)))
        if score >= 1.0:
            details.append("tsi_coherence:clean")
        return round(score, 4), details

    def compute(
        self,
        *,
        replay_results_a: Optional[List[Dict[str, Any]]] = None,
        replay_results_b: Optional[List[Dict[str, Any]]] = None,
        engine: Optional[RecoveryEngine] = None,
        state: Optional[RecoveryState] = None,
        plans: Optional[List[RecoveryPlan]] = None,
        tsi_values: Optional[List[float]] = None,
    ) -> MVIResult:
        """Compute overall MVI score."""
        all_details: List[str] = []

        # Replay stability
        r_score, r_details = self.check_replay_stability(
            replay_results_a or [], replay_results_b or []
        )
        all_details.extend(r_details)

        # Recovery consistency
        if engine and state and plans:
            c_score, c_details = self.check_recovery_consistency(engine, state, plans)
        else:
            c_score = 1.0
            c_details = ["recovery_consistency:skipped_no_engine"]
        all_details.extend(c_details)

        # TSI coherence
        t_score, t_details = self.check_tsi_coherence(tsi_values or [])
        all_details.extend(t_details)

        # Weighted MVI
        mvi = (
            self.replay_weight * r_score
            + self.recovery_weight * c_score
            + self.coherence_weight * t_score
        )
        mvi = round(mvi, 4)

        return MVIResult(
            mvi_score=mvi,
            replay_stability=r_score,
            recovery_consistency=c_score,
            tsi_coherence=t_score,
            passed=mvi >= self.pass_threshold,
            details=all_details,
        )
