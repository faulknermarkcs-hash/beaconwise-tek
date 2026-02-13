from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EvidenceType(str, Enum):
    EV_SELF_ASSERTION = "EV_SELF_ASSERTION"
    EV_PERFORMANCE = "EV_PERFORMANCE"
    EV_COMPLIANCE = "EV_COMPLIANCE"
    EV_ERROR_PATTERN = "EV_ERROR_PATTERN"
    EV_VERIFICATION_STEP = "EV_VERIFICATION_STEP"


class EvidenceStrength(str, Enum):
    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"


def strength_weight(strength: str) -> float:
    return {"E0": 0.0, "E1": 0.10, "E2": 0.25, "E3": 0.55}.get(strength, 0.0)


def cap_strength_for_type(ev_type: str, strength: str) -> str:
    if ev_type == EvidenceType.EV_SELF_ASSERTION.value:
        return EvidenceStrength.E1.value
    return strength


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass
class SkillEvidence:
    skill: str
    evidence_type: str
    strength: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: time.time())

    def is_expired(self, now: Optional[float] = None, window_s: int = 7 * 24 * 3600) -> bool:
        now = now if now is not None else time.time()
        return (now - self.timestamp) > window_s


@dataclass
class TSVSkillBeliefs:
    clarity: float = 0.50
    context: float = 0.50
    verification: float = 0.50
    constraints: float = 0.50
    translation_intent: float = 0.50


@dataclass
class TSVState:
    beliefs: TSVSkillBeliefs = field(default_factory=TSVSkillBeliefs)
    evidence_log: List[SkillEvidence] = field(default_factory=list)
    evidence_window_s: int = 7 * 24 * 3600

    def _decay(self) -> None:
        now = time.time()
        self.evidence_log = [e for e in self.evidence_log if not e.is_expired(now=now, window_s=self.evidence_window_s)]

    def has_e3(self, skill: str) -> bool:
        return any(e.skill == skill and e.strength == EvidenceStrength.E3.value for e in self.evidence_log)

    def add_evidence(self, ev: SkillEvidence) -> None:
        ev.strength = cap_strength_for_type(ev.evidence_type, ev.strength)
        self.evidence_log.append(ev)
        self._decay()

        if ev.evidence_type == EvidenceType.EV_PERFORMANCE.value:
            target = 1.0 if ev.details.get("success") else 0.0
        elif ev.evidence_type == EvidenceType.EV_ERROR_PATTERN.value:
            target = 0.0
        elif ev.evidence_type == EvidenceType.EV_VERIFICATION_STEP.value:
            target = 1.0
        else:
            target = 1.0 if ev.details.get("positive", True) else 0.0

        w = strength_weight(ev.strength)
        current = getattr(self.beliefs, ev.skill, 0.50)
        updated = current + w * (target - current)
        setattr(self.beliefs, ev.skill, clamp01(updated))

    def high_stakes_ready(self) -> bool:
        beliefs_ok = (
            self.beliefs.clarity >= 0.70 and
            self.beliefs.constraints >= 0.70 and
            self.beliefs.verification >= 0.70
        )
        return bool(beliefs_ok and self.has_e3("verification"))

    def snapshot(self) -> Dict[str, Any]:
        self._decay()
        return {
            "beliefs": {
                "clarity": self.beliefs.clarity,
                "context": self.beliefs.context,
                "verification": self.beliefs.verification,
                "constraints": self.beliefs.constraints,
                "translation_intent": self.beliefs.translation_intent,
            },
            "evidence_window_s": self.evidence_window_s,
            "evidence_recent": [
                {
                    "skill": e.skill,
                    "evidence_type": e.evidence_type,
                    "strength": e.strength,
                    "timestamp": e.timestamp,
                    "details": e.details,
                }
                for e in self.evidence_log[-20:]
            ],
            "has_e3_verification": self.has_e3("verification"),
        }
