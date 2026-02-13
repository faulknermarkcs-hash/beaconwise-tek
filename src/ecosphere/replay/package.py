"""Replay Package — formal artifact bundle for deterministic replay.

A Replay Package (RP) is the minimal set of artifacts required to reproduce
and verify a governed run, as specified in REPLAY_PROTOCOL.md §3.3 and §5.

This module provides:
  - ReplayPackage dataclass matching the DRP specification
  - build_replay_package() to construct an RP from kernel session state
  - verify_replay_package() to validate RP integrity without replaying
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from ecosphere.utils.stable import stable_hash


@dataclass
class ReplayPackage:
    """Minimal artifact set for deterministic replay verification.

    Fields map to REPLAY_PROTOCOL.md §5 (Required Artifacts):
      §5.1 Input Artifacts
      §5.2 Governance Configuration Snapshot
      §5.3 Evidence Chain State
      §5.4 Validator Decisions
      §5.5 Environment Metadata
    """

    # §5.1 Input Artifacts
    input_payload_hash: str
    input_metadata: Dict[str, Any] = field(default_factory=dict)

    # §5.2 Governance Configuration Snapshot
    kernel_version: str = ""
    governance_profile_id: str = ""
    validator_set_id: str = ""
    determinism_policy: str = "strict"
    routing_decisions: Dict[str, Any] = field(default_factory=dict)

    # §5.3 Evidence Chain State
    epack_chain: List[Dict[str, Any]] = field(default_factory=list)
    epack_head_hash: str = ""

    # §5.4 Validator Decisions
    validator_results: List[Dict[str, Any]] = field(default_factory=list)
    consensus_result: Optional[Dict[str, Any]] = None

    # §5.5 Environment Metadata
    environment: Dict[str, Any] = field(default_factory=dict)

    # Package integrity
    package_hash: str = ""

    def seal(self) -> "ReplayPackage":
        """Compute and set the package_hash over all content fields."""
        content = {
            "input_payload_hash": self.input_payload_hash,
            "input_metadata": self.input_metadata,
            "kernel_version": self.kernel_version,
            "governance_profile_id": self.governance_profile_id,
            "validator_set_id": self.validator_set_id,
            "determinism_policy": self.determinism_policy,
            "routing_decisions": self.routing_decisions,
            "epack_chain": self.epack_chain,
            "epack_head_hash": self.epack_head_hash,
            "validator_results": self.validator_results,
            "consensus_result": self.consensus_result,
            "environment": self.environment,
        }
        self.package_hash = stable_hash(content)
        return self

    def verify_seal(self) -> bool:
        """Check that package_hash matches current content."""
        saved = self.package_hash
        self.seal()
        valid = self.package_hash == saved
        self.package_hash = saved
        return valid

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_replay_package(
    *,
    session_epacks: List[Dict[str, Any]],
    kernel_version: str = "",
    governance_profile: str = "",
    validator_set_id: str = "",
    routing_decisions: Optional[Dict[str, Any]] = None,
    validator_results: Optional[List[Dict[str, Any]]] = None,
    consensus_result: Optional[Dict[str, Any]] = None,
    environment: Optional[Dict[str, Any]] = None,
) -> ReplayPackage:
    """Build a sealed ReplayPackage from session artifacts.

    Args:
        session_epacks: The EPACK chain records from the session
        kernel_version: Semantic version + build hash
        governance_profile: Which governance profile was active
        validator_set_id: Which validator set was active
        routing_decisions: Routing metadata (route sequence, reasons)
        validator_results: Per-validator decision records
        consensus_result: Final consensus outcome
        environment: Python version, platform, dependency versions
    """
    head_hash = session_epacks[-1]["hash"] if session_epacks else ""
    input_hash = ""
    if session_epacks:
        payload = session_epacks[0].get("payload", {})
        input_hash = payload.get("user_text_hash", "")

    rp = ReplayPackage(
        input_payload_hash=input_hash,
        input_metadata={"epack_count": len(session_epacks)},
        kernel_version=kernel_version,
        governance_profile_id=governance_profile,
        validator_set_id=validator_set_id,
        determinism_policy="strict",
        routing_decisions=routing_decisions or {},
        epack_chain=session_epacks,
        epack_head_hash=head_hash,
        validator_results=validator_results or [],
        consensus_result=consensus_result,
        environment=environment or {},
    )
    return rp.seal()


def verify_replay_package(rp: ReplayPackage) -> Dict[str, Any]:
    """Validate a ReplayPackage's integrity without performing replay.

    Checks:
      1. Package seal (hash matches content)
      2. EPACK chain integrity (prev_hash linkage)
      3. Head hash consistency
      4. Required fields present

    Returns dict with passed/failed status and details.
    """
    checks = []

    # 1. Package seal
    seal_ok = rp.verify_seal()
    checks.append({"check": "package_seal", "passed": seal_ok})

    # 2. EPACK chain integrity
    chain_ok = True
    chain_errors = []
    for i, ep in enumerate(rp.epack_chain):
        # Hash integrity
        expected = stable_hash({
            "seq": ep.get("seq"), "ts": ep.get("ts"),
            "prev_hash": ep.get("prev_hash"), "payload": ep.get("payload"),
        })
        if ep.get("hash") != expected:
            chain_ok = False
            chain_errors.append(f"record {i}: hash mismatch")
        # Linkage
        if i == 0:
            if ep.get("prev_hash") != "GENESIS":
                chain_ok = False
                chain_errors.append(f"record 0: expected GENESIS")
        else:
            if ep.get("prev_hash") != rp.epack_chain[i - 1].get("hash"):
                chain_ok = False
                chain_errors.append(f"record {i}: broken linkage")
    checks.append({"check": "chain_integrity", "passed": chain_ok, "errors": chain_errors})

    # 3. Head hash consistency
    head_ok = True
    if rp.epack_chain:
        head_ok = rp.epack_head_hash == rp.epack_chain[-1].get("hash", "")
    checks.append({"check": "head_hash", "passed": head_ok})

    # 4. Required fields
    required_ok = bool(rp.kernel_version and rp.input_payload_hash)
    checks.append({"check": "required_fields", "passed": required_ok})

    all_passed = all(c["passed"] for c in checks)
    return {"passed": all_passed, "checks": checks}
