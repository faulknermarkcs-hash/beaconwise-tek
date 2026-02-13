"""EPACK reader + hooks — persistence and filtering.

NOTE: Each test self-sets TECL_EPACK_DIR for runner independence.
The autouse fixture still works under pytest; both paths are clean.
"""
import json
import os

import pytest

from ecosphere.consensus.ledger.hooks import emit_stage_event
from ecosphere.consensus.ledger.reader import clear_epack_events_for_test, get_recent_events


@pytest.fixture(autouse=True)
def _clean_store(monkeypatch, tmp_path):
    """Isolate EPACK persistence per test."""
    clear_epack_events_for_test()
    monkeypatch.setenv("TECL_EPACK_DIR", str(tmp_path))
    yield
    clear_epack_events_for_test()


def test_emit_stage_event_is_readable_by_reader(tmp_path):
    clear_epack_events_for_test()
    os.environ["TECL_EPACK_DIR"] = str(tmp_path)
    epack_id = "epack-test"
    run_id = "run-test"

    h = emit_stage_event(
        epack=epack_id,
        run_id=run_id,
        stage="tecl.verification.success",
        payload={"user_id": "a@example.com", "role": "physician", "role_level": 3},
    )
    assert isinstance(h, str) and len(h) == 64

    events = get_recent_events(epack_id=epack_id, stage_prefix="tecl.verification.", limit=20)
    assert len(events) >= 1
    # Find our specific event by hash (isolation-safe)
    matching = [e for e in events if e.get("event_hash") == h]
    assert len(matching) >= 1, f"Expected event with hash {h[:12]}... not found"
    evt = matching[0]
    assert evt["stage"].startswith("tecl.verification.")
    assert evt["event_hash"] == h
    assert evt["payload"]["role_level"] == 3

    # Ensure it also wrote to disk (JSONL)
    p = tmp_path / f"{epack_id}.jsonl"
    assert p.exists()
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event_hash"] == h


def test_reader_filters_by_prefix(tmp_path):
    clear_epack_events_for_test()
    os.environ["TECL_EPACK_DIR"] = str(tmp_path)
    epack_id = "epack-test2"
    emit_stage_event(epack=epack_id, run_id="r", stage="tecl.verification.user_not_found", payload={"user_id": "x"})
    emit_stage_event(epack=epack_id, run_id="r", stage="tecl.scope_gate.pass", payload={"role_level": 1})

    only_ver = get_recent_events(epack_id=epack_id, stage_prefix="tecl.verification.", limit=10)
    assert len(only_ver) == 1
    assert only_ver[0]["stage"] == "tecl.verification.user_not_found"
