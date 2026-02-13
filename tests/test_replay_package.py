"""Replay Package — formal artifact bundling per DRP §5.

Tests that the code counterpart to REPLAY_PROTOCOL.md exists,
seals correctly, and validates chain integrity.
"""
from ecosphere.epack.chain import new_epack
from ecosphere.utils.stable import stable_hash
from ecosphere.replay.package import (
    ReplayPackage,
    build_replay_package,
    verify_replay_package,
)


def _chain(n=3):
    records = []
    prev = "GENESIS"
    for i in range(n):
        ep = new_epack(seq=i + 1, prev_hash=prev, payload={
            "user_text_hash": stable_hash(f"turn_{i}"),
            "profile": "default",
            "build_manifest": {"manifest_hash": stable_hash({"v": "1.9.0"})},
        })
        records.append({
            "seq": ep.seq, "ts": ep.ts, "prev_hash": ep.prev_hash,
            "payload": ep.payload, "hash": ep.hash,
        })
        prev = ep.hash
    return records


# --- Build ---

def test_build_creates_sealed_package():
    chain = _chain(3)
    rp = build_replay_package(
        session_epacks=chain,
        kernel_version="v1.9.0",
        governance_profile="default",
    )
    assert rp.package_hash != ""
    assert rp.kernel_version == "v1.9.0"
    assert rp.epack_head_hash == chain[-1]["hash"]
    assert len(rp.epack_chain) == 3


def test_build_captures_input_hash():
    chain = _chain(1)
    rp = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    assert rp.input_payload_hash == chain[0]["payload"]["user_text_hash"]


def test_build_empty_chain():
    rp = build_replay_package(session_epacks=[], kernel_version="v1.9.0")
    assert rp.epack_head_hash == ""
    assert rp.input_payload_hash == ""


# --- Seal ---

def test_seal_is_deterministic():
    chain = _chain(3)
    rp1 = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    rp2 = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    assert rp1.package_hash == rp2.package_hash


def test_seal_changes_with_content():
    chain = _chain(3)
    rp1 = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    rp2 = build_replay_package(session_epacks=chain, kernel_version="v2.0.0")
    assert rp1.package_hash != rp2.package_hash


def test_verify_seal_passes_clean():
    chain = _chain(3)
    rp = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    assert rp.verify_seal() is True


def test_verify_seal_fails_after_tamper():
    chain = _chain(3)
    rp = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    rp.kernel_version = "TAMPERED"
    assert rp.verify_seal() is False


# --- Verify ---

def test_verify_clean_package():
    chain = _chain(5)
    rp = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    result = verify_replay_package(rp)
    assert result["passed"] is True
    assert all(c["passed"] for c in result["checks"])


def test_verify_detects_broken_seal():
    chain = _chain(3)
    rp = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    rp.kernel_version = "TAMPERED"
    result = verify_replay_package(rp)
    seal_check = [c for c in result["checks"] if c["check"] == "package_seal"][0]
    assert seal_check["passed"] is False


def test_verify_detects_broken_chain():
    chain = _chain(5)
    chain[2]["payload"]["profile"] = "EVIL"
    rp = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    result = verify_replay_package(rp)
    chain_check = [c for c in result["checks"] if c["check"] == "chain_integrity"][0]
    assert chain_check["passed"] is False
    assert len(chain_check["errors"]) >= 1


def test_verify_detects_wrong_head_hash():
    chain = _chain(3)
    rp = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    rp.epack_head_hash = "wrong"
    rp.seal()  # reseal so package_seal passes
    result = verify_replay_package(rp)
    head_check = [c for c in result["checks"] if c["check"] == "head_hash"][0]
    assert head_check["passed"] is False


def test_verify_detects_missing_required_fields():
    chain = _chain(3)
    rp = build_replay_package(session_epacks=chain, kernel_version="")
    result = verify_replay_package(rp)
    req_check = [c for c in result["checks"] if c["check"] == "required_fields"][0]
    assert req_check["passed"] is False


# --- Serialization ---

def test_to_dict_roundtrip():
    chain = _chain(3)
    rp = build_replay_package(session_epacks=chain, kernel_version="v1.9.0")
    d = rp.to_dict()
    assert d["kernel_version"] == "v1.9.0"
    assert d["package_hash"] == rp.package_hash
    assert len(d["epack_chain"]) == 3
