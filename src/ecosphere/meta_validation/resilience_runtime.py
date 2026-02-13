"""V9 Resilience Runtime — closed-loop self-healing runtime.

Wires the resilience_policy DSL into the live kernel:
  1. TSI tracker produces live trust signals from interaction outcomes
  2. Dependency metrics from consensus config
  3. Recovery engine selects plans when triggers fire
  4. Damping stabilizer controls rollout velocity
  5. Circuit breaker prevents death-spiral re-selection
  6. Post-recovery verifier closes the loop
  7. All actions emit EPACK audit events
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .recovery_engine import RecoveryEngine, RecoveryPlan, RecoveryState, RecoveryDecision
from .damping_stabilizer import DampingStabilizer
from .circuit_breaker import CircuitBreaker
from .tsi_tracker import TSITracker, InteractionOutcome, TSISignal
from .post_recovery_verifier import PostRecoveryVerifier, VerificationResult


@dataclass
class TrustSnapshot:
    """Minimal live signal bundle used to make recovery decisions."""
    tsi_current: float
    tsi_forecast_15m: float
    der_density: float
    dep_concentration_index: float
    degraded: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tsi_current": self.tsi_current,
            "tsi_forecast_15m": self.tsi_forecast_15m,
            "der_density": self.der_density,
            "dep_concentration_index": self.dep_concentration_index,
            "degraded": self.degraded,
        }


class ResilienceRuntime:
    """Holds all resilience components and orchestrates the recovery loop."""

    def __init__(
        self,
        engine: RecoveryEngine,
        plans: List[RecoveryPlan],
        damping: Optional[DampingStabilizer] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        tsi_tracker: Optional[TSITracker] = None,
        verifier: Optional[PostRecoveryVerifier] = None,
        enabled: bool = True,
    ) -> None:
        self.engine = engine
        self.plans = plans
        self.damping = damping
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.tsi_tracker = tsi_tracker or TSITracker()
        self.verifier = verifier or PostRecoveryVerifier(targets=engine.targets)
        self.enabled = enabled

        # Mutable state
        self.last_decision: Optional[RecoveryDecision] = None
        self.last_applied_plan: Optional[RecoveryPlan] = None
        self.tsi_at_recovery: Optional[float] = None

    def record_outcome(self, status: str, validator_agreement: float = 0.5,
                       latency_ms: int = 0, challenger_fired: bool = False) -> None:
        """Feed an interaction outcome into the TSI tracker."""
        import time
        self.tsi_tracker.record(InteractionOutcome(
            timestamp=time.time(),
            status=status,
            validator_agreement=validator_agreement,
            latency_ms=latency_ms,
            challenger_fired=challenger_fired,
            recovery_active=self.last_applied_plan is not None,
        ))

    def current_signal(self) -> TSISignal:
        """Get current TSI signal from the tracker."""
        return self.tsi_tracker.signal()

    def dependency_metrics(self, provider_weights: Dict[str, float]) -> Tuple[float, float]:
        """Compute (density, concentration_index) from active provider weights.

        provider_weights: {provider_name: weight} e.g. {"openai": 0.55, "groq": 0.25, "xai": 0.20}
        """
        if not provider_weights:
            return 0.0, 1.0

        total = sum(provider_weights.values()) or 1.0
        norm = {k: v / total for k, v in provider_weights.items()}

        # HHI-style concentration index
        hhi = sum(p * p for p in norm.values())
        concentration = max(0.0, min(1.0, hhi))

        # Density: interaction edges among providers
        n = len(norm)
        density = 0.0 if n <= 1 else (n - 1) / (n * (n - 1))

        return density, concentration

    def maybe_recover(self, snapshot: TrustSnapshot) -> Optional[RecoveryDecision]:
        """Check triggers and potentially select a recovery plan.

        Returns the decision (with or without a chosen plan).
        """
        if not self.enabled:
            return None

        state = RecoveryState(
            tsi_current=snapshot.tsi_current,
            tsi_forecast_15m=snapshot.tsi_forecast_15m,
            der_density=snapshot.der_density,
            concentration_index=snapshot.dep_concentration_index,
            system_status="degraded" if snapshot.degraded else "ok",
            oscillation_index=0.0,
        )

        # Get circuit-breaker exclusions
        excluded = self.circuit_breaker.excluded_plans()

        # Respect damping cooldown
        if self.damping and self.damping.in_cooldown():
            return None

        decision = self.engine.decide(state, self.plans, excluded_plans=excluded)
        self.last_decision = decision

        # Apply damping to chosen plan
        if decision.chosen and self.damping:
            decision.chosen = self.damping.damp_plan(
                state, decision.chosen, targets=self.engine.targets,
            )

        if decision.chosen:
            self.last_applied_plan = decision.chosen
            self.tsi_at_recovery = snapshot.tsi_current

        return decision

    def verify_recovery(self, current_tsi: float, replay_results: Optional[List[Dict[str, Any]]] = None) -> Optional[VerificationResult]:
        """Verify that the last applied recovery actually helped."""
        if not self.last_applied_plan or self.tsi_at_recovery is None:
            return None

        result = self.verifier.verify(
            plan=self.last_applied_plan,
            tsi_before=self.tsi_at_recovery,
            tsi_after=current_tsi,
            replay_results=replay_results,
        )

        # Update circuit breaker
        if result.tsi_improved:
            self.circuit_breaker.record_success(self.last_applied_plan.name)
        else:
            self.circuit_breaker.record_failure(self.last_applied_plan.name)

        # Clear recovery state
        if result.recommend_rollback:
            self.last_applied_plan = None
            self.tsi_at_recovery = None

        return result
