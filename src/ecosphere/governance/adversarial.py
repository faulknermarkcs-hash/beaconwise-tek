# src/ecosphere/governance/adversarial.py
"""BeaconWise Adversarial Governance Defense Layer (V7 Capability 5).

Resilience against governance manipulation:
  - consensus poisoning detection
  - adversarial prompt detection (supplements existing safety layers)
  - model manipulation anomaly detection
  - signal verification hooks
  - adversarial governance test suite helpers

Principle: Transparency without resilience is insufficient.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ecosphere.utils.stable import stable_hash


# ── Anomaly Detection ─────────────────────────────────────────────

@dataclass
class AnomalySignal:
    """A detected governance anomaly."""
    signal_type: str       # e.g. "confidence_spike", "route_flip", "consensus_divergence"
    severity: str          # "low", "medium", "high", "critical"
    description: str
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)


class GovernanceAnomalyDetector:
    """Tracks governance telemetry and flags anomalous patterns.

    Monitors for:
    - Sudden confidence spikes/drops (model manipulation)
    - Route flipping (adversarial input probing)
    - Consensus divergence (poisoning)
    - Unusual validation failure patterns
    """

    def __init__(self, window_size: int = 50):
        self._window_size = window_size
        self._confidence_history: List[float] = []
        self._route_history: List[str] = []
        self._validation_failures: int = 0
        self._total_interactions: int = 0
        self._signals: List[AnomalySignal] = []

    def record_interaction(
        self,
        *,
        confidence: float,
        route: str,
        validation_ok: bool,
        consensus_scores: Optional[List[float]] = None,
    ) -> List[AnomalySignal]:
        """Record a governed interaction and return any new anomaly signals."""
        new_signals: List[AnomalySignal] = []
        self._total_interactions += 1

        # Track confidence
        self._confidence_history.append(confidence)
        if len(self._confidence_history) > self._window_size:
            self._confidence_history.pop(0)

        # Track routes
        self._route_history.append(route)
        if len(self._route_history) > self._window_size:
            self._route_history.pop(0)

        # Track validation
        if not validation_ok:
            self._validation_failures += 1

        # Check for confidence spike
        sig = self._check_confidence_anomaly(confidence)
        if sig:
            new_signals.append(sig)

        # Check for route flipping
        sig = self._check_route_flipping()
        if sig:
            new_signals.append(sig)

        # Check for validation failure rate
        sig = self._check_validation_rate()
        if sig:
            new_signals.append(sig)

        # Check consensus divergence
        if consensus_scores:
            sig = self._check_consensus_divergence(consensus_scores)
            if sig:
                new_signals.append(sig)

        self._signals.extend(new_signals)
        return new_signals

    def _check_confidence_anomaly(self, current: float) -> Optional[AnomalySignal]:
        """Detect sudden confidence changes (possible model manipulation)."""
        if len(self._confidence_history) < 5:
            return None
        recent = self._confidence_history[-5:]
        mean = sum(recent) / len(recent)
        # Check for spike: current is >0.3 away from recent mean
        if abs(current - mean) > 0.3:
            return AnomalySignal(
                signal_type="confidence_spike",
                severity="medium",
                description=f"Confidence {current:.2f} deviates from recent mean {mean:.2f}",
                timestamp=time.time(),
                details={"current": current, "mean": mean, "delta": abs(current - mean)},
            )
        return None

    def _check_route_flipping(self) -> Optional[AnomalySignal]:
        """Detect rapid route changes (adversarial input probing)."""
        if len(self._route_history) < 6:
            return None
        recent = self._route_history[-6:]
        changes = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i - 1])
        if changes >= 4:
            return AnomalySignal(
                signal_type="route_flip",
                severity="high",
                description=f"Route changed {changes} times in last 6 interactions",
                timestamp=time.time(),
                details={"route_history": recent, "changes": changes},
            )
        return None

    def _check_validation_rate(self) -> Optional[AnomalySignal]:
        """Detect high validation failure rate."""
        if self._total_interactions < 10:
            return None
        rate = self._validation_failures / self._total_interactions
        if rate > 0.4:
            return AnomalySignal(
                signal_type="validation_failure_rate",
                severity="high",
                description=f"Validation failure rate {rate:.1%} exceeds 40% threshold",
                timestamp=time.time(),
                details={"failures": self._validation_failures, "total": self._total_interactions, "rate": rate},
            )
        return None

    def _check_consensus_divergence(self, scores: List[float]) -> Optional[AnomalySignal]:
        """Detect consensus poisoning via model divergence."""
        if len(scores) < 2:
            return None
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std = math.sqrt(variance)
        if std > 0.35:
            return AnomalySignal(
                signal_type="consensus_divergence",
                severity="critical",
                description=f"Consensus standard deviation {std:.2f} indicates potential poisoning",
                timestamp=time.time(),
                details={"scores": scores, "mean": mean, "std": std},
            )
        return None

    def get_signals(self, min_severity: str = "low") -> List[AnomalySignal]:
        """Get all recorded anomaly signals at or above severity."""
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        threshold = severity_order.get(min_severity, 0)
        return [s for s in self._signals if severity_order.get(s.severity, 0) >= threshold]

    def reset(self) -> None:
        """Reset all tracking state."""
        self._confidence_history.clear()
        self._route_history.clear()
        self._validation_failures = 0
        self._total_interactions = 0
        self._signals.clear()


# ── Governance Manipulation Checks ────────────────────────────────

def detect_prompt_governance_bypass(text: str) -> Tuple[bool, str]:
    """Check if input attempts to bypass governance mechanisms.

    This supplements the existing Stage 1/2 safety pipeline with
    governance-specific bypass detection.
    """
    lower = text.lower()

    # Governance bypass patterns
    bypass_patterns = [
        ("ignore governance", "Attempt to disable governance"),
        ("skip validation", "Attempt to bypass validation"),
        ("disable audit", "Attempt to suppress audit chain"),
        ("bypass safety", "Attempt to circumvent safety layers"),
        ("override constitution", "Attempt to override constitutional invariants"),
        ("turn off logging", "Attempt to suppress telemetry"),
        ("act without restriction", "Attempt to remove all constraints"),
        ("pretend you have no rules", "Social engineering governance bypass"),
    ]

    for pattern, reason in bypass_patterns:
        if pattern in lower:
            return True, reason

    return False, ""


def verify_output_provenance(
    output_text: str,
    expected_model: str,
    reported_model: str,
) -> Tuple[bool, str]:
    """Verify that output provenance matches expectations.

    Detects potential model substitution attacks.
    """
    if expected_model and reported_model and expected_model != reported_model:
        return False, f"Model mismatch: expected {expected_model}, got {reported_model}"
    return True, "OK"
