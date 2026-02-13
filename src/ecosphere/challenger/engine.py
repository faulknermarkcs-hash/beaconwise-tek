# src/ecosphere/challenger/engine.py
"""Challenger Engine — adversarial governance pressure.

Decides when to trigger the challenger, parses its output,
and applies governance constraints via deterministic arbitration.

The challenger is NOT a vote. It is governance pressure.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from ecosphere.challenger.config import (
    ChallengerRules, ChallengePack, DEFAULT_CHALLENGER_RULES,
    CHALLENGER_SYSTEM_PROMPT, build_challenger_prompt,
)
from ecosphere.utils.stable import stable_hash


# ── Trigger Reasons (enum-like constants) ─────────────────────

class TriggerReason:
    HIGH_STAKES = "high_stakes_domain"
    DISAGREEMENT = "primary_validator_disagreement"
    GATE_HIT = "scope_gate_rewrite_or_refuse"
    LOW_EVIDENCE = "low_evidence_level"
    POLICY = "policy_mandated"


@dataclass
class ChallengerTriggerResult:
    """Whether and why the challenger should fire."""
    should_trigger: bool
    reasons: List[str] = field(default_factory=list)
    disagreement_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Disagreement Scoring ──────────────────────────────────────

def compute_disagreement_score(
    primary_text: str,
    validator_text: str,
) -> float:
    """Lightweight disagreement score (no embeddings, pure heuristics).

    Uses Jaccard distance + negation mismatch + length ratio.
    Returns 0.0 (identical) to 1.0 (total disagreement).
    """
    if not primary_text or not validator_text:
        return 0.0

    p_words = set(primary_text.lower().split())
    v_words = set(validator_text.lower().split())

    if not p_words or not v_words:
        return 0.0

    # Jaccard distance
    intersection = p_words & v_words
    union = p_words | v_words
    jaccard_sim = len(intersection) / len(union) if union else 1.0
    disagreement = 1.0 - jaccard_sim

    # Negation mismatch bonus
    negation_words = {"not", "no", "never", "cannot", "shouldn't", "don't", "won't", "isn't", "aren't"}
    p_negs = p_words & negation_words
    v_negs = v_words & negation_words
    if p_negs != v_negs:
        disagreement = min(1.0, disagreement + 0.15)

    # Length ratio penalty
    len_ratio = min(len(primary_text), len(validator_text)) / max(len(primary_text), len(validator_text), 1)
    if len_ratio < 0.3:
        disagreement = min(1.0, disagreement + 0.1)

    return round(disagreement, 3)


# ── Trigger Logic (pure function — deterministic) ─────────────

def should_trigger_challenger(
    *,
    rules: ChallengerRules,
    domain: str = "GENERAL",
    disagreement_score: float = 0.0,
    scope_gate_decision: str = "PASS",
    evidence_level: str = "E1",
    challenges_this_session: int = 0,
) -> ChallengerTriggerResult:
    """Determine whether to invoke the challenger."""
    if not rules.enabled:
        return ChallengerTriggerResult(should_trigger=False)

    if challenges_this_session >= rules.max_challenges_per_session:
        return ChallengerTriggerResult(
            should_trigger=False,
            reasons=["max_challenges_reached"],
        )

    reasons: List[str] = []

    if rules.trigger_on_high_stakes and domain == "HIGH_STAKES":
        reasons.append(TriggerReason.HIGH_STAKES)

    if rules.trigger_on_disagreement and disagreement_score >= rules.disagreement_threshold:
        reasons.append(TriggerReason.DISAGREEMENT)

    if rules.trigger_on_gate and scope_gate_decision in ("REWRITE", "REFUSE"):
        reasons.append(TriggerReason.GATE_HIT)

    if rules.trigger_on_low_evidence and domain == "HIGH_STAKES" and evidence_level in ("E0", "E1"):
        reasons.append(TriggerReason.LOW_EVIDENCE)

    return ChallengerTriggerResult(
        should_trigger=len(reasons) > 0,
        reasons=reasons,
        disagreement_score=disagreement_score,
    )


# ── ChallengePack Parsing ────────────────────────────────────

def parse_challenge_pack(raw_text: str) -> Tuple[Optional[ChallengePack], str]:
    """Parse raw model output into a ChallengePack.

    Returns (pack, error). If parsing fails, pack is None.
    """
    text = raw_text.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        d = json.loads(text)
        if not isinstance(d, dict):
            return None, "Challenger output is not a JSON object"
        pack = ChallengePack.from_dict(d)
        return pack, ""
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"
    except Exception as e:
        return None, f"ChallengePack parse error: {e}"


# ── Arbitration (deterministic constraint application) ────────

@dataclass
class ArbitrationResult:
    """Result of applying challenger constraints."""
    final_action: str              # PASS / REWRITE / REFUSE
    challenger_applied: bool
    constraints_applied: List[str] = field(default_factory=list)
    original_gate_decision: str = "PASS"
    rewrite_instructions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def arbitrate(
    *,
    pack: ChallengePack,
    scope_gate_decision: str = "PASS",
    role_level: int = 0,
    domain: str = "GENERAL",
) -> ArbitrationResult:
    """Apply ChallengePack as governance constraints.

    Deterministic rules:
    1. REFUSE from challenger → enforce unless expert + gate PASS
    2. High-risk claims + low tier → REWRITE or REFUSE
    3. Conflicts on high-stakes → force REWRITE with uncertainty
    4. Missing evidence on high-stakes → REWRITE to E1-safe
    5. Challenger REWRITE → upgrade action if currently PASS
    """
    constraints: List[str] = []
    action = "PASS"
    rewrite_instr: List[str] = list(pack.rewrite_instructions)

    # Rule 1: Challenger says REFUSE
    if pack.forces_refuse:
        if role_level >= 3 and scope_gate_decision == "PASS":
            action = "REWRITE"
            constraints.append("challenger_refuse_downgraded_for_expert")
            rewrite_instr.append("Add expert-only caveat and verification reminder")
        else:
            return ArbitrationResult(
                final_action="REFUSE",
                challenger_applied=True,
                constraints_applied=["challenger_refuse_enforced"],
                original_gate_decision=scope_gate_decision,
                rewrite_instructions=rewrite_instr,
            )

    # Rule 2: High-risk claims for low-tier users
    if pack.has_high_risk_claims and role_level < 2:
        action = max(action, "REWRITE", key=lambda x: ["PASS", "REWRITE", "REFUSE"].index(x))
        constraints.append("high_risk_claims_for_low_tier")
        rewrite_instr.append("Remove or soften high-risk clinical claims")
        rewrite_instr.append("Add mandatory disclaimer for non-professional tier")

    # Rule 3: Conflicts on high-stakes
    if pack.has_conflicts and domain == "HIGH_STAKES":
        action = max(action, "REWRITE", key=lambda x: ["PASS", "REWRITE", "REFUSE"].index(x))
        constraints.append("conflicts_on_high_stakes")
        rewrite_instr.append("Add explicit uncertainty language")
        rewrite_instr.append("Present alternative hypotheses where models disagree")

    # Rule 4: Missing evidence on high-stakes
    if pack.missing_evidence and domain == "HIGH_STAKES":
        action = max(action, "REWRITE", key=lambda x: ["PASS", "REWRITE", "REFUSE"].index(x))
        constraints.append("missing_evidence_high_stakes")
        rewrite_instr.append("Reframe to E1-safe (general information only)")

    # Rule 5: Challenger recommends REWRITE
    if pack.forces_rewrite and action == "PASS":
        action = "REWRITE"
        constraints.append("challenger_rewrite_recommended")

    return ArbitrationResult(
        final_action=action,
        challenger_applied=True,
        constraints_applied=constraints,
        original_gate_decision=scope_gate_decision,
        rewrite_instructions=rewrite_instr,
    )


# ── EPACK Event Helpers ───────────────────────────────────────

def challenger_event_triggered(
    trigger_result: ChallengerTriggerResult,
) -> Dict[str, Any]:
    """EPACK stage: tecl.challenger.triggered"""
    return {
        "stage": "tecl.challenger.triggered",
        "reasons": trigger_result.reasons,
        "disagreement_score": trigger_result.disagreement_score,
        "ts": time.time(),
    }


def challenger_event_skipped(reason: str = "not_triggered") -> Dict[str, Any]:
    """EPACK stage: tecl.challenger.skipped"""
    return {
        "stage": "tecl.challenger.skipped",
        "reason": reason,
        "ts": time.time(),
    }


def challenger_event_output(
    pack: ChallengePack,
    arbitration: ArbitrationResult,
) -> Dict[str, Any]:
    """EPACK stage: tecl.arbitration.applied_constraints"""
    return {
        "stage": "tecl.arbitration.applied_constraints",
        "challenge_pack_hash": stable_hash(pack.to_dict()),
        "recommended_action": pack.recommended_action,
        "final_action": arbitration.final_action,
        "constraints_applied": arbitration.constraints_applied,
        "attack_surface": pack.attack_surface,
        "ts": time.time(),
    }
