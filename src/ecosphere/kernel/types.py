from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class DomainTag(str, Enum):
    GENERAL = "GENERAL"
    TECHNICAL = "TECHNICAL"
    HIGH_STAKES = "HIGH_STAKES"


@dataclass(frozen=True)
class InputVector:
    user_text: str
    user_text_hash: str

    safe_stage1_ok: bool
    safe_stage1_reason: str

    safe_stage2_ok: bool
    safe_stage2_score: float
    safe_stage2_meta: Dict[str, Any]

    safe: bool

    domain: DomainTag
    complexity: int
    requires_reflect: bool
    requires_scaffold: bool
