from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Stage1Result:
    ok: bool
    reason: str


BAD = [
    r"\bignore previous instructions\b",
    r"\breveal system prompt\b",
    r"\bhow to make a bomb\b",
    r"\bkill myself\b",
]


def stage1(text: str) -> Stage1Result:
    t = text.lower()
    for p in BAD:
        if re.search(p, t):
            return Stage1Result(False, f"matched:{p}")
    return Stage1Result(True, "pass")
