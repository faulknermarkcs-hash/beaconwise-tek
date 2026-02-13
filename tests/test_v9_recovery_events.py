"""Recovery EPACK event tests."""
import pytest

from ecosphere.meta_validation.recovery_events import (
    emit_recovery_triggered,
    emit_recovery_decision,
    emit_recovery_applied,
    emit_recovery_verified,
    emit_recovery_rollback,
    emit_circuit_breaker_event,
)
from ecosphere.consensus.ledger.reader import _EPACK_EVENTS, clear_epack_events_for_test


def setup_function():
    clear_epack_events_for_test()


def test_emit_recovery_triggered():
    h = emit_recovery_triggered(
        epack="ep1", run_id="r1", reason="tsi_low",
        tsi_before=0.60, tsi_forecast=0.55,
    )
    assert isinstance(h, str) and len(h) == 64
    events = _EPACK_EVENTS.get("ep1", [])
    assert len(events) == 1
    assert events[0]["stage"] == "RECOVERY_TRIGGERED"


def test_emit_recovery_decision():
    h = emit_recovery_decision(epack="ep2", run_id="r2", decision={"chosen": "plan_a"})
    events = _EPACK_EVENTS.get("ep2", [])
    assert events[0]["stage"] == "RECOVERY_DECISION"


def test_emit_recovery_applied():
    h = emit_recovery_applied(
        epack="ep3", run_id="r3", plan_name="plan_a",
        routing_patch={"validators": "add:claude"},
    )
    events = _EPACK_EVENTS.get("ep3", [])
    assert events[0]["payload"]["plan_name"] == "plan_a"


def test_emit_recovery_verified():
    h = emit_recovery_verified(epack="ep4", run_id="r4", verification={"improved": True})
    events = _EPACK_EVENTS.get("ep4", [])
    assert events[0]["stage"] == "RECOVERY_VERIFIED"


def test_emit_recovery_rollback():
    h = emit_recovery_rollback(
        epack="ep5", run_id="r5", plan_name="plan_a", reasons=["tsi_degraded"],
    )
    events = _EPACK_EVENTS.get("ep5", [])
    assert events[0]["stage"] == "RECOVERY_ROLLBACK"


def test_emit_circuit_breaker():
    h = emit_circuit_breaker_event(
        epack="ep6", run_id="r6", plan_name="plan_a",
        breaker_state="OPEN", consecutive_failures=3,
    )
    events = _EPACK_EVENTS.get("ep6", [])
    assert events[0]["stage"] == "CIRCUIT_BREAKER"


def test_chain_hash_linkage():
    h1 = emit_recovery_triggered(
        epack="ep7", run_id="r7", reason="tsi_low",
        tsi_before=0.60, tsi_forecast=0.55,
    )
    h2 = emit_recovery_decision(
        epack="ep7", run_id="r7", decision={"chosen": "plan_a"},
        prev_hash=h1,
    )
    events = _EPACK_EVENTS.get("ep7", [])
    assert len(events) == 2
    assert events[1]["prev_hash"] == h1
