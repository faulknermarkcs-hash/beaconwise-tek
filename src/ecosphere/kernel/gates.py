from __future__ import annotations

import re
from typing import Any, Dict, Tuple

from ecosphere.config import Settings
from ecosphere.kernel.revisions import append_revision, render_revision_block
from ecosphere.kernel.session import PendingGate, Profile, StateTrace
from ecosphere.kernel.session_secret import derive_scoped
from ecosphere.utils.stable import hash_suffix, stable_hash


CONFIRM_YES = re.compile(r"\b(yes|yep|yeah|correct|confirmed|confirm|sounds good|that works)\b", re.I)
CONFIRM_NO = re.compile(r"\b(no|nope|incorrect|not that|revise|change)\b", re.I)

APPROVE_YES = re.compile(r"\b(approve|approved|go ahead|proceed|greenlight|ok to proceed)\b", re.I)
APPROVE_NO = re.compile(r"\b(reject|not approved|don't proceed|revise plan|change plan)\b", re.I)

CONFIRM_TOKEN = re.compile(r"\bconfirm\s+([0-9a-f]{4,10})\b", re.I)
APPROVE_TOKEN = re.compile(r"\bapprove\s+([0-9a-f]{4,10})\b", re.I)

STEP_REF = re.compile(r"\b(step|phase)\s*(\d+)\b", re.I)
REVISION_TRIGGERS = [
    r"\bbut\b",
    r"\bexcept\b",
    r"\bhowever\b",
    r"\bchange\b",
    r"\brevise\b",
    r"\bmodify\b",
    r"\badjust\b",
    r"\binstead\b",
    r"\bswap\b",
    r"\breplace\b",
    r"\badd\b",
    r"\bremove\b",
    r"\bomit\b",
    r"\bstep\s*\d+\b",
    r"\bphase\s*\d+\b",
]


def _timeout_for_profile(profile: str) -> int:
    return {
        Profile.A_FAST.value: 2,
        Profile.A_STANDARD.value: 3,
        Profile.A_HIGH_ASSURANCE.value: 5,
    }.get(profile, 3)


def _token_length_for_profile(profile: str) -> int:
    if profile == Profile.A_FAST.value:
        return int(Settings.TOKENLEN_FAST)
    if profile == Profile.A_HIGH_ASSURANCE.value:
        return int(Settings.TOKENLEN_HIGH)
    return int(Settings.TOKENLEN_STANDARD)


def _require_binding_for_profile(profile: str) -> bool:
    return profile == Profile.A_HIGH_ASSURANCE.value


def make_gate_nonce(session_id: str, interaction: int, gate: str, payload_hash: str, session_scope: str) -> str:
    raw = {"session_id": session_id, "interaction": interaction, "gate": gate, "payload_hash": payload_hash, "session_scope": session_scope}
    return stable_hash(raw)[:10]


def _extract_token(text: str, kind: str) -> str:
    t = text.strip().lower()
    m = (CONFIRM_TOKEN if kind == "confirm" else APPROVE_TOKEN).search(t)
    return m.group(1).lower() if m else ""


def _binding_decision(user_text: str, expected_token: str, require: bool, kind: str) -> Tuple[bool, str, str]:
    t = user_text.strip().lower()

    reject_pattern = CONFIRM_NO if kind == "confirm" else APPROVE_NO
    accept_pattern = CONFIRM_YES if kind == "confirm" else APPROVE_YES

    if reject_pattern.search(t):
        return (False, "rejected", "")

    provided = _extract_token(user_text, kind)
    if provided:
        if provided == expected_token:
            return (True, "bound_ok", provided)
        return (False, "token_mismatch", provided)

    if require:
        if accept_pattern.search(t):
            return (False, "missing_token", "")
        return (False, "unknown", "")

    if accept_pattern.search(t):
        return (True, "unbound_ok", "")

    return (False, "unknown", "")


def _nonce_already_used(sess) -> bool:
    n = sess.pending_gate.nonce or ""
    return bool(n and (n in sess.pending_gate.consumed_nonces))


def _consume_nonce(sess) -> None:
    n = sess.pending_gate.nonce or ""
    if n:
        sess.pending_gate.consumed_nonces.add(n)


def has_revision_intent(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t, re.I) for p in REVISION_TRIGGERS)


def parse_revision(user_text: str) -> Dict[str, Any]:
    m = STEP_REF.search(user_text)
    step_n = int(m.group(2)) if m else None
    cleaned = re.sub(r"^\s*(confirm|approve)\s+[0-9a-f]{4,10}\s*", "", user_text, flags=re.I)
    cleaned = re.sub(r"^\s*(yes|yep|yeah|approved|go ahead|proceed)\b[:,]?\s*", "", cleaned, flags=re.I)
    return {"revision_step": step_n, "revision_text": cleaned.strip()}


def clear_pending(sess, reason: str) -> None:
    sess.pending_gate.gate = PendingGate.NONE.value
    sess.pending_gate.payload = {}
    sess.pending_gate.payload_hash = ""
    sess.pending_gate.confirm_token = ""
    sess.pending_gate.nonce = ""
    sess.pending_gate.require_token_binding = False
    sess.pending_gate.prompt_cache_hash = ""
    if reason == "reset":
        sess.reflect_confirmed = False
        sess.scaffold_approved = False


def trace(sess, before: str, after: str, event: str, meta: Dict[str, Any] | None = None) -> None:
    sess.traces.append(
        StateTrace(
            state_before=before,
            state_after=after,
            event=event,
            gate=sess.pending_gate.gate,
            interaction=sess.interaction_count,
            meta=meta or {},
        )
    )


def _session_scope(sess) -> str:
    secret = getattr(sess, "_session_secret", "")
    return derive_scoped(sess.session_id, secret, "gate_scope") if secret else "noscope"


def set_pending_gate(sess, gate: str, payload: Dict[str, Any]) -> None:
    timeout = _timeout_for_profile(sess.current_profile)
    ph = stable_hash(payload)
    token_len = _token_length_for_profile(sess.current_profile)
    token = hash_suffix(ph, token_len)
    nonce = make_gate_nonce(sess.session_id, sess.interaction_count, gate, ph, _session_scope(sess))
    require = _require_binding_for_profile(sess.current_profile)

    sess.pending_gate.gate = gate
    sess.pending_gate.created_at_interaction = sess.interaction_count
    sess.pending_gate.expires_after_turns = timeout
    sess.pending_gate.payload = payload
    sess.pending_gate.payload_hash = ph
    sess.pending_gate.confirm_token = token
    sess.pending_gate.nonce = nonce
    sess.pending_gate.require_token_binding = require
    sess.pending_gate.prompt_cache_hash = stable_hash({"gate": gate, "payload_hash": ph, "token": token})


def refresh_pending_gate_crypto(sess) -> None:
    gate = sess.pending_gate.gate
    ph = stable_hash(sess.pending_gate.payload)
    token_len = _token_length_for_profile(sess.current_profile)
    token = hash_suffix(ph, token_len)
    nonce = make_gate_nonce(sess.session_id, sess.interaction_count, gate, ph, _session_scope(sess))

    sess.pending_gate.payload_hash = ph
    sess.pending_gate.confirm_token = token
    sess.pending_gate.nonce = nonce
    sess.pending_gate.created_at_interaction = sess.interaction_count
    sess.pending_gate.prompt_cache_hash = stable_hash({"gate": gate, "payload_hash": ph, "token": token})


def render_reflect_prompt(sess, summary: str) -> str:
    token = sess.pending_gate.confirm_token
    rev_block = render_revision_block(sess.pending_gate.payload)
    rev_text = f"\n\n{rev_block}\n" if rev_block else "\n"

    if sess.pending_gate.require_token_binding:
        return (
            "REFLECT (CONFIRMATION REQUIRED)\n"
            f"{summary}{rev_text}\n"
            f"Reply exactly: CONFIRM {token}\n"
            "Or: REVISE <what to change>\n"
        )
    return (
        "REFLECT\n"
        f"{summary}{rev_text}\n"
        f"Optional binding: CONFIRM {token}\n"
        "Or reply 'yes' to confirm, 'no' to revise.\n"
    )


def render_scaffold_prompt(sess, plan: str) -> str:
    token = sess.pending_gate.confirm_token
    rev_block = render_revision_block(sess.pending_gate.payload)
    rev_text = f"\n\n{rev_block}\n" if rev_block else "\n"

    if sess.pending_gate.require_token_binding:
        return (
            "SCAFFOLD (APPROVAL REQUIRED)\n"
            f"{plan}{rev_text}\n"
            f"Reply exactly: APPROVE {token}\n"
            "Or: REVISE <what to change>\n"
        )
    return (
        "SCAFFOLD\n"
        f"{plan}{rev_text}\n"
        f"Optional binding: APPROVE {token}\n"
        "Or reply 'approved' to proceed, 'no' to revise.\n"
    )


def handle_pending_gate(sess, user_text: str) -> Tuple[bool, str, Dict[str, Any]]:
    if not sess.pending_gate.is_active():
        return (False, "", {})

    if sess.pending_gate.is_expired(sess.interaction_count):
        before = sess.pending_gate.gate
        clear_pending(sess, reason="reset")
        trace(sess, before, PendingGate.NONE.value, "pending_timeout", {"expires_after_turns": sess.pending_gate.expires_after_turns})
        return (True, "Timeout on pending gate. Let's start over—what is your goal and constraints?", {"timeout": True})

    if has_revision_intent(user_text):
        rev = parse_revision(user_text)
        old_token = sess.pending_gate.confirm_token
        old_hash = sess.pending_gate.payload_hash
        old_nonce = sess.pending_gate.nonce

        sess.pending_gate.payload = append_revision(sess.pending_gate.payload, rev.get("revision_step"), rev.get("revision_text", ""))
        refresh_pending_gate_crypto(sess)

        trace(
            sess,
            sess.pending_gate.gate,
            sess.pending_gate.gate,
            "revise_in_place_applied",
            {
                "old_token": old_token,
                "new_token": sess.pending_gate.confirm_token,
                "old_payload_hash": old_hash,
                "new_payload_hash": sess.pending_gate.payload_hash,
                "old_nonce": old_nonce,
                "new_nonce": sess.pending_gate.nonce,
                "revision_step": rev.get("revision_step"),
                "revision_text_hash16": stable_hash(rev.get("revision_text", ""))[:16],
            },
        )

        if sess.pending_gate.gate == PendingGate.REFLECT_CONFIRM.value:
            return (True, render_reflect_prompt(sess, "Updated pending request with your revision. Confirm updated intent."), {"revision": True})
        return (True, render_scaffold_prompt(sess, "Updated pending plan with your revision. Approve updated plan."), {"revision": True})

    kind = "confirm" if sess.pending_gate.gate == PendingGate.REFLECT_CONFIRM.value else "approve"
    accepted, status, provided = _binding_decision(user_text, sess.pending_gate.confirm_token, sess.pending_gate.require_token_binding, kind=kind)

    if accepted:
        if _nonce_already_used(sess):
            trace(sess, sess.pending_gate.gate, sess.pending_gate.gate, "replay_detected", {"nonce": sess.pending_gate.nonce, "attempted_token": provided})
            return (True, "That confirmation was already processed (replay detected). If you have a new request, restate it.", {"replay": True})

        _consume_nonce(sess)
        before = sess.pending_gate.gate
        clear_pending(sess, reason="confirmed")
        trace(sess, before, PendingGate.NONE.value, f"{before.lower()}_accepted", {"binding_status": status, "provided_token": provided})

        if before == PendingGate.REFLECT_CONFIRM.value:
            sess.reflect_confirmed = True
            return (False, "", {"gate_cleared": "reflect", "binding_status": status})
        sess.scaffold_approved = True
        return (False, "", {"gate_cleared": "scaffold", "binding_status": status})

    if status == "rejected":
        before = sess.pending_gate.gate
        clear_pending(sess, reason="reset")
        trace(sess, before, PendingGate.NONE.value, "gate_rejected", {"kind": kind})
        return (True, "Okay—tell me what you want instead (goal + constraints + output format).", {"rejected": True})

    if status == "token_mismatch":
        trace(sess, sess.pending_gate.gate, sess.pending_gate.gate, "token_mismatch", {"provided": provided, "expected": sess.pending_gate.confirm_token})
        if sess.pending_gate.gate == PendingGate.REFLECT_CONFIRM.value:
            return (True, f"Token mismatch. Please reply: CONFIRM {sess.pending_gate.confirm_token}", {"mismatch": True})
        return (True, f"Token mismatch. Please reply: APPROVE {sess.pending_gate.confirm_token}", {"mismatch": True})

    if status == "missing_token":
        trace(sess, sess.pending_gate.gate, sess.pending_gate.gate, "missing_token", {"expected": sess.pending_gate.confirm_token})
        if sess.pending_gate.gate == PendingGate.REFLECT_CONFIRM.value:
            return (True, f"I need explicit confirmation. Reply: CONFIRM {sess.pending_gate.confirm_token}", {"missing_token": True})
        return (True, f"I need explicit approval. Reply: APPROVE {sess.pending_gate.confirm_token}", {"missing_token": True})

    trace(sess, sess.pending_gate.gate, sess.pending_gate.gate, "unclear_gate_response", {"kind": kind})
    if sess.pending_gate.gate == PendingGate.REFLECT_CONFIRM.value:
        return (True, render_reflect_prompt(sess, "Please confirm if this matches your intent."), {"unknown": True})
    return (True, render_scaffold_prompt(sess, "Please approve if this plan is correct."), {"unknown": True})
