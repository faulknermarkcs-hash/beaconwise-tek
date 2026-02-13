import pytest

from ecosphere.consensus.ledger.hooks import emit_stage_event
from ecosphere.consensus.ledger.reader import get_recent_events, _reset_events_for_test


@pytest.fixture(autouse=True)
def _reset():
    _reset_events_for_test()
    yield
    _reset_events_for_test()


def test_emit_stage_event_is_readable_by_reader():
    epack = "demo-epack"
    run_id = "demo-run"

    emit_stage_event(epack=epack, run_id=run_id, stage="tecl.verification.success", payload={"user_id": "x"})
    emit_stage_event(epack=epack, run_id=run_id, stage="tecl.scope_gate.pass", payload={"role_level": 1})
    emit_stage_event(epack=epack, run_id=run_id, stage="tecl.verification.expired", payload={"user_id": "y"})

    events = get_recent_events(epack_id=epack, stage_prefix="tecl.verification.", limit=10)
    assert len(events) == 2
    assert events[0]["stage"] == "tecl.verification.expired"
    assert events[1]["stage"] == "tecl.verification.success"
    assert "event_hash" in events[0]
    assert events[0]["payload"]["user_id"] == "y"
