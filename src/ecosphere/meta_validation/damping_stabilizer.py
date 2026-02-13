"""Recovery Damping Stabilizer (RDS).

Applies PID-inspired damping to reduce recovery overshoot/oscillation risk.
Intentionally conservative and deterministic for auditability.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict
import time

from .recovery_engine import RecoveryPlan, RecoveryState, RecoveryTargets


@dataclass
class PIDParams:
    kp: float = 0.5
    ki: float = 0.2
    kd: float = 0.1
    integral_cap: float = 2.0


@dataclass
class DampingHints:
    canary_pct: float
    cooldown_seconds: int
    note: str = "pid_damped"


class DampingStabilizer:
    """PID-inspired damping for recovery rollout velocity."""

    def __init__(self, pid: PIDParams, max_oscillation: float = 0.15, cooldown_seconds: int = 60) -> None:
        self.pid = pid
        self.max_oscillation = max_oscillation
        self.cooldown_seconds = cooldown_seconds
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_applied_ts = 0.0

    def in_cooldown(self) -> bool:
        return (time.time() - self._last_applied_ts) < float(self.cooldown_seconds)

    def damp_plan(
        self,
        state: RecoveryState,
        plan: RecoveryPlan,
        *,
        targets: RecoveryTargets,
    ) -> RecoveryPlan:
        """Return a new RecoveryPlan with RDS hints injected into routing_patch."""
        target_tsi = targets.tsi_target
        error = max(0.0, target_tsi - state.tsi_forecast_15m)

        # PID compute
        self._integral = max(-self.pid.integral_cap, min(self.pid.integral_cap, self._integral + error))
        deriv = error - self._prev_error
        self._prev_error = error
        u = (self.pid.kp * error) + (self.pid.ki * self._integral) + (self.pid.kd * deriv)

        # Map u to canary rollout percent [0.15, 1.0]
        canary = 0.15 + min(0.85, max(0.0, u))

        # High concentration or critical forecast → bump rollout
        if state.concentration_index >= 0.75 or state.tsi_forecast_15m < targets.tsi_critical:
            canary = min(1.0, canary + 0.15)

        # High oscillation → reduce rollout to avoid yo-yo
        if state.oscillation_index > self.max_oscillation:
            canary = max(0.15, canary * 0.8)

        hints = DampingHints(canary_pct=round(canary, 3), cooldown_seconds=self.cooldown_seconds)
        self._last_applied_ts = time.time()

        # Build new plan with RDS hints injected
        patch = dict(plan.routing_patch or {})
        patch.setdefault("rds", {})
        patch["rds"].update(asdict(hints))

        from dataclasses import replace
        return replace(plan, routing_patch=patch) if hasattr(plan, '__dataclass_fields__') else plan

    def reset(self) -> None:
        """Reset PID state (e.g., after manual override)."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_applied_ts = 0.0
