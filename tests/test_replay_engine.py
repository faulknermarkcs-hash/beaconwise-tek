"""Replay Engine — deterministic governance reproducibility verification.

Covers the 6-step verification pipeline (V8 restored + V9 chain linkage):
  1. EPACK hash integrity (tamper detection)
  2. Routing determinism
  3. Safety screening consistency
  4. Profile consistency
  5. Build manifest integrity
  6. Chain linkage (prev_hash continuity)
"""
import copy
import time
import pytest

from ecosphere.epack.chain import new_epack
from ecosphere.utils.stable import stable_hash
from ecosphere.replay.engine import (
    replay_governance_decision,
    replay_chain,
    replay_summary,
    ReplayResult,
    ReplayStep,
)


# --------------- helpers ---------------

def _build_chain(n=3):
    """Build a clean n-record EPACK chain with prev_hash linkage."""
    chain = []
    prev = "GENESIS"
    for i in range(n):
        ep = new_epack(seq=i + 1, prev_hash=prev, payload={
            "user_text_hash": stable_hash(f"turn_{i}"),
            "profile": "default",
            "extra": {
                "route": "TDM",
                "safety_stage1_ok": True,
                "input_vector": {"complexity": 3},
            },
            "build_manifest": {"manifest_hash": stable_hash({"v": "1.9.0"})},
        })
        chain.append({
            "seq": ep.seq, "ts": ep.ts, "prev_hash": ep.prev_hash,
            "payload": ep.payload, "hash": ep.hash,
        })
        prev = ep.hash
    return chain


def _always_tdm(iv):
    return "TDM"

def _always_safe(text_hash):
    return True

def _always_unsafe(text_hash):
    return False


# --------------- Step 1: Hash integrity ---------------

def test_hash_integrity_clean_record():
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0])
    step = [s for s in result.steps if s.step_name == "epack_hash_integrity"][0]
    assert step.match is True
    assert result.governance_match is True


def test_hash_integrity_detects_tampered_payload():
    chain = _build_chain(1)
    chain[0]["payload"]["profile"] = "INJECTED"
    result = replay_governance_decision(epack_record=chain[0])
    step = [s for s in result.steps if s.step_name == "epack_hash_integrity"][0]
    assert step.match is False
    assert "TAMPERED" in step.detail
    assert result.governance_match is False


def test_hash_integrity_detects_tampered_hash():
    chain = _build_chain(1)
    chain[0]["hash"] = "0" * 64
    result = replay_governance_decision(epack_record=chain[0])
    step = [s for s in result.steps if s.step_name == "epack_hash_integrity"][0]
    assert step.match is False


def test_hash_integrity_detects_tampered_seq():
    chain = _build_chain(1)
    chain[0]["seq"] = 999
    result = replay_governance_decision(epack_record=chain[0])
    step = [s for s in result.steps if s.step_name == "epack_hash_integrity"][0]
    assert step.match is False


def test_hash_integrity_detects_tampered_timestamp():
    chain = _build_chain(1)
    chain[0]["ts"] = 0.0
    result = replay_governance_decision(epack_record=chain[0])
    step = [s for s in result.steps if s.step_name == "epack_hash_integrity"][0]
    assert step.match is False


# --------------- Step 2: Routing determinism ---------------

def test_routing_match_when_consistent():
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0], route_fn=_always_tdm)
    step = [s for s in result.steps if s.step_name == "routing_determinism"][0]
    assert step.match is True
    assert result.route_match is True


def test_routing_mismatch_when_divergent():
    chain = _build_chain(1)
    result = replay_governance_decision(
        epack_record=chain[0],
        route_fn=lambda iv: "BOUND",  # different route
    )
    step = [s for s in result.steps if s.step_name == "routing_determinism"][0]
    assert step.match is False
    assert result.route_match is False


def test_routing_skipped_when_no_fn():
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0], route_fn=None)
    step = [s for s in result.steps if s.step_name == "routing_determinism"][0]
    assert step.match is True  # skipped counts as pass
    assert "skipped" in step.detail.lower()


def test_routing_error_handled_gracefully():
    def _explode(iv):
        raise RuntimeError("adapter down")
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0], route_fn=_explode)
    step = [s for s in result.steps if s.step_name == "routing_determinism"][0]
    assert step.match is False
    assert "ERROR" in step.replayed_value


# --------------- Step 3: Safety screening ---------------

def test_safety_match_when_consistent():
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0], safety_fn=_always_safe)
    step = [s for s in result.steps if s.step_name == "safety_screening"][0]
    assert step.match is True
    assert result.safety_match is True


def test_safety_mismatch_when_divergent():
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0], safety_fn=_always_unsafe)
    step = [s for s in result.steps if s.step_name == "safety_screening"][0]
    assert step.match is False
    assert result.safety_match is False


# --------------- Step 4: Profile consistency ---------------

def test_profile_always_present():
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0])
    step = [s for s in result.steps if s.step_name == "profile_consistency"][0]
    assert step.match is True


# --------------- Step 5: Build manifest ---------------

def test_manifest_present_passes():
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0])
    step = [s for s in result.steps if s.step_name == "build_manifest"][0]
    assert step.match is True


def test_manifest_missing_fails():
    chain = _build_chain(1)
    chain[0]["payload"]["build_manifest"] = {}
    # Recompute hash so step 1 passes (isolate manifest test)
    chain[0]["hash"] = stable_hash({
        "seq": chain[0]["seq"], "ts": chain[0]["ts"],
        "prev_hash": chain[0]["prev_hash"], "payload": chain[0]["payload"],
    })
    result = replay_governance_decision(epack_record=chain[0])
    step = [s for s in result.steps if s.step_name == "build_manifest"][0]
    assert step.match is False
    assert result.governance_match is False


# --------------- Step 6: Chain linkage (V9) ---------------

def test_chain_linkage_correct():
    chain = _build_chain(3)
    result = replay_governance_decision(
        epack_record=chain[1],
        expected_prev_hash=chain[0]["hash"],
    )
    step = [s for s in result.steps if s.step_name == "chain_linkage"][0]
    assert step.match is True
    assert result.chain_link_match is True


def test_chain_linkage_broken_detects_gap():
    chain = _build_chain(3)
    result = replay_governance_decision(
        epack_record=chain[2],
        expected_prev_hash="wrong_hash_value",
    )
    step = [s for s in result.steps if s.step_name == "chain_linkage"][0]
    assert step.match is False
    assert "BROKEN" in step.detail
    assert result.chain_link_match is False


def test_chain_linkage_not_checked_when_no_expected():
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0])
    linkage_steps = [s for s in result.steps if s.step_name == "chain_linkage"]
    assert len(linkage_steps) == 0  # not checked when expected_prev_hash is None


# --------------- Full chain replay ---------------

def test_replay_chain_all_match():
    chain = _build_chain(5)
    results = replay_chain(chain, route_fn=_always_tdm, safety_fn=_always_safe)
    assert len(results) == 5
    assert all(r.governance_match for r in results)
    assert all(r.chain_link_match for r in results)


def test_replay_chain_detects_tampered_middle():
    chain = _build_chain(5)
    chain[2]["payload"]["profile"] = "EVIL"  # tamper record 3
    results = replay_chain(chain, route_fn=_always_tdm, safety_fn=_always_safe)
    assert results[0].governance_match is True
    assert results[1].governance_match is True
    assert results[2].governance_match is False  # tampered
    # Record 3 also breaks chain for record 4 (prev_hash won't match)
    # because replay_chain uses record.hash (the original, now wrong relative to payload)
    # Actually: replay_chain passes prev_hash = chain[2]["hash"] which is the ORIGINAL hash
    # but chain[2] was tampered so its step 1 fails. Chain linkage for [3] checks
    # chain[3].prev_hash == chain[2].hash which is still the original — so linkage holds.
    # The tamper is caught at step 1 of record [2].


def test_replay_chain_detects_deleted_record():
    chain = _build_chain(5)
    del chain[2]  # delete record 3 — breaks linkage for record 4
    results = replay_chain(chain)
    # Record at position 2 (originally record 4) should fail chain linkage
    # because its prev_hash points to record 3 which is gone
    assert results[2].chain_link_match is False


def test_replay_chain_detects_reordered_records():
    chain = _build_chain(5)
    chain[1], chain[2] = chain[2], chain[1]  # swap records 2 and 3
    results = replay_chain(chain)
    # At least one chain linkage should break
    broken = [r for r in results if not r.chain_link_match]
    assert len(broken) >= 1


def test_replay_chain_detects_inserted_record():
    chain = _build_chain(3)
    # Insert a foreign record between 1 and 2
    foreign = new_epack(seq=99, prev_hash="fake", payload={"injected": True})
    foreign_dict = {
        "seq": foreign.seq, "ts": foreign.ts, "prev_hash": foreign.prev_hash,
        "payload": foreign.payload, "hash": foreign.hash,
    }
    chain.insert(1, foreign_dict)
    results = replay_chain(chain)
    # The foreign record's chain linkage should fail (prev_hash doesn't match record 1)
    assert results[1].chain_link_match is False


# --------------- Summary ---------------

def test_summary_perfect_chain():
    chain = _build_chain(4)
    results = replay_chain(chain, route_fn=_always_tdm, safety_fn=_always_safe)
    summary = replay_summary(results)
    assert summary["total"] == 4
    assert summary["governance_match_rate"] == 1.0
    assert summary["chain_link_rate"] == 1.0
    assert summary["tampered_records"] == []
    assert summary["determinism_index"] == 100.0


def test_summary_with_tampered():
    chain = _build_chain(4)
    chain[1]["payload"]["profile"] = "EVIL"
    results = replay_chain(chain)
    summary = replay_summary(results)
    assert summary["governance_match_rate"] < 1.0
    assert 2 in summary["tampered_records"]  # seq=2 is tampered


def test_summary_empty():
    summary = replay_summary([])
    assert summary["total"] == 0


# --------------- Determinism index ---------------

def test_determinism_index_perfect():
    chain = _build_chain(1)
    result = replay_governance_decision(
        epack_record=chain[0],
        route_fn=_always_tdm,
        safety_fn=_always_safe,
    )
    assert result.determinism_index == 100.0


def test_determinism_index_degraded():
    chain = _build_chain(1)
    chain[0]["payload"]["profile"] = "TAMPERED"
    result = replay_governance_decision(
        epack_record=chain[0],
        route_fn=_always_tdm,
        safety_fn=_always_safe,
    )
    assert result.determinism_index < 100.0


# --------------- Result serialization ---------------

def test_replay_result_to_dict():
    chain = _build_chain(1)
    result = replay_governance_decision(epack_record=chain[0])
    d = result.to_dict()
    assert "replay_id" in d
    assert "steps" in d
    assert isinstance(d["steps"], list)
    assert all("step_name" in s for s in d["steps"])


# --------------- Idempotency ---------------

def test_replay_is_idempotent():
    """Same record replayed twice must produce identical results."""
    chain = _build_chain(1)
    r1 = replay_governance_decision(epack_record=chain[0], route_fn=_always_tdm, safety_fn=_always_safe)
    r2 = replay_governance_decision(epack_record=chain[0], route_fn=_always_tdm, safety_fn=_always_safe)
    assert r1.governance_match == r2.governance_match
    assert r1.determinism_index == r2.determinism_index
    assert len(r1.steps) == len(r2.steps)
    for s1, s2 in zip(r1.steps, r2.steps):
        assert s1.match == s2.match
        assert s1.step_name == s2.step_name
