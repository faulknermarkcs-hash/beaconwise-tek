# tests/test_epack_reader_hooks.py
import pytest

from ecosphere.consensus.ledger.hooks import emit_stage_event
from ecosphere.consensus.ledger.reader import get_recent_events, clear_events


def test_emit_stage_event_is_readable_by_reader():
    clear_events()
    epack_id = "epack-test"
    run_id = "run-test"

    h1 = emit_stage_event(epack=epack_id, run_id=run_id, stage="tecl.verification.success", payload={"role":"physician"})
    assert isinstance(h1, str) and len(h1) >= 16

    events = get_recent_events(epack_id=epack_id, stage_prefix="tecl.verification.", limit=5)
    assert len(events) == 1
    evt = events[0]
    assert evt["stage"] == "tecl.verification.success"
    assert evt["payload"]["role"] == "physician"
    assert evt["event_hash"] == h1
