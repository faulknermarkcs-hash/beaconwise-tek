"""Circuit breaker tests."""
import time
import pytest

from ecosphere.meta_validation.circuit_breaker import CircuitBreaker, BreakerConfig


def test_new_plan_is_closed():
    cb = CircuitBreaker()
    assert "plan_a" not in cb.excluded_plans()


def test_breaker_trips_after_threshold():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=3))
    for _ in range(3):
        cb.record_failure("plan_a")
    assert "plan_a" in cb.excluded_plans()


def test_success_resets_breaker():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=2))
    cb.record_failure("plan_a")
    cb.record_failure("plan_a")
    assert "plan_a" in cb.excluded_plans()
    cb.record_success("plan_a")
    assert "plan_a" not in cb.excluded_plans()


def test_cooldown_transitions_to_half_open():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=2, cooldown_seconds=0.01))
    cb.record_failure("plan_a")
    cb.record_failure("plan_a")
    assert "plan_a" in cb.excluded_plans()
    time.sleep(0.02)
    assert "plan_a" not in cb.excluded_plans()
    b = cb._get("plan_a")
    assert b.state == "HALF_OPEN"


def test_half_open_failure_reopens():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=2, cooldown_seconds=0.01))
    cb.record_failure("plan_a")
    cb.record_failure("plan_a")
    time.sleep(0.02)
    cb.excluded_plans()  # trigger transition
    cb.record_failure("plan_a")
    assert cb._get("plan_a").state == "OPEN"


def test_half_open_success_closes():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=2, cooldown_seconds=0.01))
    cb.record_failure("plan_a")
    cb.record_failure("plan_a")
    time.sleep(0.02)
    cb.excluded_plans()
    cb.record_success("plan_a")
    assert cb._get("plan_a").state == "CLOSED"
    assert cb._get("plan_a").consecutive_failures == 0


def test_multiple_plans_independent():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=2))
    cb.record_failure("plan_a")
    cb.record_failure("plan_a")
    cb.record_failure("plan_b")
    assert "plan_a" in cb.excluded_plans()
    assert "plan_b" not in cb.excluded_plans()


def test_state_snapshot():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=2))
    cb.record_failure("plan_a")
    cb.record_success("plan_b")
    snap = cb.state_snapshot()
    assert len(snap) == 2
    names = {s["plan_name"] for s in snap}
    assert names == {"plan_a", "plan_b"}


def test_reset_single():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=2))
    cb.record_failure("plan_a")
    cb.record_failure("plan_a")
    cb.reset("plan_a")
    assert "plan_a" not in cb.excluded_plans()


def test_reset_all():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=1))
    cb.record_failure("plan_a")
    cb.record_failure("plan_b")
    cb.reset()
    assert len(cb.excluded_plans()) == 0


def test_below_threshold_not_excluded():
    cb = CircuitBreaker(BreakerConfig(failure_threshold=3))
    cb.record_failure("plan_a")
    cb.record_failure("plan_a")
    assert "plan_a" not in cb.excluded_plans()
