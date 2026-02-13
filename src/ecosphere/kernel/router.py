from __future__ import annotations

from typing import List, Tuple

from ecosphere.kernel.session import SessionState
from ecosphere.kernel.types import DomainTag, InputVector


def route_aru_sequence(iv: InputVector, sess: SessionState) -> Tuple[List[str], str]:
    if not iv.safe:
        return (["BOUND"], "safety_fail")

    if iv.requires_reflect and not sess.reflect_confirmed:
        return (["REFLECT"], "requires_reflect")

    if iv.requires_scaffold and sess.reflect_confirmed and not sess.scaffold_approved:
        return (["SCAFFOLD"], "requires_scaffold")

    if iv.domain == DomainTag.HIGH_STAKES and not sess.tsv.high_stakes_ready():
        return (["DEFER"], "high_stakes_gate")

    return (["TDM"], "default")
