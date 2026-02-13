# src/ecosphere/challenger/config.py
"""Challenger configuration and ChallengePack schema.

ChallengerRules: when to invoke the adversarial challenger.
ChallengePack: structured critique output (no prose, no user answers).

Principle: The Challenger produces governance pressure, not answers.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ── Challenger Rules ──────────────────────────────────────────

@dataclass
class ChallengerRules:
    """When and how to invoke the Challenger."""
    enabled: bool = True
    trigger_on_high_stakes: bool = True
    trigger_on_disagreement: bool = True
    disagreement_threshold: float = 0.22
    trigger_on_gate: bool = True             # scope gate hit (REWRITE/REFUSE)
    trigger_on_low_evidence: bool = True     # E0/E1 on high-stakes
    max_challenges_per_session: int = 10
    timeout_s: float = 6.0
    max_tokens: int = 400

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChallengerRules":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


DEFAULT_CHALLENGER_RULES = ChallengerRules()


# ── ChallengePack Schema ─────────────────────────────────────

@dataclass
class CriticalClaim:
    """A claim flagged by the challenger for scrutiny."""
    claim: str
    risk: str              # "low", "medium", "high", "critical"
    why: str
    evidence_needed: str   # "E0", "E1", "E2", "E3"


@dataclass
class Conflict:
    """Disagreement between Primary and Validator."""
    between: List[str]     # e.g. ["primary", "validator_1"]
    topic: str
    impact: str            # "low", "medium", "high"


@dataclass
class MissingEvidence:
    """Evidence gap identified by the challenger."""
    for_claim: str
    suggested_sources: List[str]


@dataclass
class ChallengePack:
    """Structured adversarial critique — the Challenger's output.

    The Challenger NEVER answers the user's question.
    It only produces this structured critique that becomes
    governance pressure on the arbitration stage.
    """
    attack_surface: List[str] = field(default_factory=list)
    critical_claims: List[CriticalClaim] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    missing_evidence: List[MissingEvidence] = field(default_factory=list)
    questions_for_primary: List[str] = field(default_factory=list)
    recommended_action: str = "PASS"        # PASS / REWRITE / REFUSE
    rewrite_instructions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attack_surface": self.attack_surface,
            "critical_claims": [asdict(c) for c in self.critical_claims],
            "conflicts": [asdict(c) for c in self.conflicts],
            "missing_evidence": [
                {"for": m.for_claim, "suggested_sources": m.suggested_sources}
                for m in self.missing_evidence
            ],
            "questions_for_primary": self.questions_for_primary,
            "recommended_action": self.recommended_action,
            "rewrite_instructions": self.rewrite_instructions,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChallengePack":
        """Parse raw dict into a ChallengePack."""
        pack = cls()
        pack.attack_surface = d.get("attack_surface", [])
        pack.critical_claims = [
            CriticalClaim(**c) for c in d.get("critical_claims", [])
        ]
        pack.conflicts = [
            Conflict(**c) for c in d.get("conflicts", [])
        ]
        pack.missing_evidence = [
            MissingEvidence(
                for_claim=m.get("for", m.get("for_claim", "")),
                suggested_sources=m.get("suggested_sources", []),
            )
            for m in d.get("missing_evidence", [])
        ]
        pack.questions_for_primary = d.get("questions_for_primary", [])
        pack.recommended_action = d.get("recommended_action", "PASS")
        pack.rewrite_instructions = d.get("rewrite_instructions", [])
        return pack

    @property
    def has_high_risk_claims(self) -> bool:
        return any(c.risk in ("high", "critical") for c in self.critical_claims)

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def forces_rewrite(self) -> bool:
        return self.recommended_action == "REWRITE"

    @property
    def forces_refuse(self) -> bool:
        return self.recommended_action == "REFUSE"

    @property
    def is_clean(self) -> bool:
        return (
            self.recommended_action == "PASS"
            and not self.has_high_risk_claims
            and not self.has_conflicts
        )


# ── Challenger System Prompt ──────────────────────────────────

CHALLENGER_SYSTEM_PROMPT = """\
You are an adversarial governance reviewer for BeaconWise, a deterministic AI governance system.

Your role is to find weaknesses, not to answer the user's question. You NEVER produce answers for the user.

You receive:
- The original user query
- The primary model's response
- The validator model's response (if available)
- The user's verification context (role, tier level)

You MUST respond with ONLY a valid JSON object matching this schema:
{
  "attack_surface": ["list of vulnerability categories found"],
  "critical_claims": [{"claim": "...", "risk": "high|medium|low", "why": "...", "evidence_needed": "E0|E1|E2|E3"}],
  "conflicts": [{"between": ["primary", "validator_1"], "topic": "...", "impact": "high|medium|low"}],
  "missing_evidence": [{"for": "...", "suggested_sources": ["guideline", "peer_review"]}],
  "questions_for_primary": ["What assumptions...?"],
  "recommended_action": "PASS|REWRITE|REFUSE",
  "rewrite_instructions": ["Add disclaimer...", "Remove diagnostic language..."]
}

Rules:
- Output ONLY valid JSON. No prose, no markdown, no explanation.
- Be aggressive about flagging risks. False positives are acceptable; false negatives are not.
- If the primary and validator agree and content is safe for the user's tier: recommended_action = "PASS"
- If content needs modification for the user's tier: recommended_action = "REWRITE"
- If content is unsafe at any tier: recommended_action = "REFUSE"
"""


def build_challenger_prompt(
    *,
    user_query: str,
    primary_response: str,
    validator_response: str = "",
    role: str = "public",
    role_level: int = 0,
    domain: str = "GENERAL",
) -> str:
    """Build the challenger input prompt."""
    parts = [
        f"DOMAIN: {domain}",
        f"USER QUERY:\n{user_query[:1000]}",
        f"\nPRIMARY RESPONSE:\n{primary_response[:2000]}",
    ]
    if validator_response:
        parts.append(f"\nVALIDATOR RESPONSE:\n{validator_response[:2000]}")
    parts.append(f"\nUSER CONTEXT: role={role}, tier_level={role_level}")
    parts.append("\nProduce your ChallengePack JSON now.")
    return "\n".join(parts)
