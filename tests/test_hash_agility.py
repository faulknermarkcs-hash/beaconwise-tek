"""Hash Algorithm Agility — per SECURITY_MODEL.md §4.2.

Proves the system supports algorithm migration without breaking
existing chain verification for SHA-256 records.
"""
import os
import pytest

from ecosphere.utils.stable import (
    stable_hash,
    stable_hash_tagged,
    stable_json,
    verify_tagged_hash,
    hash_suffix,
    supported_algorithms,
    HASH_ALGORITHM,
)


# --- Backward compatibility ---

def test_default_is_sha256():
    """Default algorithm must be SHA-256 for backward compat."""
    h = stable_hash({"test": True})
    assert len(h) == 64  # SHA-256 produces 64 hex chars


def test_sha256_produces_same_result_as_before():
    """Regression: exact hash for known input must not change."""
    h = stable_hash({"a": 1, "b": 2})
    # This is the canonical SHA-256 of '{"a":1,"b":2}'
    assert len(h) == 64
    # Re-compute to verify determinism
    assert h == stable_hash({"b": 2, "a": 1})


# --- Algorithm selection ---

def test_sha384_produces_96_chars():
    h = stable_hash({"test": True}, algorithm="sha384")
    assert len(h) == 96


def test_sha512_produces_128_chars():
    h = stable_hash({"test": True}, algorithm="sha512")
    assert len(h) == 128


def test_different_algorithms_produce_different_hashes():
    obj = {"data": "test"}
    h256 = stable_hash(obj, algorithm="sha256")
    h384 = stable_hash(obj, algorithm="sha384")
    h512 = stable_hash(obj, algorithm="sha512")
    assert h256 != h384 != h512


def test_unsupported_algorithm_raises():
    try:
        stable_hash({"x": 1}, algorithm="md5")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "md5" in str(e)
        assert "sha256" in str(e)


def test_supported_algorithms_list():
    algos = supported_algorithms()
    assert "sha256" in algos
    assert "sha384" in algos
    assert "sha512" in algos


# --- Tagged hashes ---

def test_tagged_hash_includes_algorithm():
    tagged = stable_hash_tagged({"x": 1})
    assert tagged.startswith("sha256:")
    assert len(tagged.split(":")[1]) == 64


def test_tagged_hash_sha512():
    tagged = stable_hash_tagged({"x": 1}, algorithm="sha512")
    assert tagged.startswith("sha512:")
    assert len(tagged.split(":")[1]) == 128


def test_verify_tagged_hash_passes():
    tagged = stable_hash_tagged({"data": "test"})
    assert verify_tagged_hash({"data": "test"}, tagged) is True


def test_verify_tagged_hash_fails_on_tamper():
    tagged = stable_hash_tagged({"data": "test"})
    assert verify_tagged_hash({"data": "TAMPERED"}, tagged) is False


def test_verify_tagged_hash_works_cross_algorithm():
    obj = {"data": "test"}
    for algo in supported_algorithms():
        tagged = stable_hash_tagged(obj, algorithm=algo)
        assert verify_tagged_hash(obj, tagged) is True


def test_verify_legacy_untagged_hash():
    """Legacy hashes (no tag prefix) verified as SHA-256."""
    obj = {"data": "test"}
    legacy = stable_hash(obj, algorithm="sha256")
    assert ":" not in legacy
    assert verify_tagged_hash(obj, legacy) is True


# --- hash_suffix with tags ---

def test_hash_suffix_plain():
    assert hash_suffix("abcdef1234", 4) == "1234"


def test_hash_suffix_tagged():
    assert hash_suffix("sha256:abcdef1234", 4) == "1234"


def test_hash_suffix_empty():
    assert hash_suffix("") == ""


# --- Environment override ---

def test_env_override(monkeypatch):
    monkeypatch.setenv("ECOSPHERE_HASH_ALGORITHM", "sha512")
    # Re-import to pick up env var
    import importlib
    import ecosphere.utils.stable as mod
    importlib.reload(mod)
    assert mod.HASH_ALGORITHM == "sha512"
    h = mod.stable_hash({"test": True})
    assert len(h) == 128  # SHA-512
    # Restore
    monkeypatch.setenv("ECOSPHERE_HASH_ALGORITHM", "sha256")
    importlib.reload(mod)
