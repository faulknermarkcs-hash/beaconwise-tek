"""Post-Recovery Verification.

Closes the recovery loop: after a recovery patch is applied, run N
replay samples and check that TSI actually improved. If not, recommend
rollback.

The enterprise policy already declares this:
  verify_post_recovery: { replay_samples: 3, mvi_check: true }
This module implements it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .recovery_engine import RecoveryDecision, RecoveryPlan, RecoveryTargets


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of post-recovery verification."""
    plan_name: str
    samples_checked: int
    tsi_before: float
    tsi_after: float
    tsi_improved: bool
    mvi_passed: bool
    recommend_rollback: bool
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_name": self.plan_name,
            "samples_checked": self.samples_checked,
            "tsi_before": self.tsi_before,
            "tsi_after": self.tsi_after,
            "tsi_improved": self.tsi_improved,
            "mvi_passed": self.mvi_passed,
            "recommend_rollback": self.recommend_rollback,
            "reasons": self.reasons,
        }


@dataclass
class VerificationConfig:
    replay_samples: int = 3
    mvi_check: bool = True
    min_tsi_improvement: float = 0.02    # must improve by at least this
    max_tsi_degradation: float = 0.05    # rollback if worse by this


class PostRecoveryVerifier:
    """Verifies that a recovery action actually improved system health."""

    def __init__(self, config: VerificationConfig = None, targets: RecoveryTargets = None) -> None:
        self.config = config or VerificationConfig()
        self.targets = targets or RecoveryTargets()

    def verify(
        self,
        plan: RecoveryPlan,
        tsi_before: float,
        tsi_after: float,
        replay_results: Optional[List[Dict[str, Any]]] = None,
    ) -> VerificationResult:
        """Check whether recovery improved things.

        Args:
            plan: The plan that was applied
            tsi_before: TSI at time of recovery decision
            tsi_after: TSI after recovery patch was active for verification window
            replay_results: Optional replay sample results for MVI check
        """
        reasons: List[str] = []
        tsi_improved = False
        mvi_passed = True
        recommend_rollback = False

        delta = tsi_after - tsi_before

        # Check TSI improvement
        if delta >= self.config.min_tsi_improvement:
            tsi_improved = True
        elif delta < 0:
            reasons.append(f"tsi_degraded:{delta:+.4f}")
            if abs(delta) >= self.config.max_tsi_degradation:
                recommend_rollback = True
                reasons.append("rollback:tsi_degradation_exceeds_threshold")
        else:
            reasons.append(f"tsi_flat:delta={delta:+.4f}<min_improvement={self.config.min_tsi_improvement}")

        # Check if TSI still below critical
        if tsi_after < self.targets.tsi_critical:
            reasons.append(f"tsi_still_critical:{tsi_after:.3f}<{self.targets.tsi_critical}")
            recommend_rollback = True

        # MVI check: replay samples should all show governance_match
        samples_checked = 0
        if self.config.mvi_check and replay_results:
            samples_checked = len(replay_results)
            mismatches = sum(
                1 for r in replay_results
                if not r.get("governance_match", True)
            )
            if mismatches > 0:
                mvi_passed = False
                reasons.append(f"mvi_failed:{mismatches}/{samples_checked}_governance_mismatches")
                recommend_rollback = True

        if not reasons:
            reasons.append("recovery_verified_ok")

        return VerificationResult(
            plan_name=plan.name,
            samples_checked=samples_checked,
            tsi_before=tsi_before,
            tsi_after=tsi_after,
            tsi_improved=tsi_improved,
            mvi_passed=mvi_passed,
            recommend_rollback=recommend_rollback,
            reasons=reasons,
        )
