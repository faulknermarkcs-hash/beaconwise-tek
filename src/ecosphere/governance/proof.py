# src/ecosphere/governance/proof.py
"""BeaconWise Governance Proof Protocol (V7 Capability 1).

Provides cryptographically verifiable governance proofs:
  - deterministic routing proofs
  - signed EPACK forensic audit chains
  - reproducible state replay
  - tamper-evident governance receipts
  - third-party verification API
  - lightweight default proof mode
  - deep forensic audit mode

Principle: Governance must be provable, not asserted.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ecosphere.utils.stable import stable_hash, stable_json


# ── Proof Modes ───────────────────────────────────────────────────

class ProofMode(str, Enum):
    """Governance proof depth."""
    LIGHTWEIGHT = "lightweight"   # Hash chain + routing proof only
    STANDARD = "standard"         # + signed receipts + TSV snapshot
    FORENSIC = "forensic"         # + full state replay + input vectors


# ── Governance Proof Schema ───────────────────────────────────────

@dataclass(frozen=True)
class RoutingProof:
    """Deterministic proof that a specific route was taken."""
    input_hash: str              # SHA-256 of user input
    route_sequence: List[str]    # e.g. ["REFLECT", "TDM"]
    route_reason: str            # why this route was chosen
    safety_stage1_ok: bool
    safety_stage2_ok: bool
    safety_stage2_score: float
    domain: str
    complexity: int
    profile: str
    timestamp: float

    def seal(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class GovernanceReceipt:
    """Tamper-evident receipt for a single governed interaction."""
    receipt_id: str
    epack_hash: str              # hash of the sealed EPACK
    routing_proof_hash: str      # hash of RoutingProof
    manifest_hash: str           # build manifest hash
    tsv_snapshot_hash: str       # hash of belief state at decision time
    scope_gate_decision: str     # PASS / REWRITE / REFUSE / N/A
    profile: str
    mode: str                    # ProofMode value
    timestamp: float
    signature: str               # HMAC signature over all fields

    def verify(self, key: bytes) -> bool:
        """Verify receipt signature."""
        expected = _sign_receipt_fields(self, key)
        return hmac.compare_digest(self.signature, expected)


@dataclass
class GovernanceProof:
    """Complete governance proof bundle for an interaction."""
    version: str = "beaconwise-v7.0"
    mode: str = ProofMode.LIGHTWEIGHT.value
    receipt: Optional[GovernanceReceipt] = None
    routing_proof: Optional[RoutingProof] = None
    epack_chain_hashes: List[str] = field(default_factory=list)
    state_replay: Optional[Dict[str, Any]] = None  # forensic mode only

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "version": self.version,
            "mode": self.mode,
            "epack_chain_hashes": self.epack_chain_hashes,
        }
        if self.receipt:
            d["receipt"] = asdict(self.receipt)
        if self.routing_proof:
            d["routing_proof"] = asdict(self.routing_proof)
        if self.state_replay:
            d["state_replay"] = self.state_replay
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


# ── Signing ───────────────────────────────────────────────────────

def _sign_receipt_fields(receipt: GovernanceReceipt, key: bytes) -> str:
    """HMAC-SHA256 over canonical receipt fields (excludes signature)."""
    payload = stable_json({
        "receipt_id": receipt.receipt_id,
        "epack_hash": receipt.epack_hash,
        "routing_proof_hash": receipt.routing_proof_hash,
        "manifest_hash": receipt.manifest_hash,
        "tsv_snapshot_hash": receipt.tsv_snapshot_hash,
        "scope_gate_decision": receipt.scope_gate_decision,
        "profile": receipt.profile,
        "mode": receipt.mode,
        "timestamp": receipt.timestamp,
    })
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_receipt(
    *,
    receipt_id: str,
    epack_hash: str,
    routing_proof_hash: str,
    manifest_hash: str,
    tsv_snapshot_hash: str,
    scope_gate_decision: str,
    profile: str,
    mode: str,
    signing_key: bytes,
) -> GovernanceReceipt:
    """Create a signed governance receipt."""
    ts = time.time()
    # Build unsigned receipt to compute signature
    unsigned = GovernanceReceipt(
        receipt_id=receipt_id,
        epack_hash=epack_hash,
        routing_proof_hash=routing_proof_hash,
        manifest_hash=manifest_hash,
        tsv_snapshot_hash=tsv_snapshot_hash,
        scope_gate_decision=scope_gate_decision,
        profile=profile,
        mode=mode,
        timestamp=ts,
        signature="",
    )
    sig = _sign_receipt_fields(unsigned, signing_key)
    return GovernanceReceipt(
        receipt_id=receipt_id,
        epack_hash=epack_hash,
        routing_proof_hash=routing_proof_hash,
        manifest_hash=manifest_hash,
        tsv_snapshot_hash=tsv_snapshot_hash,
        scope_gate_decision=scope_gate_decision,
        profile=profile,
        mode=mode,
        timestamp=ts,
        signature=sig,
    )


# ── Verification ──────────────────────────────────────────────────

def verify_receipt(receipt: GovernanceReceipt, key: bytes) -> bool:
    """Third-party verification of a governance receipt."""
    return receipt.verify(key)


def verify_epack_chain(chain: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Verify EPACK hash chain integrity.

    Returns (valid, errors).
    """
    errors: List[str] = []
    if not chain:
        return True, []

    for i, record in enumerate(chain):
        expected = stable_hash({
            "seq": record["seq"],
            "ts": record["ts"],
            "prev_hash": record["prev_hash"],
            "payload": record["payload"],
        })
        if record["hash"] != expected:
            errors.append(f"seq={record['seq']}: hash mismatch (expected {expected[:12]}..., got {record['hash'][:12]}...)")

        if i > 0:
            if record["prev_hash"] != chain[i - 1]["hash"]:
                errors.append(f"seq={record['seq']}: prev_hash does not link to seq={chain[i-1]['seq']}")

    return len(errors) == 0, errors


def verify_routing_proof(proof: RoutingProof) -> Tuple[bool, str]:
    """Verify a routing proof is internally consistent."""
    if not proof.safety_stage1_ok or not proof.safety_stage2_ok:
        if proof.route_sequence and proof.route_sequence[0] != "BOUND":
            return False, "Unsafe input should route to BOUND"
    if proof.seal() == "":
        return False, "Proof seal is empty"
    return True, "OK"


# ── Proof Generation ──────────────────────────────────────────────

def generate_proof(
    *,
    mode: ProofMode = ProofMode.LIGHTWEIGHT,
    epack_chain: List[Dict[str, Any]],
    routing_proof: Optional[RoutingProof] = None,
    manifest_hash: str = "",
    tsv_snapshot: Optional[Dict[str, Any]] = None,
    scope_gate_decision: str = "N/A",
    profile: str = "STANDARD",
    signing_key: Optional[bytes] = None,
    state_replay: Optional[Dict[str, Any]] = None,
) -> GovernanceProof:
    """Generate a complete governance proof bundle."""
    chain_hashes = [r["hash"] for r in epack_chain]
    epack_hash = chain_hashes[-1] if chain_hashes else ""

    proof = GovernanceProof(
        version="beaconwise-v7.0",
        mode=mode.value,
        epack_chain_hashes=chain_hashes,
        routing_proof=routing_proof,
    )

    # Standard+ modes include signed receipts
    if mode in (ProofMode.STANDARD, ProofMode.FORENSIC) and signing_key:
        receipt_id = stable_hash({
            "epack_hash": epack_hash,
            "ts": time.time(),
        })[:16]

        proof.receipt = sign_receipt(
            receipt_id=receipt_id,
            epack_hash=epack_hash,
            routing_proof_hash=routing_proof.seal() if routing_proof else "",
            manifest_hash=manifest_hash,
            tsv_snapshot_hash=stable_hash(tsv_snapshot) if tsv_snapshot else "",
            scope_gate_decision=scope_gate_decision,
            profile=profile,
            mode=mode.value,
            signing_key=signing_key,
        )

    # Forensic mode includes state replay data
    if mode == ProofMode.FORENSIC and state_replay:
        proof.state_replay = state_replay

    return proof


# ── Audit Replay ──────────────────────────────────────────────────

def replay_audit_chain(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Replay an audit chain and annotate each record with verification status.

    Returns list of records with 'verified' and 'verification_error' fields.
    """
    results: List[Dict[str, Any]] = []
    for i, record in enumerate(chain):
        expected = stable_hash({
            "seq": record["seq"],
            "ts": record["ts"],
            "prev_hash": record["prev_hash"],
            "payload": record["payload"],
        })
        verified = record["hash"] == expected
        link_ok = True
        if i > 0:
            link_ok = record["prev_hash"] == chain[i - 1]["hash"]

        results.append({
            "seq": record["seq"],
            "ts": record["ts"],
            "hash": record["hash"],
            "verified": verified and link_ok,
            "hash_ok": verified,
            "link_ok": link_ok,
            "verification_error": None if (verified and link_ok) else
                ("hash mismatch" if not verified else "chain link broken"),
        })
    return results
