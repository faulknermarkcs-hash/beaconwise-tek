"""Tests for kernel.router.route_aru_sequence.

Covers: BOUND, REFLECT, SCAFFOLD, DEFER, TDM default routing paths.
"""
import pytest

from ecosphere.kernel.router import route_aru_sequence
from ecosphere.kernel.session import SessionState
from ecosphere.kernel.types import DomainTag, InputVector
from ecosphere.utils.stable import stable_hash


def _iv(*, safe=True, s1_ok=True, s2_ok=True, domain=DomainTag.GENERAL,
         complexity=2, requires_reflect=False, requires_scaffold=False,
         text="test"):
    return InputVector(
        user_text=text,
        user_text_hash=stable_hash(text),
        safe_stage1_ok=s1_ok,
        safe_stage1_reason="pass" if s1_ok else "fail",
        safe_stage2_ok=s2_ok,
        safe_stage2_score=0.0 if s2_ok else 0.9,
        safe_stage2_meta={},
        safe=safe,
        domain=domain,
        complexity=complexity,
        requires_reflect=requires_reflect,
        requires_scaffold=requires_scaffold,
    )


def test_route_bound_on_unsafe():
    sess = SessionState(session_id="r1")
    iv = _iv(safe=False)
    seq, why = route_aru_sequence(iv, sess)
    assert seq == ["BOUND"]
    assert why == "safety_fail"


def test_route_reflect_when_required():
    sess = SessionState(session_id="r2")
    iv = _iv(requires_reflect=True)
    seq, why = route_aru_sequence(iv, sess)
    assert seq == ["REFLECT"]
    assert why == "requires_reflect"


def test_route_scaffold_after_reflect():
    sess = SessionState(session_id="r3")
    sess.reflect_confirmed = True
    iv = _iv(requires_reflect=True, requires_scaffold=True)
    seq, why = route_aru_sequence(iv, sess)
    assert seq == ["SCAFFOLD"]
    assert why == "requires_scaffold"


def test_route_tdm_after_both_gates():
    sess = SessionState(session_id="r4")
    sess.reflect_confirmed = True
    sess.scaffold_approved = True
    iv = _iv(requires_reflect=True, requires_scaffold=True)
    seq, why = route_aru_sequence(iv, sess)
    assert seq == ["TDM"]
    assert why == "default"


def test_route_defer_high_stakes_without_readiness():
    sess = SessionState(session_id="r5")
    iv = _iv(domain=DomainTag.HIGH_STAKES)
    seq, why = route_aru_sequence(iv, sess)
    assert seq == ["DEFER"]
    assert why == "high_stakes_gate"


def test_route_tdm_simple():
    sess = SessionState(session_id="r6")
    iv = _iv()
    seq, why = route_aru_sequence(iv, sess)
    assert seq == ["TDM"]
    assert why == "default"


def test_route_reflect_takes_priority_over_defer():
    """When both reflect and high-stakes apply, reflect comes first."""
    sess = SessionState(session_id="r7")
    iv = _iv(requires_reflect=True, domain=DomainTag.HIGH_STAKES)
    seq, why = route_aru_sequence(iv, sess)
    assert seq == ["REFLECT"]


def test_route_bound_takes_priority_over_everything():
    sess = SessionState(session_id="r8")
    iv = _iv(safe=False, requires_reflect=True, domain=DomainTag.HIGH_STAKES)
    seq, why = route_aru_sequence(iv, sess)
    assert seq == ["BOUND"]
