"""Tests for engine profile escalation/de-escalation.

Covers: escalate on validation failures, escalate on domain shift,
de-escalate on clean streak, boundary clamping.
"""
import pytest

from ecosphere.kernel.engine import _escalate_profile
from ecosphere.kernel.session import Profile, SessionState
from ecosphere.validation.validators import ValidationAttempt


def _sess(profile=Profile.A_STANDARD.value, interaction=5) -> SessionState:
    s = SessionState(session_id="esc-test")
    s.current_profile = profile
    s.interaction_count = interaction
    s.last_failure_interaction = 0
    return s


def _attempts(ok_list: list) -> list:
    return [ValidationAttempt(attempt=i+1, ok=ok, reason="test", score=1.0 if ok else 0.0) for i, ok in enumerate(ok_list)]


# ── Escalation on failures ────────────────────────────────────────

def test_escalate_fast_to_standard_on_failures():
    s = _sess(Profile.A_FAST.value)
    _escalate_profile(s, _attempts([False, False]))
    assert s.current_profile == Profile.A_STANDARD.value


def test_escalate_standard_to_high_on_failures():
    s = _sess(Profile.A_STANDARD.value)
    _escalate_profile(s, _attempts([False, False]))
    assert s.current_profile == Profile.A_HIGH_ASSURANCE.value


def test_no_escalation_above_high():
    s = _sess(Profile.A_HIGH_ASSURANCE.value)
    _escalate_profile(s, _attempts([False, False]))
    assert s.current_profile == Profile.A_HIGH_ASSURANCE.value


def test_escalate_on_domain_shift():
    s = _sess(Profile.A_FAST.value)
    _escalate_profile(s, _attempts([True]), domain_shift=True)
    assert s.current_profile == Profile.A_STANDARD.value


# ── De-escalation on clean streak ─────────────────────────────────

def test_deescalate_high_to_standard_on_clean_streak():
    s = _sess(Profile.A_HIGH_ASSURANCE.value, interaction=20)
    s.last_failure_interaction = 10  # 10 turns of clean streak
    _escalate_profile(s, _attempts([True, True]))
    assert s.current_profile == Profile.A_STANDARD.value


def test_deescalate_standard_to_fast_on_clean_streak():
    s = _sess(Profile.A_STANDARD.value, interaction=20)
    s.last_failure_interaction = 10
    _escalate_profile(s, _attempts([True]))
    assert s.current_profile == Profile.A_FAST.value


def test_no_deescalation_below_fast():
    s = _sess(Profile.A_FAST.value, interaction=20)
    s.last_failure_interaction = 10
    _escalate_profile(s, _attempts([True]))
    assert s.current_profile == Profile.A_FAST.value


def test_no_deescalation_on_short_streak():
    s = _sess(Profile.A_HIGH_ASSURANCE.value, interaction=5)
    s.last_failure_interaction = 2  # only 3 clean turns
    _escalate_profile(s, _attempts([True]))
    assert s.current_profile == Profile.A_HIGH_ASSURANCE.value


# ── Single failure doesn't escalate ───────────────────────────────

def test_single_failure_no_escalation():
    s = _sess(Profile.A_FAST.value)
    _escalate_profile(s, _attempts([False, True]))  # 1 fail < 2 threshold
    assert s.current_profile == Profile.A_FAST.value
