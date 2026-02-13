"""Sliding-Window Trust Stability Index (TSI) Tracker.

Replaces the hardcoded 0.85/0.55 in the kernel with a proper aggregator
that tracks recent interaction outcomes and produces a weighted TSI signal.

Design:
  - Fixed-size circular buffer of interaction outcomes
  - Exponential decay weighting (recent outcomes matter more)
  - Aggregates: pass/refuse/error rates, validator agreement, latency
  - Produces current TSI + simple forecast (linear extrapolation)
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class InteractionOutcome:
    """Single interaction outcome fed into the TSI tracker."""
    timestamp: float
    status: str                    # PASS | WARN | REFUSE | ERROR
    validator_agreement: float     # 0.0–1.0 (avg validator confidence)
    latency_ms: int = 0
    challenger_fired: bool = False
    recovery_active: bool = False


@dataclass
class TSISignal:
    """Output signal from the tracker."""
    tsi_current: float
    tsi_forecast_15m: float
    window_size: int
    pass_rate: float
    refuse_rate: float
    error_rate: float
    avg_agreement: float
    trend_slope: float             # positive = improving


class TSITracker:
    """Sliding-window TSI aggregator with exponential decay."""

    # Base TSI contribution by status
    STATUS_BASE: Dict[str, float] = {
        "PASS": 0.90,
        "WARN": 0.70,
        "REFUSE": 0.45,
        "ERROR": 0.30,
    }

    def __init__(
        self,
        window_size: int = 20,
        decay_lambda: float = 0.1,
        agreement_weight: float = 0.20,
        latency_penalty_per_s: float = 0.02,
        challenger_penalty: float = 0.03,
    ) -> None:
        self.window_size = max(5, window_size)
        self.decay_lambda = decay_lambda
        self.agreement_weight = agreement_weight
        self.latency_penalty_per_s = latency_penalty_per_s
        self.challenger_penalty = challenger_penalty
        self._buffer: Deque[InteractionOutcome] = deque(maxlen=self.window_size)

    def record(self, outcome: InteractionOutcome) -> None:
        """Push an interaction outcome into the sliding window."""
        self._buffer.append(outcome)

    def signal(self, now: Optional[float] = None) -> TSISignal:
        """Compute current TSI signal from the window."""
        now = now or time.time()

        if not self._buffer:
            return TSISignal(
                tsi_current=0.82, tsi_forecast_15m=0.80,
                window_size=0, pass_rate=0.0, refuse_rate=0.0,
                error_rate=0.0, avg_agreement=0.0, trend_slope=0.0,
            )

        # Compute per-outcome scores with exponential decay
        scores: List[Tuple[float, float]] = []  # (weight, score)
        total_weight = 0.0
        status_counts: Dict[str, int] = {"PASS": 0, "WARN": 0, "REFUSE": 0, "ERROR": 0}
        agreement_sum = 0.0

        for o in self._buffer:
            age_s = max(0.0, now - o.timestamp)
            weight = math.exp(-self.decay_lambda * age_s / 60.0)  # decay per minute

            base = self.STATUS_BASE.get(o.status, 0.50)

            # Agreement bonus/penalty
            agreement_mod = self.agreement_weight * (o.validator_agreement - 0.5)

            # Latency penalty
            lat_pen = self.latency_penalty_per_s * (o.latency_ms / 1000.0)

            # Challenger penalty (challenger firing means governance stress)
            ch_pen = self.challenger_penalty if o.challenger_fired else 0.0

            score = max(0.0, min(1.0, base + agreement_mod - lat_pen - ch_pen))
            scores.append((weight, score))
            total_weight += weight

            status_counts[o.status] = status_counts.get(o.status, 0) + 1
            agreement_sum += o.validator_agreement

        # Weighted TSI
        if total_weight > 0:
            tsi = sum(w * s for w, s in scores) / total_weight
        else:
            tsi = 0.50

        n = len(self._buffer)
        pass_rate = status_counts.get("PASS", 0) / n
        refuse_rate = status_counts.get("REFUSE", 0) / n
        error_rate = status_counts.get("ERROR", 0) / n
        avg_agreement = agreement_sum / n

        # Trend: simple linear slope over last min(10, n) weighted scores
        trend_n = min(10, len(scores))
        trend_slope = 0.0
        if trend_n >= 3:
            recent = [s for _, s in scores[-trend_n:]]
            x_mean = (trend_n - 1) / 2.0
            y_mean = sum(recent) / trend_n
            num = sum((i - x_mean) * (recent[i] - y_mean) for i in range(trend_n))
            den = sum((i - x_mean) ** 2 for i in range(trend_n))
            trend_slope = num / den if den > 0 else 0.0

        # Forecast: linear extrapolation 15 min
        forecast = max(0.0, min(1.0, tsi + trend_slope * 2.0))

        return TSISignal(
            tsi_current=round(tsi, 4),
            tsi_forecast_15m=round(forecast, 4),
            window_size=n,
            pass_rate=round(pass_rate, 3),
            refuse_rate=round(refuse_rate, 3),
            error_rate=round(error_rate, 3),
            avg_agreement=round(avg_agreement, 3),
            trend_slope=round(trend_slope, 5),
        )

    def clear(self) -> None:
        self._buffer.clear()
