# src/ecosphere/governance/failure.py
"""BeaconWise Governance Failure Disclosure Protocol (V7).

When governance cannot determine safety:
  - explicitly signal uncertainty
  - preserve partial audit chain
  - degrade safely
  - prevent silent fallback
  - document failure reason

Produces structured disclosure artifacts suitable for
internal review, regulatory reporting, or public transparency.

Principle: Transparent failure is safer than hidden success.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ecosphere.utils.stable import stable_hash


class FailureSeverity(str, Enum):
    DEGRADED = "degraded"          # Partial functionality, safe
    SAFETY_UNCERTAIN = "safety_uncertain"  # Cannot verify safety
    GOVERNANCE_BREACH = "governance_breach"  # Invariant violated
    SYSTEM_FAILURE = "system_failure"       # Infrastructure down


class FailureAction(str, Enum):
    REFUSE_AND_LOG = "refuse_and_log"
    DEGRADE_AND_LOG = "degrade_and_log"
    ALERT_AND_CONTINUE = "alert_and_continue"
    HALT = "halt"


@dataclass
class GovernanceFailure:
    """Structured governance failure disclosure artifact."""
    failure_id: str
    severity: str
    action_taken: str
    reason: str
    component: str          # which module failed
    timestamp: float
    partial_audit_hash: str  # hash of whatever audit data was captured
    invariants_affected: List[str] = field(default_factory=list)
    remediation: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def seal_hash(self) -> str:
        return stable_hash(self.to_dict())


def create_failure_disclosure(
    *,
    severity: FailureSeverity,
    reason: str,
    component: str,
    partial_audit_data: Optional[Dict[str, Any]] = None,
    invariants_affected: Optional[List[str]] = None,
    remediation: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> GovernanceFailure:
    """Create a structured failure disclosure artifact."""
    ts = time.time()
    partial_hash = stable_hash(partial_audit_data) if partial_audit_data else ""

    # Determine action based on severity
    action_map = {
        FailureSeverity.DEGRADED: FailureAction.DEGRADE_AND_LOG,
        FailureSeverity.SAFETY_UNCERTAIN: FailureAction.REFUSE_AND_LOG,
        FailureSeverity.GOVERNANCE_BREACH: FailureAction.HALT,
        FailureSeverity.SYSTEM_FAILURE: FailureAction.HALT,
    }

    return GovernanceFailure(
        failure_id=stable_hash({"ts": ts, "reason": reason, "component": component})[:16],
        severity=severity.value,
        action_taken=action_map.get(severity, FailureAction.REFUSE_AND_LOG).value,
        reason=reason,
        component=component,
        timestamp=ts,
        partial_audit_hash=partial_hash,
        invariants_affected=invariants_affected or [],
        remediation=remediation,
        details=details or {},
    )


# ── Educational Governance Mode ───────────────────────────────────
# src/ecosphere/governance/education.py functionality included here
# for simplicity (V7 Capability 9).

@dataclass
class GovernanceExplanation:
    """Human-readable explanation of a governance decision."""
    step: int
    layer: str          # TSL, TSV, RIL, TDM, EPACK, TE-CL
    action: str         # what happened
    reason: str         # why it happened
    outcome: str        # what it means for the user
    learn_more: str     # educational note


def explain_governance_decision(
    *,
    route: str,
    safety_stage1_ok: bool,
    safety_stage2_ok: bool,
    safety_stage2_score: float,
    domain: str,
    complexity: int,
    profile: str,
    validation_ok: bool,
    scope_decision: str = "N/A",
) -> List[GovernanceExplanation]:
    """Generate a step-by-step educational explanation of how governance
    processed a given interaction.

    Supports cognitive sovereignty by making governance visible.
    """
    steps: List[GovernanceExplanation] = []

    # Step 1: Safety screening
    s1_outcome = "passed" if safety_stage1_ok else "flagged as unsafe"
    steps.append(GovernanceExplanation(
        step=1,
        layer="TSL (Safety Layer)",
        action=f"Stage 1 pattern screening: {s1_outcome}",
        reason="Regex patterns check for known harmful content categories",
        outcome=f"Input {'cleared' if safety_stage1_ok else 'blocked at'} first safety gate",
        learn_more="Stage 1 uses compiled regular expressions against known violation patterns. "
                   "This is fast and deterministic — same input always gets same result.",
    ))

    if safety_stage1_ok:
        s2_outcome = "passed" if safety_stage2_ok else "flagged"
        steps.append(GovernanceExplanation(
            step=2,
            layer="TSL (Safety Layer)",
            action=f"Stage 2 semantic screening: score={safety_stage2_score:.3f}, {s2_outcome}",
            reason="Cosine similarity against frozen violation exemplars",
            outcome=f"Input {'cleared' if safety_stage2_ok else 'blocked at'} semantic safety gate",
            learn_more="Stage 2 compares input embeddings against known-bad exemplars. "
                       "The exemplars are frozen at build time — the model cannot change them.",
        ))

    # Step 2: Routing
    route_explanations = {
        "BOUND": "Input was blocked by safety layers. No further processing occurs.",
        "DEFER": "This is a high-stakes topic requiring verified expertise before proceeding.",
        "REFLECT": "This question is complex enough to need your confirmation before proceeding.",
        "SCAFFOLD": "This requires a multi-step plan for approval before execution.",
        "TDM": "Normal generation with validation checks.",
    }
    first_route = route.split(",")[0] if route else "TDM"
    steps.append(GovernanceExplanation(
        step=len(steps) + 1,
        layer="RIL (Routing Layer)",
        action=f"Route selected: {first_route}",
        reason=f"Domain={domain}, complexity={complexity}, profile={profile}",
        outcome=route_explanations.get(first_route, "Proceeding through standard pipeline"),
        learn_more="Routing is a pure function of input properties. Given the same input, "
                   "the same route is always chosen — this is deterministic governance.",
    ))

    # Step 3: Validation
    if first_route == "TDM":
        val_outcome = "Output passed all checks" if validation_ok else "Output failed validation — CLARIFY sent instead"
        steps.append(GovernanceExplanation(
            step=len(steps) + 1,
            layer="TDM (Dialogue Manager)",
            action=f"Validation: {'PASS' if validation_ok else 'FAIL'}",
            reason="All outputs must pass schema and alignment validation before delivery",
            outcome=val_outcome,
            learn_more="Validation-before-delivery means you never see unvalidated AI output. "
                       "If validation fails, you get a CLARIFY message instead of bad content.",
        ))

    # Step 4: Scope gate (if applicable)
    if scope_decision != "N/A":
        steps.append(GovernanceExplanation(
            step=len(steps) + 1,
            layer="TE-CL (Consensus Layer)",
            action=f"Scope gate decision: {scope_decision}",
            reason="Output filtered based on your verified role and credential level",
            outcome=f"Content {'approved' if scope_decision == 'PASS' else 'restricted'} for your access tier",
            learn_more="The scope gate ensures you only receive content appropriate for your "
                       "verified expertise level. This protects both you and the system.",
        ))

    # Step 5: EPACK sealing
    steps.append(GovernanceExplanation(
        step=len(steps) + 1,
        layer="EPACK (Audit Layer)",
        action="Interaction sealed into tamper-evident audit record",
        reason="Every governed interaction produces a hash-chained audit record",
        outcome="This interaction is now permanently auditable",
        learn_more="EPACK records form a chain where each record's hash depends on the previous one. "
                   "Like blockchain, tampering with any record breaks the chain — making fraud detectable.",
    ))

    return steps


def format_explanation_text(steps: List[GovernanceExplanation]) -> str:
    """Format governance explanation as readable text."""
    lines = ["═══ How BeaconWise Governed This Interaction ═══\n"]
    for step in steps:
        lines.append(f"Step {step.step}: {step.layer}")
        lines.append(f"  Action: {step.action}")
        lines.append(f"  Why: {step.reason}")
        lines.append(f"  Result: {step.outcome}")
        lines.append(f"  💡 {step.learn_more}")
        lines.append("")
    return "\n".join(lines)
