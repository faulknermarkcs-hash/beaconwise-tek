"""EPACK Chain Integrity — cryptographic tamper detection.

Proves the claims BeaconWise makes about immutable audit trails:
  - Every EPACK is sealed with sha256(seq + ts + prev_hash + payload)
  - Chains are linked via prev_hash → parent.hash
  - Any modification to any field in any record is detectable
  - Insertion, deletion, and reordering of records breaks the chain
  - The genesis record anchors the entire chain
"""
import copy
import pytest

from ecosphere.epack.chain import new_epack, EPACK
from ecosphere.utils.stable import stable_hash, stable_json


# --------------- helpers ---------------

def _chain(n=5):
    """Build a valid n-record chain."""
    records = []
    prev = "GENESIS"
    for i in range(n):
        ep = new_epack(seq=i + 1, prev_hash=prev, payload={"turn": i + 1, "text": f"message_{i + 1}"})
        records.append(ep)
        prev = ep.hash
    return records


def _verify_chain(records):
    """Independent chain verification (no replay engine dependency)."""
    errors = []
    for i, ep in enumerate(records):
        # Recompute hash
        expected = stable_hash({"seq": ep.seq, "ts": ep.ts, "prev_hash": ep.prev_hash, "payload": ep.payload})
        if ep.hash != expected:
            errors.append(f"record {i}: hash mismatch")
        # Check linkage
        if i == 0:
            if ep.prev_hash != "GENESIS":
                errors.append(f"record 0: expected GENESIS, got {ep.prev_hash}")
        else:
            if ep.prev_hash != records[i - 1].hash:
                errors.append(f"record {i}: prev_hash doesn't link to record {i-1}")
    return errors


# --------------- Genesis ---------------

def test_genesis_anchor():
    chain = _chain(1)
    assert chain[0].prev_hash == "GENESIS"
    assert chain[0].seq == 1


def test_genesis_hash_is_deterministic():
    """Same inputs must produce same hash."""
    a = stable_hash({"seq": 1, "ts": 100.0, "prev_hash": "GENESIS", "payload": {"x": 1}})
    b = stable_hash({"seq": 1, "ts": 100.0, "prev_hash": "GENESIS", "payload": {"x": 1}})
    assert a == b


def test_genesis_hash_changes_with_any_field():
    base = {"seq": 1, "ts": 100.0, "prev_hash": "GENESIS", "payload": {"x": 1}}
    h_base = stable_hash(base)
    # Change each field independently
    for key, alt in [("seq", 2), ("ts", 200.0), ("prev_hash", "OTHER"), ("payload", {"x": 2})]:
        modified = dict(base)
        modified[key] = alt
        assert stable_hash(modified) != h_base, f"Changing {key} should change hash"


# --------------- Chain linkage ---------------

def test_clean_chain_validates():
    chain = _chain(10)
    errors = _verify_chain(chain)
    assert errors == []


def test_every_record_links_to_predecessor():
    chain = _chain(5)
    for i in range(1, len(chain)):
        assert chain[i].prev_hash == chain[i - 1].hash


def test_chain_hashes_are_all_unique():
    chain = _chain(20)
    hashes = [ep.hash for ep in chain]
    assert len(set(hashes)) == 20


# --------------- Tamper detection: payload ---------------

def test_tamper_payload_text():
    chain = _chain(5)
    # Tamper record 3's payload
    tampered = EPACK(
        seq=chain[2].seq, ts=chain[2].ts, prev_hash=chain[2].prev_hash,
        payload={"turn": 3, "text": "TAMPERED_MESSAGE"},
        hash=chain[2].hash,  # keep original hash — should fail verification
    )
    chain_list = list(chain)
    chain_list[2] = tampered
    errors = _verify_chain(chain_list)
    assert any("hash mismatch" in e for e in errors)


def test_tamper_payload_add_key():
    chain = _chain(3)
    tampered = EPACK(
        seq=chain[1].seq, ts=chain[1].ts, prev_hash=chain[1].prev_hash,
        payload={**chain[1].payload, "injected_key": "malicious"},
        hash=chain[1].hash,
    )
    chain_list = list(chain)
    chain_list[1] = tampered
    errors = _verify_chain(chain_list)
    assert any("hash mismatch" in e for e in errors)


def test_tamper_payload_remove_key():
    chain = _chain(3)
    trimmed_payload = {"turn": chain[1].payload["turn"]}  # drop "text"
    tampered = EPACK(
        seq=chain[1].seq, ts=chain[1].ts, prev_hash=chain[1].prev_hash,
        payload=trimmed_payload, hash=chain[1].hash,
    )
    chain_list = list(chain)
    chain_list[1] = tampered
    errors = _verify_chain(chain_list)
    assert any("hash mismatch" in e for e in errors)


# --------------- Tamper detection: metadata ---------------

def test_tamper_seq():
    chain = _chain(3)
    tampered = EPACK(seq=999, ts=chain[1].ts, prev_hash=chain[1].prev_hash,
                     payload=chain[1].payload, hash=chain[1].hash)
    chain_list = list(chain)
    chain_list[1] = tampered
    errors = _verify_chain(chain_list)
    assert any("hash mismatch" in e for e in errors)


def test_tamper_timestamp():
    chain = _chain(3)
    tampered = EPACK(seq=chain[1].seq, ts=0.0, prev_hash=chain[1].prev_hash,
                     payload=chain[1].payload, hash=chain[1].hash)
    chain_list = list(chain)
    chain_list[1] = tampered
    errors = _verify_chain(chain_list)
    assert any("hash mismatch" in e for e in errors)


def test_tamper_prev_hash():
    chain = _chain(3)
    tampered = EPACK(seq=chain[1].seq, ts=chain[1].ts, prev_hash="FORGED",
                     payload=chain[1].payload, hash=chain[1].hash)
    chain_list = list(chain)
    chain_list[1] = tampered
    errors = _verify_chain(chain_list)
    assert any("hash mismatch" in e or "prev_hash" in e for e in errors)


# --------------- Tamper detection: structural ---------------

def test_delete_record_breaks_chain():
    chain = _chain(5)
    chain_list = list(chain)
    del chain_list[2]  # remove record 3
    errors = _verify_chain(chain_list)
    assert any("prev_hash" in e for e in errors)


def test_insert_record_breaks_chain():
    chain = _chain(5)
    foreign = new_epack(seq=99, prev_hash="FORGED", payload={"injected": True})
    chain_list = list(chain)
    chain_list.insert(2, foreign)
    errors = _verify_chain(chain_list)
    assert len(errors) >= 1


def test_reorder_records_breaks_chain():
    chain = _chain(5)
    chain_list = list(chain)
    chain_list[1], chain_list[3] = chain_list[3], chain_list[1]
    errors = _verify_chain(chain_list)
    assert len(errors) >= 2


def test_duplicate_record_breaks_chain():
    chain = _chain(5)
    chain_list = list(chain)
    chain_list.insert(3, chain_list[2])  # duplicate record 3
    errors = _verify_chain(chain_list)
    assert len(errors) >= 1


def test_replace_genesis_breaks_everything():
    chain = _chain(5)
    fake_genesis = new_epack(seq=1, prev_hash="GENESIS", payload={"turn": 1, "text": "REPLACED"})
    chain_list = list(chain)
    chain_list[0] = fake_genesis
    errors = _verify_chain(chain_list)
    # Record 1's hash changed so record 2's linkage breaks
    assert any("prev_hash" in e for e in errors)


# --------------- Sophisticated attacks ---------------

def test_rehash_attack_detected_by_linkage():
    """Attacker modifies payload AND recomputes hash — but can't fix the next record's prev_hash."""
    chain = _chain(5)
    # Tamper record 3's payload and recompute its hash
    new_payload = {"turn": 3, "text": "SECRETLY_MODIFIED"}
    new_hash = stable_hash({
        "seq": chain[2].seq, "ts": chain[2].ts,
        "prev_hash": chain[2].prev_hash, "payload": new_payload,
    })
    tampered = EPACK(seq=chain[2].seq, ts=chain[2].ts, prev_hash=chain[2].prev_hash,
                     payload=new_payload, hash=new_hash)
    chain_list = list(chain)
    chain_list[2] = tampered
    errors = _verify_chain(chain_list)
    # Record 3's own hash is now valid, but record 4's prev_hash still points to old hash
    assert any("prev_hash" in e for e in errors)


def test_full_chain_rewrite_detectable_if_genesis_anchor_preserved():
    """If we have a trusted copy of the genesis hash, a full chain rewrite is detectable."""
    original = _chain(5)
    trusted_genesis_hash = original[0].hash

    # Attacker builds a completely new chain
    forged = _chain(5)  # different timestamps → different hashes
    errors = _verify_chain(forged)
    assert errors == [], "Forged chain is internally consistent"
    # But the genesis hash differs from the trusted anchor
    assert forged[0].hash != trusted_genesis_hash


# --------------- Stable hash properties ---------------

def test_stable_hash_is_sha256():
    h = stable_hash({"test": True})
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_stable_json_is_canonical():
    """Key order and whitespace must not affect hash."""
    a = stable_json({"b": 2, "a": 1})
    b = stable_json({"a": 1, "b": 2})
    assert a == b


def test_stable_hash_handles_nested_objects():
    obj = {"a": {"b": {"c": [1, 2, {"d": 3}]}}}
    h1 = stable_hash(obj)
    h2 = stable_hash(obj)
    assert h1 == h2
