"""TSI tracker tests."""
import time
import pytest

from ecosphere.meta_validation.tsi_tracker import TSITracker, InteractionOutcome, TSISignal


def _outcome(status="PASS", agreement=0.8, ts=None):
    return InteractionOutcome(
        timestamp=ts or time.time(),
        status=status,
        validator_agreement=agreement,
        latency_ms=100,
    )


def test_empty_tracker_returns_defaults():
    t = TSITracker(window_size=10)
    sig = t.signal()
    assert sig.tsi_current == 0.82
    assert sig.window_size == 0


def test_single_pass_outcome():
    t = TSITracker(window_size=10)
    t.record(_outcome("PASS", 0.9))
    sig = t.signal()
    assert sig.window_size == 1
    assert sig.tsi_current > 0.80
    assert sig.pass_rate == 1.0


def test_refuse_lowers_tsi():
    t = TSITracker(window_size=10)
    t.record(_outcome("PASS", 0.9))
    sig_pass = t.signal()
    t.record(_outcome("REFUSE", 0.3))
    sig_refuse = t.signal()
    assert sig_refuse.tsi_current < sig_pass.tsi_current


def test_error_lowers_tsi_further():
    t = TSITracker(window_size=10)
    for _ in range(5):
        t.record(_outcome("ERROR", 0.1))
    sig = t.signal()
    assert sig.tsi_current < 0.50
    assert sig.error_rate == 1.0


def test_window_size_respected():
    t = TSITracker(window_size=5)
    for _ in range(10):
        t.record(_outcome("PASS", 0.9))
    sig = t.signal()
    assert sig.window_size == 5


def test_mixed_outcomes():
    t = TSITracker(window_size=20)
    for _ in range(8):
        t.record(_outcome("PASS", 0.85))
    for _ in range(2):
        t.record(_outcome("REFUSE", 0.3))
    sig = t.signal()
    assert sig.pass_rate == 0.8
    assert sig.refuse_rate == 0.2
    assert 0.60 < sig.tsi_current < 0.95


def test_trend_slope_positive_on_improvement():
    t = TSITracker(window_size=20)
    now = time.time()
    # Start bad, get better
    for i in range(5):
        t.record(_outcome("REFUSE", 0.3, ts=now + i))
    for i in range(5):
        t.record(_outcome("PASS", 0.9, ts=now + 5 + i))
    sig = t.signal(now=now + 10)
    assert sig.trend_slope > 0, "Improving trend should have positive slope"


def test_forecast_bounded():
    t = TSITracker(window_size=10)
    for _ in range(10):
        t.record(_outcome("PASS", 1.0))
    sig = t.signal()
    assert 0.0 <= sig.tsi_forecast_15m <= 1.0


def test_clear():
    t = TSITracker(window_size=10)
    t.record(_outcome("PASS", 0.9))
    t.clear()
    sig = t.signal()
    assert sig.window_size == 0
