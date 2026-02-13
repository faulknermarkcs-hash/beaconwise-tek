"""Tests for tsv.state — Bayesian belief tracking, evidence lifecycle.

Covers: belief updates, strength capping, time decay, high_stakes_ready(),
snapshot, evidence types.
"""
import time

import pytest

from ecosphere.tsv.state import (
    EvidenceStrength,
    EvidenceType,
    SkillEvidence,
    TSVSkillBeliefs,
    TSVState,
    cap_strength_for_type,
    clamp01,
    strength_weight,
)


# ── Utility functions ─────────────────────────────────────────────

def test_clamp01():
    assert clamp01(-0.5) == 0.0
    assert clamp01(0.5) == 0.5
    assert clamp01(1.5) == 1.0


def test_strength_weight():
    assert strength_weight("E0") == 0.0
    assert strength_weight("E1") == 0.10
    assert strength_weight("E2") == 0.25
    assert strength_weight("E3") == 0.55
    assert strength_weight("INVALID") == 0.0


def test_cap_strength_self_assertion():
    """Self-assertions are capped at E1 regardless of input."""
    assert cap_strength_for_type(EvidenceType.EV_SELF_ASSERTION.value, "E3") == "E1"
    assert cap_strength_for_type(EvidenceType.EV_SELF_ASSERTION.value, "E2") == "E1"


def test_cap_strength_other_types():
    assert cap_strength_for_type(EvidenceType.EV_PERFORMANCE.value, "E3") == "E3"
    assert cap_strength_for_type(EvidenceType.EV_VERIFICATION_STEP.value, "E2") == "E2"


# ── TSVSkillBeliefs defaults ──────────────────────────────────────

def test_beliefs_default_to_half():
    b = TSVSkillBeliefs()
    assert b.clarity == 0.50
    assert b.context == 0.50
    assert b.verification == 0.50
    assert b.constraints == 0.50
    assert b.translation_intent == 0.50


# ── SkillEvidence expiry ──────────────────────────────────────────

def test_evidence_not_expired():
    ev = SkillEvidence(
        skill="clarity",
        evidence_type=EvidenceType.EV_PERFORMANCE.value,
        strength="E2",
        timestamp=time.time(),
    )
    assert ev.is_expired() is False


def test_evidence_expired():
    ev = SkillEvidence(
        skill="clarity",
        evidence_type=EvidenceType.EV_PERFORMANCE.value,
        strength="E2",
        timestamp=time.time() - (8 * 24 * 3600),  # 8 days ago, window is 7
    )
    assert ev.is_expired() is True


# ── TSVState.add_evidence — belief updates ────────────────────────

def test_add_positive_performance_evidence_increases_belief():
    state = TSVState()
    initial = state.beliefs.clarity
    ev = SkillEvidence(
        skill="clarity",
        evidence_type=EvidenceType.EV_PERFORMANCE.value,
        strength="E3",
        details={"success": True},
    )
    state.add_evidence(ev)
    assert state.beliefs.clarity > initial


def test_add_negative_performance_evidence_decreases_belief():
    state = TSVState()
    initial = state.beliefs.clarity
    ev = SkillEvidence(
        skill="clarity",
        evidence_type=EvidenceType.EV_PERFORMANCE.value,
        strength="E3",
        details={"success": False},
    )
    state.add_evidence(ev)
    assert state.beliefs.clarity < initial


def test_add_error_pattern_decreases_belief():
    state = TSVState()
    initial = state.beliefs.constraints
    ev = SkillEvidence(
        skill="constraints",
        evidence_type=EvidenceType.EV_ERROR_PATTERN.value,
        strength="E2",
    )
    state.add_evidence(ev)
    assert state.beliefs.constraints < initial


def test_add_verification_step_increases_belief():
    state = TSVState()
    initial = state.beliefs.verification
    ev = SkillEvidence(
        skill="verification",
        evidence_type=EvidenceType.EV_VERIFICATION_STEP.value,
        strength="E3",
    )
    state.add_evidence(ev)
    assert state.beliefs.verification > initial


def test_self_assertion_capped_at_e1():
    """Self-assertions should have minimal impact due to E1 cap."""
    state = TSVState()
    initial = state.beliefs.clarity
    ev = SkillEvidence(
        skill="clarity",
        evidence_type=EvidenceType.EV_SELF_ASSERTION.value,
        strength="E3",  # will be capped to E1
        details={"positive": True},
    )
    state.add_evidence(ev)
    # Should increase but only by E1 weight (0.10)
    delta = state.beliefs.clarity - initial
    assert 0 < delta < 0.15  # E1 weight * (1.0 - 0.50) ≈ 0.05


def test_belief_stays_in_bounds():
    state = TSVState()
    # Push belief to extreme
    for _ in range(50):
        ev = SkillEvidence(
            skill="clarity",
            evidence_type=EvidenceType.EV_PERFORMANCE.value,
            strength="E3",
            details={"success": True},
        )
        state.add_evidence(ev)
    assert 0.0 <= state.beliefs.clarity <= 1.0


# ── TSVState.high_stakes_ready ────────────────────────────────────

def test_high_stakes_not_ready_by_default():
    state = TSVState()
    assert state.high_stakes_ready() is False


def test_high_stakes_ready_requires_e3_verification():
    state = TSVState()
    state.beliefs.clarity = 0.80
    state.beliefs.constraints = 0.80
    state.beliefs.verification = 0.80
    # Beliefs are high but no E3 verification evidence
    assert state.high_stakes_ready() is False


def test_high_stakes_ready_requires_belief_thresholds():
    state = TSVState()
    # Add E3 verification evidence but beliefs are default (0.50)
    ev = SkillEvidence(
        skill="verification",
        evidence_type=EvidenceType.EV_VERIFICATION_STEP.value,
        strength="E3",
    )
    state.add_evidence(ev)
    assert state.high_stakes_ready() is False  # beliefs too low


def test_high_stakes_ready_when_fully_satisfied():
    state = TSVState()
    state.beliefs.clarity = 0.80
    state.beliefs.constraints = 0.80
    state.beliefs.verification = 0.80
    ev = SkillEvidence(
        skill="verification",
        evidence_type=EvidenceType.EV_VERIFICATION_STEP.value,
        strength="E3",
    )
    state.add_evidence(ev)
    assert state.high_stakes_ready() is True


# ── TSVState.has_e3 ───────────────────────────────────────────────

def test_has_e3_false_by_default():
    state = TSVState()
    assert state.has_e3("verification") is False


def test_has_e3_true_after_e3_evidence():
    state = TSVState()
    ev = SkillEvidence(
        skill="verification",
        evidence_type=EvidenceType.EV_VERIFICATION_STEP.value,
        strength="E3",
    )
    state.add_evidence(ev)
    assert state.has_e3("verification") is True
    assert state.has_e3("clarity") is False  # different skill


# ── TSVState.snapshot ─────────────────────────────────────────────

def test_snapshot_structure():
    state = TSVState()
    ev = SkillEvidence(
        skill="clarity",
        evidence_type=EvidenceType.EV_PERFORMANCE.value,
        strength="E2",
        details={"success": True},
    )
    state.add_evidence(ev)
    snap = state.snapshot()
    assert "beliefs" in snap
    assert "evidence_window_s" in snap
    assert "evidence_recent" in snap
    assert "has_e3_verification" in snap
    assert len(snap["evidence_recent"]) == 1


# ── Time decay ────────────────────────────────────────────────────

def test_decay_removes_old_evidence():
    state = TSVState()
    old_ev = SkillEvidence(
        skill="verification",
        evidence_type=EvidenceType.EV_VERIFICATION_STEP.value,
        strength="E3",
        timestamp=time.time() - (8 * 24 * 3600),  # 8 days old
    )
    state.evidence_log.append(old_ev)
    assert state.has_e3("verification") is True  # before decay

    # Adding new evidence triggers decay
    new_ev = SkillEvidence(
        skill="clarity",
        evidence_type=EvidenceType.EV_PERFORMANCE.value,
        strength="E1",
        details={"success": True},
    )
    state.add_evidence(new_ev)
    assert state.has_e3("verification") is False  # old evidence decayed
