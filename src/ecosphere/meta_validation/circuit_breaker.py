"""Recovery Circuit Breaker.

Prevents death-spiral recovery: if a plan fails N consecutive times,
trip the breaker open so the engine stops selecting it until cooldown expires.

States:
  CLOSED  — plan is eligible for selection
  OPEN    — plan is blocked (consecutive failures >= threshold)
  HALF_OPEN — cooldown expired, plan gets ONE retry attempt

Deterministic, no network calls, fully auditable via state_snapshot().
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class BreakerConfig:
    failure_threshold: int = 3        # consecutive failures to trip open
    cooldown_seconds: float = 120.0   # how long OPEN before HALF_OPEN
    half_open_max_attempts: int = 1   # retries allowed in HALF_OPEN


@dataclass
class PlanBreaker:
    """Per-plan circuit breaker state."""
    plan_name: str
    consecutive_failures: int = 0
    state: str = "CLOSED"             # CLOSED | OPEN | HALF_OPEN
    last_failure_ts: float = 0.0
    last_success_ts: float = 0.0
    half_open_attempts: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker:
    """Manages per-plan circuit breakers for the recovery engine."""

    def __init__(self, config: BreakerConfig = None) -> None:
        self.config = config or BreakerConfig()
        self._breakers: Dict[str, PlanBreaker] = {}

    def _get(self, plan_name: str) -> PlanBreaker:
        if plan_name not in self._breakers:
            self._breakers[plan_name] = PlanBreaker(plan_name=plan_name)
        return self._breakers[plan_name]

    def _maybe_transition(self, b: PlanBreaker, now: float) -> None:
        """Transition OPEN → HALF_OPEN if cooldown expired."""
        if b.state == "OPEN" and (now - b.last_failure_ts) >= self.config.cooldown_seconds:
            b.state = "HALF_OPEN"
            b.half_open_attempts = 0

    def excluded_plans(self, now: Optional[float] = None) -> Set[str]:
        """Return set of plan names currently blocked (OPEN state)."""
        now = now or time.time()
        blocked: Set[str] = set()
        for b in self._breakers.values():
            self._maybe_transition(b, now)
            if b.state == "OPEN":
                blocked.add(b.plan_name)
            elif b.state == "HALF_OPEN" and b.half_open_attempts >= self.config.half_open_max_attempts:
                blocked.add(b.plan_name)
        return blocked

    def record_success(self, plan_name: str, now: Optional[float] = None) -> None:
        """Plan was applied and TSI improved — reset breaker to CLOSED."""
        now = now or time.time()
        b = self._get(plan_name)
        b.consecutive_failures = 0
        b.state = "CLOSED"
        b.last_success_ts = now
        b.half_open_attempts = 0
        b.total_successes += 1

    def record_failure(self, plan_name: str, now: Optional[float] = None) -> None:
        """Plan was applied but TSI did not improve — increment failure count."""
        now = now or time.time()
        b = self._get(plan_name)
        b.consecutive_failures += 1
        b.total_failures += 1
        b.last_failure_ts = now

        if b.state == "HALF_OPEN":
            # Failed during probe — trip back to OPEN
            b.state = "OPEN"
            b.half_open_attempts = 0
        elif b.consecutive_failures >= self.config.failure_threshold:
            b.state = "OPEN"

    def record_half_open_attempt(self, plan_name: str) -> None:
        """Track a retry attempt during HALF_OPEN."""
        b = self._get(plan_name)
        if b.state == "HALF_OPEN":
            b.half_open_attempts += 1

    def state_snapshot(self) -> List[Dict[str, Any]]:
        """Auditable snapshot of all breaker states."""
        return [
            {
                "plan_name": b.plan_name,
                "state": b.state,
                "consecutive_failures": b.consecutive_failures,
                "total_failures": b.total_failures,
                "total_successes": b.total_successes,
                "last_failure_ts": b.last_failure_ts,
                "last_success_ts": b.last_success_ts,
            }
            for b in self._breakers.values()
        ]

    def reset(self, plan_name: Optional[str] = None) -> None:
        """Reset one or all breakers (e.g., manual override / break-glass)."""
        if plan_name:
            if plan_name in self._breakers:
                self._breakers[plan_name] = PlanBreaker(plan_name=plan_name)
        else:
            self._breakers.clear()
