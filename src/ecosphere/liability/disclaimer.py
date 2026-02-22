"""ecosphere.liability.disclaimer — Brick 12 liability containment helpers."""

from __future__ import annotations

from typing import Dict


def generate_disclaimer(domain: str = "GENERAL", risk_level: str = "UNKNOWN") -> str:
    d = (domain or "GENERAL").upper()
    r = (risk_level or "UNKNOWN").upper()

    msg = "This output is AI-assisted and provided for informational purposes."
    if d in ("HIGH_STAKES", "MEDICAL", "LEGAL", "FINANCIAL"):
        msg += " It is not professional advice."
    if r in ("ELEVATED", "HIGH", "CRITICAL"):
        msg += " Independent expert review is required before acting."
    return msg


def responsibility_tag(human_final: bool, human_override: bool = False) -> str:
    if human_override:
        return "human"
    if human_final:
        return "shared"
    return "automation"


def liability_metadata(*, domain: str, risk_level: str, human_final: bool, human_override: bool = False) -> Dict[str, str]:
    return {
        "domain": domain,
        "risk_level": risk_level,
        "responsibility": responsibility_tag(human_final, human_override),
        "disclaimer": generate_disclaimer(domain, risk_level),
    }
