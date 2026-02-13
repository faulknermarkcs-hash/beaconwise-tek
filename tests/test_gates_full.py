"""Tests for kernel.gates — full pending gate lifecycle.

Covers: set_pending_gate, handle_pending_gate (confirm, reject, timeout,
token mismatch, missing token, revision, replay detection, nonce consumption).
"""
import pytest

from ecosphere.kernel.gates import (
    clear_pending,
    handle_pending_gate,
    has_revision_intent,
    parse_revision,
    set_pending_gate,
)
from ecosphere.kernel.session import PendingGate, Profile, SessionState


def _sess(profile=Profile.A_STANDARD.value) -> SessionState:
    s = SessionState(session_id="gate-test")
    s.interaction_count = 1
    s.current_profile = profile
    return s


def _with_reflect_gate(profile=Profile.A_STANDARD.value) -> SessionState:
    s = _sess(profile)
    set_pending_gate(s, PendingGate.REFLECT_CONFIRM.value, {"x": 1})
    return s


def _with_scaffold_gate(profile=Profile.A_STANDARD.value) -> SessionState:
    s = _sess(profile)
    set_pending_gate(s, PendingGate.SCAFFOLD_APPROVE.value, {"plan": "test"})
    return s


# ── set_pending_gate basics ───────────────────────────────────────

def test_set_pending_gate_populates_fields():
    s = _sess()
    set_pending_gate(s, PendingGate.REFLECT_CONFIRM.value, {"x": 1})
    pg = s.pending_gate
    assert pg.gate == PendingGate.REFLECT_CONFIRM.value
    assert pg.is_active()
    assert pg.confirm_token
    assert pg.nonce
    assert pg.payload_hash
    assert pg.prompt_cache_hash


def test_set_pending_gate_token_binding_for_high_assurance():
    s = _sess(Profile.A_HIGH_ASSURANCE.value)
    set_pending_gate(s, PendingGate.REFLECT_CONFIRM.value, {"x": 1})
    assert s.pending_gate.require_token_binding is True


def test_set_pending_gate_no_binding_for_fast():
    s = _sess(Profile.A_FAST.value)
    set_pending_gate(s, PendingGate.REFLECT_CONFIRM.value, {"x": 1})
    assert s.pending_gate.require_token_binding is False


# ── handle_pending_gate: confirm (yes) ────────────────────────────

def test_confirm_with_yes():
    s = _with_reflect_gate()
    handled, text, meta = handle_pending_gate(s, "yes")
    assert handled is False  # gate cleared, no UI text
    assert meta.get("gate_cleared") == "reflect"
    assert s.reflect_confirmed is True
    assert not s.pending_gate.is_active()


def test_approve_with_go_ahead():
    s = _with_scaffold_gate()
    handled, text, meta = handle_pending_gate(s, "go ahead")
    assert handled is False
    assert meta.get("gate_cleared") == "scaffold"
    assert s.scaffold_approved is True


# ── handle_pending_gate: confirm with token binding ───────────────

def test_confirm_with_correct_token():
    s = _with_reflect_gate()
    token = s.pending_gate.confirm_token
    handled, text, meta = handle_pending_gate(s, f"confirm {token}")
    assert handled is False
    assert meta.get("gate_cleared") == "reflect"
    assert meta.get("binding_status") == "bound_ok"


def test_approve_with_correct_token():
    s = _with_scaffold_gate()
    token = s.pending_gate.confirm_token
    handled, text, meta = handle_pending_gate(s, f"approve {token}")
    assert handled is False
    assert meta.get("gate_cleared") == "scaffold"


# ── handle_pending_gate: reject ───────────────────────────────────

def test_confirm_rejected():
    s = _with_reflect_gate()
    handled, text, meta = handle_pending_gate(s, "no")
    assert handled is True
    assert "instead" in text.lower() or "want" in text.lower()
    assert meta.get("rejected") is True
    assert not s.pending_gate.is_active()
    assert s.reflect_confirmed is False


def test_approve_rejected():
    s = _with_scaffold_gate()
    handled, text, meta = handle_pending_gate(s, "not approved")
    assert handled is True
    assert meta.get("rejected") is True


# ── handle_pending_gate: token mismatch ───────────────────────────

def test_token_mismatch_reflect():
    s = _with_reflect_gate()
    handled, text, meta = handle_pending_gate(s, "confirm deadbeef")
    assert handled is True
    assert "mismatch" in text.lower()
    assert meta.get("mismatch") is True
    assert s.pending_gate.is_active()  # stays active


def test_token_mismatch_scaffold():
    s = _with_scaffold_gate()
    handled, text, meta = handle_pending_gate(s, "approve deadbeef")
    assert handled is True
    assert "mismatch" in text.lower()


# ── handle_pending_gate: missing token (high assurance) ───────────

def test_missing_token_high_assurance():
    s = _with_reflect_gate(Profile.A_HIGH_ASSURANCE.value)
    # "yes" without token when binding required
    handled, text, meta = handle_pending_gate(s, "yes")
    assert handled is True
    assert meta.get("missing_token") is True
    assert "CONFIRM" in text


# ── handle_pending_gate: timeout ──────────────────────────────────

def test_gate_timeout():
    s = _with_reflect_gate()
    # Fast-forward interaction count past expiry
    s.interaction_count = s.pending_gate.created_at_interaction + s.pending_gate.expires_after_turns + 1
    handled, text, meta = handle_pending_gate(s, "yes")
    assert handled is True
    assert "timeout" in text.lower() or meta.get("timeout") is True


# ── handle_pending_gate: replay detection ─────────────────────────

def test_replay_detection():
    s = _with_reflect_gate()
    token = s.pending_gate.confirm_token

    # First confirm succeeds
    handled1, _, meta1 = handle_pending_gate(s, f"confirm {token}")
    assert meta1.get("gate_cleared") == "reflect"

    # Re-set the gate with same payload to simulate replay
    set_pending_gate(s, PendingGate.REFLECT_CONFIRM.value, {"x": 1})
    # Manually mark the nonce as consumed
    s.pending_gate.consumed_nonces.add(s.pending_gate.nonce)

    token2 = s.pending_gate.confirm_token
    handled2, text2, meta2 = handle_pending_gate(s, f"confirm {token2}")
    assert handled2 is True
    assert meta2.get("replay") is True


# ── handle_pending_gate: no active gate ───────────────────────────

def test_no_pending_gate():
    s = _sess()
    handled, text, meta = handle_pending_gate(s, "yes")
    assert handled is False
    assert text == ""


# ── handle_pending_gate: unclear response ─────────────────────────

def test_unclear_response_reflect():
    s = _with_reflect_gate()
    handled, text, meta = handle_pending_gate(s, "maybe later idk")
    assert handled is True
    assert meta.get("unknown") is True
    assert s.pending_gate.is_active()


# ── Revision detection and parsing ────────────────────────────────

def test_has_revision_intent_positive():
    assert has_revision_intent("yes but change step 2")
    assert has_revision_intent("revise the approach")
    assert has_revision_intent("add more detail")


def test_has_revision_intent_negative():
    assert not has_revision_intent("yes confirmed")
    assert not has_revision_intent("looks good")


def test_parse_revision_with_step():
    r = parse_revision("yes but change step 3 to use async")
    assert r["revision_step"] == 3
    assert "async" in r["revision_text"]


def test_parse_revision_without_step():
    r = parse_revision("but add error handling")
    assert r["revision_step"] is None
    assert "error handling" in r["revision_text"]


# ── Revision in-place during pending gate ─────────────────────────

def test_revision_in_place_updates_crypto():
    s = _with_reflect_gate()
    old_token = s.pending_gate.confirm_token
    old_hash = s.pending_gate.payload_hash

    handled, text, meta = handle_pending_gate(s, "yes but change step 2 to use async")
    assert handled is True
    assert meta.get("revision") is True
    assert s.pending_gate.confirm_token != old_token
    assert s.pending_gate.payload_hash != old_hash
    assert s.pending_gate.is_active()  # gate stays open
    assert "revision_history" in s.pending_gate.payload


# ── clear_pending ─────────────────────────────────────────────────

def test_clear_pending_resets_state():
    s = _with_reflect_gate()
    clear_pending(s, "reset")
    assert not s.pending_gate.is_active()
    assert s.reflect_confirmed is False
    assert s.scaffold_approved is False
