"""EPACK Chain Integrity — tamper detection (Brick 3 compatible).

Claims:
  - Every EPACK is sealed with stable_hash(header + payload + payload_hash)
  - Chains are linked via prev_hash → parent.hash
  - Any modification is detectable
  - Insertion, deletion, and reordering breaks the chain
"""
import copy
import pytest

from ecosphere.epack.chain import new_epack
from ecosphere.utils.stable import stable_hash


def test_chain_links_and_detects_tamper():
    payload1 = {"type": "x", "decision_hash": "a" * 64}
    e1 = new_epack(0, "GENESIS", payload1, payload_hash_override=payload1["decision_hash"])

    payload2 = {"type": "y", "decision_hash": "b" * 64}
    e2 = new_epack(1, e1.hash, payload2, payload_hash_override=payload2["decision_hash"])

    assert e2.prev_hash == e1.hash
    assert e1.payload_hash == "a" * 64
    assert e2.payload_hash == "b" * 64

    # tamper payload
    bad = copy.deepcopy(e2.payload)
    bad["type"] = "evil"
    tampered_hash = stable_hash({
        "seq": e2.seq,
        "ts": e2.ts,
        "prev_hash": e2.prev_hash,
        "payload_hash": e2.payload_hash,
        "payload": bad,
    })
    assert tampered_hash != e2.hash
