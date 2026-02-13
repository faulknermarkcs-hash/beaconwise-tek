from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Pattern, Tuple

from pydantic import BaseModel, ConfigDict, Field

from ecosphere.consensus.ledger.hooks import emit_stage_event
from ecosphere.consensus.schemas import PrimaryOutput, SynthesizerOutput
from ecosphere.consensus.verification.types import VerificationContext

Decision = Literal["PASS", "REWRITE", "REFUSE"]


class ScopeGateConfig(BaseModel):
    """Configurable content guard rules per domain.

    Regex patterns trigger if role_level < min_level.
    """
    domain: str = Field("general", description="healthcare | legal | financial | engineering | ...")

    block_patterns: List[Dict[str, Any]] = Field(
        default_factory=lambda: [
            # NOTE: keep patterns reasonably specific to reduce false positives.
            {"pattern": r"\b(you are diagnosed with|diagnosis|prognosis|treatment plan)\b", "min_level": 3, "reason": "Diagnostic/prognostic language"},
            {"pattern": r"\b(expected return\s*\d+%|portfolio allocation|buy\s+[A-Z]{1,5}|sell\s+[A-Z]{1,5}|tax strategy)\b", "min_level": 3, "reason": "Investment advice"},
            {"pattern": r"\b(file a lawsuit|you should sue|settlement range|liability exposure)\b", "min_level": 3, "reason": "Legal strategy/advice"},
            {"pattern": r"\b(p-value|confidence interval|statistical significance|replication)\b", "min_level": 4, "reason": "Advanced statistical detail"},
        ],
        description="Each dict: pattern (regex), min_level (int), reason (str)",
    )

    require_disclaimer_low_tier: bool = True
    low_tier_disclaimer_snippet: str = "This is general information only and not professional advice. Consult a qualified expert."

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


@dataclass(frozen=True)
class _CompiledRule:
    pattern: Pattern[str]
    min_level: int
    reason: str
    raw: str


def _compile_rules(config: ScopeGateConfig) -> List[_CompiledRule]:
    compiled: List[_CompiledRule] = []
    for rule in config.block_patterns:
        raw = str(rule["pattern"])
        compiled.append(
            _CompiledRule(
                pattern=re.compile(raw, re.IGNORECASE),
                min_level=int(rule["min_level"]),
                reason=str(rule.get("reason", "")),
                raw=raw,
            )
        )
    return compiled


def scope_gate_v1(
    *,
    output: PrimaryOutput | SynthesizerOutput,
    verification: VerificationContext,
    config: ScopeGateConfig,
    epack: str,
    run_id: str,
) -> Dict[str, Any]:
    """Deterministic post-generation scope guard.

    Returns:
      { "decision": PASS|REWRITE|REFUSE, "reason": str, "details": {...} }
    """
    role_level = int(verification.role_level)

    full_text = getattr(output, "answer", "") or ""
    if hasattr(output, "reasoning_trace") and getattr(output, "reasoning_trace"):
        full_text += " " + " ".join(getattr(output, "reasoning_trace") or [])

    compiled = _compile_rules(config)

    violations: List[Dict[str, Any]] = []
    for rule in compiled:
        matches = rule.pattern.findall(full_text)
        if matches and role_level < rule.min_level:
            # normalize matches to strings
            sample = []
            for m in matches[:3]:
                sample.append(m if isinstance(m, str) else str(m))
            violations.append(
                {
                    "pattern": rule.raw,
                    "matches": sample,
                    "required_level": rule.min_level,
                    "reason": rule.reason,
                }
            )

    disclaimer_issue: Optional[str] = None
    if config.require_disclaimer_low_tier and role_level <= 2:
        if config.low_tier_disclaimer_snippet.lower() not in full_text.lower():
            disclaimer_issue = "Missing required low-tier disclaimer"

    if violations or disclaimer_issue:
        emit_stage_event(
            epack=epack,
            run_id=run_id,
            stage="tecl.scope_gate.violation",
            payload={
                "domain": config.domain,
                "role_level": role_level,
                "verification": {"verified": verification.verified, "role": verification.role},
                "violations": violations,
                "disclaimer_issue": disclaimer_issue,
            },
        )

        if role_level >= 2:
            return {
                "decision": "REWRITE",
                "reason": f"Scope violations for role_level {role_level}",
                "details": {
                    "violations": violations,
                    "disclaimer_issue": disclaimer_issue,
                    "suggested_rewrite_prompt": (
                        f"Rewrite the output to be safe and appropriate for role_level {role_level} ({verification.role}). "
                        "Remove diagnostic, prognostic, prescriptive, strategic, or probabilistic language. "
                        f'Add this disclaimer at the top: "{config.low_tier_disclaimer_snippet}". '
                        "Keep helpful general information only. Be concise. "
                        f"Original output: {full_text[:800]}..."
                    ),
                },
            }
        return {
            "decision": "REFUSE",
            "reason": "Output contains content unsafe for public/unverified users",
            "details": {"violations": violations, "disclaimer_issue": disclaimer_issue},
        }

    emit_stage_event(
        epack=epack,
        run_id=run_id,
        stage="tecl.scope_gate.pass",
        payload={"domain": config.domain, "role_level": role_level},
    )
    return {"decision": "PASS", "reason": "Content appropriate for verified role", "details": {}}
