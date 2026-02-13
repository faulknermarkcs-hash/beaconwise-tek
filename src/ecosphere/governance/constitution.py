# src/ecosphere/governance/constitution.py
"""BeaconWise Governance Constitution (V7 Capabilities 3, 8).

Machine-readable constitutional enforcement:
  - immutable governance invariants
  - constitutional check functions
  - anti-capture safeguards
  - fork-continuity audit preservation
  - invariant violation detection

Principle: Governance stability requires explicit constitutional grounding.
Principle: Governance must not be quietly weakened.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ecosphere.utils.stable import stable_hash


# ── Constitutional Invariants ─────────────────────────────────────

class InvariantSeverity(str, Enum):
    """How critical an invariant violation is."""
    CRITICAL = "critical"      # System must halt or refuse
    WARNING = "warning"        # Log and continue with caution
    ADVISORY = "advisory"      # Informational only


@dataclass(frozen=True)
class GovernanceInvariant:
    """A single governance invariant."""
    id: str
    name: str
    description: str
    severity: str  # InvariantSeverity value
    check_fn_name: str  # name of the function that checks this
    category: str  # e.g. "transparency", "determinism", "audit", "anti-capture"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── The Constitution ──────────────────────────────────────────────

# These are the non-negotiable invariants of BeaconWise governance.
# They cannot be overridden by configuration, deployment, or integration.

CONSTITUTION: List[GovernanceInvariant] = [
    # --- Determinism ---
    GovernanceInvariant(
        id="INV-DET-001",
        name="Deterministic Routing",
        description="All routing decisions must be pure functions of their inputs. "
                    "Given the same InputVector and SessionState, the same route must be chosen.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_deterministic_routing",
        category="determinism",
    ),
    GovernanceInvariant(
        id="INV-DET-002",
        name="No Hidden State",
        description="No governance decision may depend on state not captured in the EPACK chain. "
                    "All decision-relevant state must be auditable.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_no_hidden_state",
        category="determinism",
    ),

    # --- Transparency ---
    GovernanceInvariant(
        id="INV-TRA-001",
        name="Audit Chain Completeness",
        description="Every governed interaction must produce an EPACK record. "
                    "No interaction may bypass the audit chain.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_audit_completeness",
        category="transparency",
    ),
    GovernanceInvariant(
        id="INV-TRA-002",
        name="Failure Transparency",
        description="When governance cannot determine safety, uncertainty must be "
                    "explicitly signaled. Silent fallback is prohibited.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_failure_transparency",
        category="transparency",
    ),
    GovernanceInvariant(
        id="INV-TRA-003",
        name="Non-Persuasion",
        description="BeaconWise must not optimize for persuasion, engagement, or "
                    "behavioral influence. Any output-influencing capability must include "
                    "corresponding transparency and user override controls.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_non_persuasion",
        category="transparency",
    ),

    # --- Audit Permanence ---
    GovernanceInvariant(
        id="INV-AUD-001",
        name="Hash Chain Integrity",
        description="EPACK records must form a tamper-evident hash chain. "
                    "Each record's prev_hash must equal the prior record's hash.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_hash_chain_integrity",
        category="audit",
    ),
    GovernanceInvariant(
        id="INV-AUD-002",
        name="Provenance Manifests",
        description="Every EPACK record must include a build manifest with kernel version "
                    "and feature flags, sealed with a manifest hash.",
        severity=InvariantSeverity.WARNING.value,
        check_fn_name="check_provenance_manifest",
        category="audit",
    ),

    # --- Anti-Capture ---
    GovernanceInvariant(
        id="INV-CAP-001",
        name="Vendor Neutrality",
        description="No single AI provider, cloud platform, or organization may gain "
                    "privileged governance control. Adapters must be provider-agnostic.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_vendor_neutrality",
        category="anti-capture",
    ),
    GovernanceInvariant(
        id="INV-CAP-002",
        name="Fork Continuity",
        description="Audit chains must survive forks. Any fork of BeaconWise must "
                    "preserve the existing audit chain and governance proofs.",
        severity=InvariantSeverity.WARNING.value,
        check_fn_name="check_fork_continuity",
        category="anti-capture",
    ),
    GovernanceInvariant(
        id="INV-CAP-003",
        name="Configuration Transparency",
        description="All governance configuration changes must produce audit events. "
                    "No silent reconfiguration is permitted.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_config_transparency",
        category="anti-capture",
    ),

    # --- Safety ---
    GovernanceInvariant(
        id="INV-SAF-001",
        name="Validation Before Delivery",
        description="No model output may reach the user without validation. "
                    "Validation failure must result in CLARIFY or REFUSE, never passthrough.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_validation_before_delivery",
        category="safety",
    ),
    GovernanceInvariant(
        id="INV-SAF-002",
        name="Human Override Preservation",
        description="Governance infrastructure must augment human judgment, not replace it. "
                    "Meaningful human override capability must always be preserved.",
        severity=InvariantSeverity.CRITICAL.value,
        check_fn_name="check_human_override",
        category="safety",
    ),

    # --- Evolution ---
    GovernanceInvariant(
        id="INV-EVO-001",
        name="Backward Compatibility",
        description="Upgrades must preserve backward compatibility of audit formats, "
                    "governance proofs, and interoperability schemas wherever feasible.",
        severity=InvariantSeverity.WARNING.value,
        check_fn_name="check_backward_compatibility",
        category="evolution",
    ),
]


# ── Check Functions ───────────────────────────────────────────────

@dataclass
class InvariantCheckResult:
    invariant_id: str
    passed: bool
    message: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)


def check_audit_completeness(
    interaction_count: int,
    epack_count: int,
) -> InvariantCheckResult:
    """INV-TRA-001: Every interaction must produce an EPACK."""
    passed = epack_count >= interaction_count
    return InvariantCheckResult(
        invariant_id="INV-TRA-001",
        passed=passed,
        message="OK" if passed else f"Missing EPACKs: {interaction_count} interactions but only {epack_count} records",
        details={"interaction_count": interaction_count, "epack_count": epack_count},
    )


def check_hash_chain_integrity(chain: List[Dict[str, Any]]) -> InvariantCheckResult:
    """INV-AUD-001: Verify hash chain links."""
    if not chain:
        return InvariantCheckResult(invariant_id="INV-AUD-001", passed=True, message="Empty chain (trivially valid)")

    for i, record in enumerate(chain):
        expected = stable_hash({
            "seq": record["seq"],
            "ts": record["ts"],
            "prev_hash": record["prev_hash"],
            "payload": record["payload"],
        })
        if record["hash"] != expected:
            return InvariantCheckResult(
                invariant_id="INV-AUD-001", passed=False,
                message=f"Hash mismatch at seq={record['seq']}",
                details={"seq": record["seq"], "expected": expected[:16], "actual": record["hash"][:16]},
            )
        if i > 0 and record["prev_hash"] != chain[i - 1]["hash"]:
            return InvariantCheckResult(
                invariant_id="INV-AUD-001", passed=False,
                message=f"Chain link broken at seq={record['seq']}",
                details={"seq": record["seq"]},
            )

    return InvariantCheckResult(invariant_id="INV-AUD-001", passed=True, message=f"Chain verified: {len(chain)} records")


def check_provenance_manifest(epack_payload: Dict[str, Any]) -> InvariantCheckResult:
    """INV-AUD-002: Check that EPACK contains build manifest."""
    manifest = epack_payload.get("build_manifest")
    if not manifest:
        return InvariantCheckResult(
            invariant_id="INV-AUD-002", passed=False,
            message="Missing build_manifest in EPACK payload",
        )
    if "manifest_hash" not in manifest:
        return InvariantCheckResult(
            invariant_id="INV-AUD-002", passed=False,
            message="Build manifest missing manifest_hash",
        )
    return InvariantCheckResult(invariant_id="INV-AUD-002", passed=True, message="OK")


def check_validation_before_delivery(
    validation_ran: bool,
    validation_ok: Optional[bool],
    output_delivered: bool,
) -> InvariantCheckResult:
    """INV-SAF-001: No unvalidated output delivery."""
    if output_delivered and not validation_ran:
        return InvariantCheckResult(
            invariant_id="INV-SAF-001", passed=False,
            message="Output delivered without validation",
        )
    if output_delivered and validation_ok is False:
        return InvariantCheckResult(
            invariant_id="INV-SAF-001", passed=False,
            message="Failed validation output was delivered",
        )
    return InvariantCheckResult(invariant_id="INV-SAF-001", passed=True, message="OK")


def check_vendor_neutrality(adapter_providers: List[str]) -> InvariantCheckResult:
    """INV-CAP-001: Multiple providers must be supported."""
    unique = set(adapter_providers)
    if len(unique) < 2:
        return InvariantCheckResult(
            invariant_id="INV-CAP-001", passed=False,
            message=f"Only {len(unique)} adapter provider(s) registered; minimum 2 required",
            details={"providers": list(unique)},
        )
    return InvariantCheckResult(
        invariant_id="INV-CAP-001", passed=True,
        message=f"OK: {len(unique)} providers registered",
        details={"providers": list(unique)},
    )


# ── Constitutional Enforcement ────────────────────────────────────

def get_constitution() -> List[Dict[str, Any]]:
    """Return the constitution as a list of dicts (machine-readable)."""
    return [inv.to_dict() for inv in CONSTITUTION]


def get_constitution_hash() -> str:
    """Compute a stable hash of the entire constitution."""
    return stable_hash([inv.to_dict() for inv in CONSTITUTION])


def run_constitutional_checks(
    *,
    interaction_count: int = 0,
    epack_chain: Optional[List[Dict[str, Any]]] = None,
    epack_payload: Optional[Dict[str, Any]] = None,
    validation_ran: bool = True,
    validation_ok: Optional[bool] = True,
    output_delivered: bool = False,
    adapter_providers: Optional[List[str]] = None,
) -> List[InvariantCheckResult]:
    """Run all applicable constitutional checks and return results."""
    results: List[InvariantCheckResult] = []

    epack_chain = epack_chain or []
    adapter_providers = adapter_providers or ["anthropic", "openai", "mock"]

    results.append(check_audit_completeness(interaction_count, len(epack_chain)))
    results.append(check_hash_chain_integrity(epack_chain))

    if epack_payload:
        results.append(check_provenance_manifest(epack_payload))

    results.append(check_validation_before_delivery(validation_ran, validation_ok, output_delivered))
    results.append(check_vendor_neutrality(adapter_providers))

    return results


def any_critical_violations(results: List[InvariantCheckResult]) -> bool:
    """Check if any critical invariant was violated."""
    critical_ids = {inv.id for inv in CONSTITUTION if inv.severity == InvariantSeverity.CRITICAL.value}
    for r in results:
        if not r.passed and r.invariant_id in critical_ids:
            return True
    return False
