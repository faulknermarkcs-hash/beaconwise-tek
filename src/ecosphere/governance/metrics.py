# src/ecosphere/governance/metrics.py
"""BeaconWise Governance Observability & Metrics (V7 Capability 7).

Measurable metrics for:
  - transparency coverage
  - determinism stability
  - audit completeness
  - verification latency
  - governance health dashboard data

Principle: AI is governed, never blindly trusted.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GovernanceMetrics:
    """Rolling governance health metrics."""

    # Counters
    total_interactions: int = 0
    total_epacks: int = 0
    total_bound: int = 0        # safety blocks
    total_defer: int = 0        # high-stakes deferrals
    total_reflect: int = 0      # complexity confirmations
    total_tdm: int = 0          # normal generation
    total_validation_pass: int = 0
    total_validation_fail: int = 0
    total_scope_pass: int = 0
    total_scope_refuse: int = 0
    total_scope_rewrite: int = 0

    # Latency tracking (ms)
    _latencies: List[float] = field(default_factory=list)

    # Anomaly counts
    anomaly_signals: int = 0
    critical_violations: int = 0

    def record_interaction(
        self,
        *,
        route: str = "TDM",
        validation_ok: bool = True,
        scope_decision: str = "N/A",
        latency_ms: float = 0.0,
    ) -> None:
        self.total_interactions += 1
        self.total_epacks += 1

        route_upper = route.upper()
        if route_upper == "BOUND":
            self.total_bound += 1
        elif route_upper == "DEFER":
            self.total_defer += 1
        elif route_upper == "REFLECT":
            self.total_reflect += 1
        else:
            self.total_tdm += 1

        if validation_ok:
            self.total_validation_pass += 1
        else:
            self.total_validation_fail += 1

        scope_upper = scope_decision.upper()
        if scope_upper == "PASS":
            self.total_scope_pass += 1
        elif scope_upper == "REFUSE":
            self.total_scope_refuse += 1
        elif scope_upper == "REWRITE":
            self.total_scope_rewrite += 1

        if latency_ms > 0:
            self._latencies.append(latency_ms)
            if len(self._latencies) > 1000:
                self._latencies = self._latencies[-500:]

    @property
    def audit_completeness(self) -> float:
        """Ratio of EPACKs to interactions (should be 1.0)."""
        if self.total_interactions == 0:
            return 1.0
        return self.total_epacks / self.total_interactions

    @property
    def safety_block_rate(self) -> float:
        if self.total_interactions == 0:
            return 0.0
        return self.total_bound / self.total_interactions

    @property
    def validation_pass_rate(self) -> float:
        total = self.total_validation_pass + self.total_validation_fail
        if total == 0:
            return 1.0
        return self.total_validation_pass / total

    @property
    def avg_latency_ms(self) -> float:
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)

    @property
    def p95_latency_ms(self) -> float:
        if not self._latencies:
            return 0.0
        sorted_lat = sorted(self._latencies)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    def dashboard(self) -> Dict[str, Any]:
        """Generate governance dashboard data."""
        return {
            "governance_version": "beaconwise-v7.0",
            "total_interactions": self.total_interactions,
            "audit_completeness": self.audit_completeness,
            "safety_block_rate": self.safety_block_rate,
            "validation_pass_rate": self.validation_pass_rate,
            "routing_distribution": {
                "BOUND": self.total_bound,
                "DEFER": self.total_defer,
                "REFLECT": self.total_reflect,
                "TDM": self.total_tdm,
            },
            "scope_distribution": {
                "PASS": self.total_scope_pass,
                "REFUSE": self.total_scope_refuse,
                "REWRITE": self.total_scope_rewrite,
            },
            "latency": {
                "avg_ms": round(self.avg_latency_ms, 1),
                "p95_ms": round(self.p95_latency_ms, 1),
            },
            "anomaly_signals": self.anomaly_signals,
            "critical_violations": self.critical_violations,
        }
