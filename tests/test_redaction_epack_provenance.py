"""Tests for security.redaction, epack.chain, and kernel.provenance.

Covers: recursive redaction of nested structures, EPACK hash chaining,
provenance manifest seal hash stability.
"""
import os
import json
import time

import pytest

from ecosphere.security.redaction import redact_payload, redact_value, _redact_recursive
from ecosphere.epack.chain import new_epack, EPACK
from ecosphere.kernel.provenance import current_manifest, BuildManifest
from ecosphere.storage.store import append_jsonl, read_jsonl
from ecosphere.utils.stable import stable_hash


# ── redact_value ──────────────────────────────────────────────────

def test_redact_value_string():
    r = redact_value("secret")
    assert r["_redacted"] is True
    assert "sha256" in r
    assert r["sha256"] == stable_hash("secret")


def test_redact_value_non_string():
    assert redact_value(42) == 42
    assert redact_value(True) is True


# ── redact_payload — top level ────────────────────────────────────

def test_redact_payload_top_level(monkeypatch):
    monkeypatch.setenv("ECOSPHERE_REDACT_MODE", "hash")
    payload = {"name": "Alice", "count": 5}
    r = redact_payload(payload)
    assert r["name"]["_redacted"] is True
    assert r["count"] == 5


def test_redact_payload_off(monkeypatch):
    monkeypatch.setenv("ECOSPHERE_REDACT_MODE", "off")
    # Need to reload Settings to pick up env change
    from ecosphere.config import Settings
    old = Settings.REDACT_MODE
    Settings.REDACT_MODE = "off"
    payload = {"name": "Alice"}
    r = redact_payload(payload)
    assert r["name"] == "Alice"
    Settings.REDACT_MODE = old


# ── redact_payload — nested (NEW in v6) ──────────────────────────

def test_redact_payload_nested_dict():
    payload = {"outer": {"inner": "secret", "num": 7}}
    r = _redact_recursive(payload)
    assert r["outer"]["inner"]["_redacted"] is True
    assert r["outer"]["num"] == 7


def test_redact_payload_nested_list():
    payload = {"items": ["alpha", "beta"], "count": 2}
    r = _redact_recursive(payload)
    assert r["items"][0]["_redacted"] is True
    assert r["items"][1]["_redacted"] is True
    assert r["count"] == 2


def test_redact_payload_deeply_nested():
    payload = {"a": {"b": {"c": {"d": "deep"}}}}
    r = _redact_recursive(payload)
    assert r["a"]["b"]["c"]["d"]["_redacted"] is True


def test_redact_payload_mixed_list():
    payload = {"mix": ["text", 42, True, {"key": "val"}]}
    r = _redact_recursive(payload)
    assert r["mix"][0]["_redacted"] is True
    assert r["mix"][1] == 42
    assert r["mix"][2] is True
    assert r["mix"][3]["key"]["_redacted"] is True


# ── EPACK chain ───────────────────────────────────────────────────

def test_new_epack_fields():
    ep = new_epack(seq=1, prev_hash="GENESIS", payload={"x": 1})
    assert ep.seq == 1
    assert ep.prev_hash == "GENESIS"
    assert ep.payload == {"x": 1}
    assert isinstance(ep.hash, str) and len(ep.hash) == 64
    assert ep.ts > 0


def test_epack_chain_integrity():
    ep1 = new_epack(seq=1, prev_hash="GENESIS", payload={"x": 1})
    ep2 = new_epack(seq=2, prev_hash=ep1.hash, payload={"x": 2})
    ep3 = new_epack(seq=3, prev_hash=ep2.hash, payload={"x": 3})

    assert ep2.prev_hash == ep1.hash
    assert ep3.prev_hash == ep2.hash
    # All hashes are unique
    assert len({ep1.hash, ep2.hash, ep3.hash}) == 3


def test_epack_hash_deterministic_for_same_ts():
    """Same inputs (including ts) → same hash."""
    payload = {"x": 1}
    h1 = stable_hash({"seq": 1, "ts": 1000.0, "prev_hash": "GENESIS", "payload": payload})
    h2 = stable_hash({"seq": 1, "ts": 1000.0, "prev_hash": "GENESIS", "payload": payload})
    assert h1 == h2


def test_epack_hash_changes_with_payload():
    """Different payloads → different hashes."""
    h1 = stable_hash({"seq": 1, "ts": 1000.0, "prev_hash": "GENESIS", "payload": {"x": 1}})
    h2 = stable_hash({"seq": 1, "ts": 1000.0, "prev_hash": "GENESIS", "payload": {"x": 2}})
    assert h1 != h2


# ── Provenance manifest ──────────────────────────────────────────

def test_manifest_has_required_fields():
    m = current_manifest()
    assert "kernel_version" in m
    assert "python" in m
    assert "manifest_hash" in m
    assert m["pr5_10_tool_sandbox"] is True
    assert m["pr6_schema_retry_loop"] is True


def test_manifest_hash_is_stable():
    m1 = current_manifest()
    m2 = current_manifest()
    assert m1["manifest_hash"] == m2["manifest_hash"]


# ── Storage: append_jsonl / read_jsonl ────────────────────────────

def test_jsonl_round_trip(tmp_path):
    path = str(tmp_path / "test.jsonl")
    append_jsonl(path, {"a": 1})
    append_jsonl(path, {"b": 2})

    records = read_jsonl(path)
    assert len(records) == 2
    assert records[0]["a"] == 1
    assert records[1]["b"] == 2


def test_jsonl_read_nonexistent():
    records = read_jsonl("/nonexistent/path.jsonl")
    assert records == []


def test_jsonl_limit(tmp_path):
    path = str(tmp_path / "limit.jsonl")
    for i in range(10):
        append_jsonl(path, {"i": i})

    records = read_jsonl(path, limit=3)
    assert len(records) == 3
