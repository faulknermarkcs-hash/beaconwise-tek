from __future__ import annotations

import os
import asyncio
from functools import lru_cache
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from ecosphere.config import Settings
from ecosphere.embeddings.factory import make_embedder
from ecosphere.epack.chain import new_epack
from ecosphere.decision.object import build_decision_object
from ecosphere.kernel.gates import (
    PendingGate,
    handle_pending_gate,
    render_reflect_prompt,
    render_scaffold_prompt,
    set_pending_gate,
    trace,
)
from ecosphere.kernel.provenance import current_manifest
from ecosphere.kernel.router import route_aru_sequence
from ecosphere.kernel.session import Profile, SessionState
from ecosphere.kernel.session_secret import new_session_secret
from ecosphere.kernel.tools import call_tool
from ecosphere.kernel.types import DomainTag, InputVector
from ecosphere.providers.base import GenerationConfig
from ecosphere.providers.factory import make_llm_provider
from ecosphere.safety.embedding_stage2 import EmbeddingStage2Safety

# V9 runtime-loop imports (lazy — only used when BW_KERNEL_MODE=v9)
from ecosphere.meta_validation.policy_compiler import compile_resilience_policy, CompiledResilience
from ecosphere.meta_validation.resilience_runtime import ResilienceRuntime, TrustSnapshot
from ecosphere.safety.stage1 import stage1
from ecosphere.security.redaction import redact_payload
from ecosphere.storage.store import append_jsonl
from ecosphere.utils.stable import stable_hash
from ecosphere.validation.validators import ValidationAttempt, validate_output
from ecosphere.tools.citations import verify_citations, VerificationEvent


# ---------------------------
# TDM output post-processing (deterministic)
# ---------------------------

def _postprocess_tdm_json(raw: str) -> str:
    """Deterministic, audit-safe normalization of PR6 JSON output.

    - Appends the standard Citation Integrity Notice when citations are present.
    - Never adds new keys; modifies only obj['text'].
    """
    import json

    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return raw

        citations = obj.get("citations")
        has_citations = isinstance(citations, list) and len(citations) > 0
        if has_citations and Settings.AUTO_APPEND_CITATION_NOTICE:
            notice = (
                "Citations reflect representative evidence and may not be exhaustive. "
                "Independent verification is recommended for critical decisions."
            )
            txt = obj.get("text") if isinstance(obj.get("text"), str) else ""
            if notice not in txt:
                obj["text"] = txt.rstrip() + "\n\nCitation Integrity Notice: " + notice
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return raw


# ---------------------------
# Profile helpers
# ---------------------------

def _verify_citations_in_tdm_json(raw: str) -> tuple[str, list[dict], list[dict]]:
    """
    Attempts to verify citations (Crossref/PubMed) and upgrade verification_status to verified_reference.

    Returns: (patched_raw_json, events_as_dicts)

    NOTE: This uses public APIs and can change over time. Callers should ensure EPACK includes
    timestamps/hashes if strict replay is required.
    """
    import json
    from ecosphere.config import Settings

    events_out: list[dict] = []
    cache_updates_out: list[dict] = []
    if not Settings.CITATION_VERIFY:
        return raw, events_out, cache_updates_out

    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return raw, events_out, cache_updates_out

        citations = obj.get("citations")
        if not (isinstance(citations, list) and citations):
            return raw, events_out, cache_updates_out

        patched, events, cache_updates = verify_citations(
            citations,
            epack_store_path=Settings.EPACK_STORE_PATH,
            max_to_verify=Settings.CITATION_VERIFY_MAX,
            timeout_s=Settings.CITATION_VERIFY_TIMEOUT_S,
        )
        obj["citations"] = patched
        if isinstance(cache_updates, list):
            cache_updates_out = cache_updates

        # Convert dataclass events to dicts for EPACK friendliness
        for ev in events:
            if hasattr(ev, "__dict__"):
                events_out.append(ev.__dict__)
            else:
                events_out.append(dict(ev))

        # Deterministic-ish JSON dump
        patched_raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        return patched_raw, events_out, cache_updates_out
    except Exception:
        return raw, events_out, cache_updates_out


def _profile_alignment_threshold(profile: str) -> float:
    if profile == Profile.A_FAST.value:
        return Settings.ALIGN_FAST
    if profile == Profile.A_HIGH_ASSURANCE.value:
        return Settings.ALIGN_HIGH
    return Settings.ALIGN_STANDARD


def _max_retries_for_profile(profile: str) -> int:
    return {
        Profile.A_FAST.value: 1,
        Profile.A_STANDARD.value: 2,
        Profile.A_HIGH_ASSURANCE.value: 3,
    }.get(profile, 2)


def _estimate_complexity(text: str) -> int:
    n = len(text.split())
    if n <= 8:
        return 2
    if n <= 25:
        return 4
    if n <= 60:
        return 6
    return 8


def _detect_domain(text: str) -> DomainTag:
    t = text.lower()
    if any(k in t for k in ["dosage", "legal advice", "suicide", "harm myself", "insulin"]):
        return DomainTag.HIGH_STAKES
    if any(k in t for k in ["architecture", "database", "api", "kubernetes", "python", "code"]):
        return DomainTag.TECHNICAL
    return DomainTag.GENERAL


# ---------------------------
# Input vector build
# ---------------------------

def _build_input_vector(user_text: str) -> InputVector:
    s1 = stage1(user_text)

    embedder = make_embedder()
    s2_engine = EmbeddingStage2Safety(
        embedder=embedder,
        model=Settings.EMBEDDINGS_MODEL,
        threshold=Settings.STAGE2_THRESHOLD,
    )
    s2 = s2_engine.score(user_text)

    safe = bool(s1.ok and s2.ok)

    domain = _detect_domain(user_text)
    complexity = _estimate_complexity(user_text)

    requires_reflect = complexity >= 6
    requires_scaffold = complexity >= 7

    return InputVector(
        user_text=user_text,
        safe_stage1_ok=s1.ok,
        safe_stage1_reason=s1.reason,
        safe_stage2_ok=s2.ok,
        safe_stage2_score=float(s2.score),
        safe_stage2_meta=s2_engine.meta(s2),
        safe=safe,
        domain=domain,
        complexity=complexity,
        requires_reflect=requires_reflect,
        requires_scaffold=requires_scaffold,
        user_text_hash=stable_hash(user_text),
    )


# ---------------------------
# TDM prompt (PR6 strict JSON)
# ---------------------------

def _prompt_for_tdm(user_text: str) -> str:
    # PR6 strict JSON + BeaconWise citation governance
    return f"""You are the Transparency Ecosphere Kernel.

Output rules (STRICT):
- Output MUST be valid JSON object.
- Allowed keys only: text, disclosure, citations, assumptions.
- Do not output any extra keys.
- Do not include any text outside the JSON.

Citation rules (BeaconWise):
- If you reference studies, research, guidelines, trials, reviews, or meta-analyses, you MUST include at least 1 citation object in citations.
- Each citation object MUST use only these fields:
  Required: title, authors_or_org, year, source_type, evidence_strength, verification_status
  Optional: identifier, notes
- year must be an integer year or the string 'unknown'.
- source_type must be one of: randomized_trial, meta_analysis, systematic_review, clinical_guideline, observational_study, technical_standard, institutional_report, textbook_reference, general_background
- evidence_strength must be one of: strong_consensus, moderate_evidence, emerging_evidence, contested, contextual_reference
- verification_status must be one of: verified_reference, probable_reference, unverified_model_recall, citation_not_retrieved
- If you cannot retrieve a specific source, set verification_status='citation_not_retrieved' and state that limitation in disclosure.
- Do NOT invent journal names, DOIs, or authors.

Safety rules:
- If safety is at risk, refuse and redirect.

USER:
{user_text}
"""


# ---------------------------
# Profile escalation / de-escalation (PR6)
# ---------------------------

def _escalate_profile(sess: SessionState, validation_attempts: List[ValidationAttempt], domain_shift: bool = False) -> None:
    fails = sum(1 for a in validation_attempts if not a.ok)

    if fails > 0:
        setattr(sess, "last_failure_interaction", sess.interaction_count)

    last_fail = int(getattr(sess, "last_failure_interaction", 0))
    clean_streak = sess.interaction_count - last_fail

    if fails >= 2 or domain_shift:
        if sess.current_profile == Profile.A_FAST.value:
            sess.current_profile = Profile.A_STANDARD.value
        elif sess.current_profile == Profile.A_STANDARD.value:
            sess.current_profile = Profile.A_HIGH_ASSURANCE.value
        trace(sess, "PROFILE", "PROFILE", "profile_up", {"fails": fails, "domain_shift": domain_shift})

    elif clean_streak >= 8 and sess.current_profile != Profile.A_FAST.value:
        if sess.current_profile == Profile.A_HIGH_ASSURANCE.value:
            sess.current_profile = Profile.A_STANDARD.value
        elif sess.current_profile == Profile.A_STANDARD.value:
            sess.current_profile = Profile.A_FAST.value
        trace(sess, "PROFILE", "PROFILE", "profile_down", {"clean_streak": clean_streak})


# ---------------------------
# Tool routing
# ---------------------------

def _tool_search(query: str) -> Tuple[str, Dict[str, Any]]:
    """
    Prefer Brave; fallback to Serper. Both return structured dicts.
    """
    tool_records: List[Dict[str, Any]] = []

    # 1) brave_search
    tr1 = call_tool("brave_search", {"q": query, "count": 5})
    tool_records.append({"tool": tr1.tool, "ok": tr1.ok, "args_hash": tr1.args_hash, "output": tr1.output})

    if tr1.ok and tr1.output.get("ok") is True:
        results = tr1.output.get("results", [])
        lines = ["SEARCH (brave):"]
        for i, r in enumerate(results[:5], start=1):
            lines.append(f"{i}. {r.get('title','').strip()} — {r.get('url','').strip()}")
            snip = (r.get("snippet") or "").strip()
            if snip:
                lines.append(f"   {snip}")
        return ("\n".join(lines), {"provider": "tool_sandbox", "tool_records": tool_records})

    # 2) serper_search fallback
    tr2 = call_tool("serper_search", {"q": query, "num": 5})
    tool_records.append({"tool": tr2.tool, "ok": tr2.ok, "args_hash": tr2.args_hash, "output": tr2.output})

    if tr2.ok and tr2.output.get("ok") is True:
        results = tr2.output.get("results", [])
        lines = ["SEARCH (serper):"]
        for i, r in enumerate(results[:5], start=1):
            lines.append(f"{i}. {r.get('title','').strip()} — {r.get('url','').strip()}")
            snip = (r.get("snippet") or "").strip()
            if snip:
                lines.append(f"   {snip}")
        return ("\n".join(lines), {"provider": "tool_sandbox", "tool_records": tool_records})

    return ("CLARIFY: search tool failed (missing keys or network error).", {"provider": "tool_sandbox", "tool_records": tool_records})


# ---------------------------
# TDM execution (PR6 retry loop)
# ---------------------------

def _execute_tdm(sess: SessionState, iv: InputVector) -> Tuple[str, Dict[str, Any]]:
    provider = make_llm_provider()
    cfg = GenerationConfig(model=Settings.MODEL, temperature=0.0, max_tokens=900)

    # Tool sandbox: calc
    if iv.user_text.strip().lower().startswith("calc:"):
        expr = iv.user_text.split(":", 1)[1].strip()
        tr = call_tool("safe_calc", {"expr": expr})
        meta = {"provider": "tool_sandbox", "tool_records": [{"tool": tr.tool, "ok": tr.ok, "args_hash": tr.args_hash, "output": tr.output}]}
        if tr.ok:
            return (f"{tr.output.get('value')}", meta)
        return ("CLARIFY: invalid calc expression.", meta)

    # Tool sandbox: search
    if iv.user_text.strip().lower().startswith("search:"):
        q = iv.user_text.split(":", 1)[1].strip()
        return _tool_search(q)

    thr = _profile_alignment_threshold(sess.current_profile)
    max_retries = _max_retries_for_profile(sess.current_profile)

    prompt = _prompt_for_tdm(iv.user_text)
    all_attempts: List[ValidationAttempt] = []
    chosen_text = ""
    chosen_meta: Dict[str, Any] = {}

    for attempt in range(1, max_retries + 1):
        gen = provider.generate(prompt, cfg)
        val_attempts = validate_output(iv.user_text, gen.text, threshold=thr)
        all_attempts.extend(val_attempts)

        ok = all(a.ok for a in val_attempts)
        if ok:
            patched_json, citation_verify_events, citation_cache_updates = _verify_citations_in_tdm_json(gen.text)
            chosen_text = _postprocess_tdm_json(patched_json)
            chosen_meta = {
                "provider": gen.provider,
                "model": gen.model,
                "usage": gen.usage,
                "attempt": attempt,
                "citation_verification": citation_verify_events,
                "citation_cache_updates": citation_cache_updates,
                "validation": [asdict(a) for a in val_attempts],
                "validation_ok": True,
                "align_threshold": thr,
            }
            break

        # Harden prompt on failure
        prompt += (
            "\n\nPrevious output failed validation.\n"
            "Retry rules:\n"
            "- Output MUST be valid JSON.\n"
            "- Only keys: text, disclosure, citations, assumptions.\n"
            "- No extra keys.\n"
            "- No text outside JSON.\n"
        )

    if not chosen_text:
        chosen_text = "CLARIFY: Output validation failed after retries. Provide goal + constraints + output format in 1–3 bullets."
        chosen_meta = {
            "provider": "validation_fail_closed",
            "attempts": max_retries,
            "validation_ok": False,
            "align_threshold": thr,
            "validation": [asdict(a) for a in all_attempts],
        }

    _escalate_profile(sess, all_attempts, domain_shift=False)
    return chosen_text, chosen_meta


# ---------------------------
# Session secret
# ---------------------------

def _ensure_session_secret(sess: SessionState) -> None:
    if not getattr(sess, "_session_secret", ""):
        setattr(sess, "_session_secret", new_session_secret())


# ---------------------------
# Workflow queue hooks
# ---------------------------

def notify_reflect_confirmed_hook(sess: SessionState, iv: InputVector) -> None:
    if iv.requires_scaffold and not sess.scaffold_approved:
        sess.workflow_queue = ["SCAFFOLD"]
    else:
        sess.workflow_queue = ["TDM"]


def notify_scaffold_approved_hook(sess: SessionState) -> None:
    sess.workflow_queue = ["TDM"]


# ---------------------------
# Main turn handler
# ---------------------------

def handle_turn(sess: SessionState, user_text: str) -> Dict[str, Any]:
    _ensure_session_secret(sess)
    sess.interaction_count += 1

    handled, gate_text, gate_meta = handle_pending_gate(sess, user_text)
    if handled:
        return _seal(sess, user_text, assistant_text=gate_text, extra={"gate_meta": gate_meta})

    # if gate cleared, chain into workflow queue deterministically
    if gate_meta.get("gate_cleared") == "reflect":
        iv0 = _build_input_vector(user_text)
        notify_reflect_confirmed_hook(sess, iv0)
    elif gate_meta.get("gate_cleared") == "scaffold":
        notify_scaffold_approved_hook(sess)

    iv = _build_input_vector(user_text)

    # ----------------------------
    # V9 fast path: full runtime loop
    # ----------------------------
    if os.getenv("BW_KERNEL_MODE", "v8").lower() == "v9":
        out, meta = _execute_v9_runtime(sess, user_text, iv)
        return _seal(sess, user_text, out, extra={"v9": True, "iv": asdict(iv), "v9_meta": meta})

    # workflow queue step
    if sess.workflow_queue:
        next_aru = sess.workflow_queue.pop(0)
        trace(sess, "QUEUE", "QUEUE", "workflow_step_dequeued", {"next": next_aru})

        if next_aru == "SCAFFOLD":
            payload = {
                "user_text_hash": iv.user_text_hash,
                "domain": iv.domain.value,
                "complexity": iv.complexity,
                "plan_stub": True,
                "workflow": "chained",
            }
            set_pending_gate(sess, PendingGate.SCAFFOLD_APPROVE.value, payload)
            trace(sess, PendingGate.NONE.value, PendingGate.SCAFFOLD_APPROVE.value, "enter_scaffold_pending_chained", {"token": sess.pending_gate.confirm_token})

            plan = (
                "Plan:\n"
                "1) Confirm requirements and constraints\n"
                "2) Propose architecture / approach\n"
                "3) Provide implementation steps\n"
                "4) Provide test + validation checklist\n"
            )
            return _seal(sess, user_text, render_scaffold_prompt(sess, plan), extra={"workflow": "chained", "iv": asdict(iv)})

        if next_aru == "TDM":
            out, meta = _execute_tdm(sess, iv)
            return _seal(sess, user_text, out, extra={"workflow": "chained", "iv": asdict(iv), "gen_meta": meta})

    seq, why = route_aru_sequence(iv, sess)

    if seq and seq[0] == "BOUND":
        msg = (
            "BOUND: I can’t help with that.\n"
            f"Reason: safe={iv.safe} | s1_ok={iv.safe_stage1_ok} ({iv.safe_stage1_reason}) "
            f"| s2_ok={iv.safe_stage2_ok} score={iv.safe_stage2_score:.3f}\n"
            "REDIRECT: Ask for safe, lawful, non-harmful info instead."
        )
        return _seal(sess, user_text, msg, extra={"route": {"seq": seq, "why": why}, "iv": asdict(iv)})

    if seq and seq[0] == "DEFER":
        msg = (
            "DEFER: This is high-stakes. I need strong verification evidence (E3) before proceeding.\n"
            "To continue safely:\n"
            "1) Provide authoritative sources you want used, OR\n"
            "2) Describe your verification method, OR\n"
            "3) Narrow to general, non-actionable info."
        )
        return _seal(sess, user_text, msg, extra={"route": {"seq": seq, "why": why}, "iv": asdict(iv)})

    if seq and seq[0] == "REFLECT":
        payload = {
            "user_text_hash": iv.user_text_hash,
            "domain": iv.domain.value,
            "complexity": iv.complexity,
            "requires_scaffold": iv.requires_scaffold,
        }
        set_pending_gate(sess, PendingGate.REFLECT_CONFIRM.value, payload)
        trace(sess, PendingGate.NONE.value, PendingGate.REFLECT_CONFIRM.value, "enter_reflect_pending", {"why": why, "token": sess.pending_gate.confirm_token})
        summary = f"You want help with: {iv.user_text.strip()[:220]}"
        return _seal(sess, user_text, render_reflect_prompt(sess, summary), extra={"route": {"seq": seq, "why": why}, "iv": asdict(iv)})

    if seq and seq[0] == "SCAFFOLD":
        payload = {
            "user_text_hash": iv.user_text_hash,
            "domain": iv.domain.value,
            "complexity": iv.complexity,
            "plan_stub": True,
        }
        set_pending_gate(sess, PendingGate.SCAFFOLD_APPROVE.value, payload)
        trace(sess, PendingGate.NONE.value, PendingGate.SCAFFOLD_APPROVE.value, "enter_scaffold_pending", {"why": why, "token": sess.pending_gate.confirm_token})

        plan = (
            "Plan:\n"
            "1) Confirm requirements and constraints\n"
            "2) Propose architecture / approach\n"
            "3) Provide implementation steps\n"
            "4) Provide test + validation checklist\n"
        )
        return _seal(sess, user_text, render_scaffold_prompt(sess, plan), extra={"route": {"seq": seq, "why": why}, "iv": asdict(iv)})

    out, meta = _execute_tdm(sess, iv)
    return _seal(sess, user_text, out, extra={"route": {"seq": seq, "why": why}, "iv": asdict(iv), "gen_meta": meta})


# ---------------------------
# EPACK sealing + persistence
# ---------------------------

def _seal(sess: SessionState, user_text: str, assistant_text: str, extra: Dict[str, Any]) -> Dict[str, Any]:
    sess.epack_seq += 1

    payload = {
        "interaction": sess.interaction_count,
        "profile": sess.current_profile,
        "user_text_hash": stable_hash(user_text),
        "assistant_text_hash": stable_hash(assistant_text),
        "pending_gate": {
            "gate": sess.pending_gate.gate,
            "created_at_interaction": sess.pending_gate.created_at_interaction,
            "expires_after_turns": sess.pending_gate.expires_after_turns,
            "pending_payload_hash": sess.pending_gate.payload_hash,
            "pending_confirm_token": sess.pending_gate.confirm_token,
            "pending_require_token_binding": sess.pending_gate.require_token_binding,
            "pending_nonce": sess.pending_gate.nonce,
            "prompt_cache_hash": sess.pending_gate.prompt_cache_hash,
        },
        "traces_tail": [asdict(t) for t in sess.traces[-20:]],
        "tsv_snapshot": sess.tsv.snapshot(),
        "build_manifest": current_manifest(),
        "extra": extra,
    }

    # ── Brick 3: Decision Object + EPACK commitment ─────────────────────
    decision_obj, decision_hash = build_decision_object(
        session_id=getattr(sess, "session_id", "unknown"),
        payload=payload,
        assistant_text=assistant_text,
        build_manifest=current_manifest(),
        profile=getattr(sess, "current_profile", None),
        prev_decision_hash=getattr(sess, "prev_decision_hash", None),
    )
    payload["decision_hash"] = decision_hash
    payload["decision_object"] = decision_obj
    setattr(sess, "prev_decision_hash", decision_hash)

    ep = new_epack(
        sess.epack_seq,
        sess.epack_prev_hash,
        payload,
        payload_hash_override=decision_hash,
    )
    sess.epack_prev_hash = ep.hash

    record = {
        "seq": ep.seq,
        "ts": ep.ts,
        "prev_hash": ep.prev_hash,
        "payload_hash": getattr(ep, "payload_hash", decision_hash),
        "hash": ep.hash,
        "payload": ep.payload,
    }
    sess.epacks.append(record)

    persist_record = dict(record)
    persist_record["payload"] = redact_payload(persist_record["payload"])

    if Settings.PERSIST_EPACKS and ep.seq > sess.last_persisted_seq:
        append_jsonl(Settings.EPACK_STORE_PATH, persist_record)
        sess.last_persisted_seq = ep.seq

    return {"assistant_text": assistant_text, "epack": record}


# ============================
# V9 Full Runtime Loop
# ============================

@lru_cache(maxsize=1)
def _v9_runtime() -> ResilienceRuntime:
    """Process-wide singleton: compile resilience policy into a live runtime.

    The runtime holds the recovery engine, damping, circuit breaker, TSI
    tracker, and verifier — all wired from the governance YAML.
    """
    from ecosphere.governance.dsl_loader import load_policy

    default_policy_path = os.getenv("BW_POLICY_PATH") or "policies/enterprise_v9.yaml"
    if not os.path.exists(default_policy_path):
        default_policy_path = "policies/default.yaml"

    policy = load_policy(default_policy_path)
    compiled = compile_resilience_policy(policy)

    if compiled.enabled and compiled.runtime:
        return compiled.runtime

    # Fallback: disabled resilience (still returns a runtime for API compatibility)
    from ecosphere.meta_validation.recovery_engine import RecoveryEngine, RecoveryBudgets, RecoveryTargets
    return ResilienceRuntime(
        engine=RecoveryEngine(budgets=RecoveryBudgets(), targets=RecoveryTargets()),
        plans=[],
        enabled=False,
    )


def _execute_v9_runtime(sess: SessionState, user_text: str, iv: InputVector) -> Tuple[str, Dict[str, Any]]:
    """Run a single turn through the V9 consensus + resilience loop."""
    from ecosphere.consensus.policy_loader import consensus_config_from_policy
    from ecosphere.consensus.orchestrator.flow import run_consensus
    from ecosphere.governance.dsl_loader import load_policy

    rt = _v9_runtime()

    # Build consensus config from policy
    default_policy_path = os.getenv("BW_POLICY_PATH") or "policies/enterprise_v9.yaml"
    if not os.path.exists(default_policy_path):
        default_policy_path = "policies/default.yaml"
    policy = load_policy(default_policy_path)
    consensus_config = consensus_config_from_policy(policy)

    # Run consensus
    import uuid as _uuid
    _run_id = _uuid.uuid4().hex
    _epack_id = f"v9-{_run_id[:12]}"
    result = asyncio.run(run_consensus(
        user_query=user_text,
        epack=_epack_id,
        config=consensus_config,
        run_id=_run_id,
    ))

    # Feed outcome into TSI tracker
    status = getattr(result, "status", None) or "UNKNOWN"
    rt.record_outcome(
        status=status,
        validator_agreement=0.5,
        latency_ms=int((getattr(result, "timings", {}) or {}).get("total_ms", 0)),
        challenger_fired=False,
    )

    # Get live TSI signal
    signal = rt.current_signal()

    # Build trust snapshot for recovery decision
    snapshot = TrustSnapshot(
        tsi_current=signal.tsi_current,
        tsi_forecast_15m=signal.tsi_forecast_15m,
        der_density=0.0,
        dep_concentration_index=0.0,
        degraded=(status != "PASS"),
    )

    # Maybe trigger recovery
    decision = rt.maybe_recover(snapshot)

    # Extract assistant text
    output = getattr(result, "output", None)
    if output and hasattr(output, "answer"):
        assistant_text = output.answer
    elif output:
        assistant_text = str(output)
    else:
        assistant_text = getattr(result, "text", None) or str(result)

    meta: Dict[str, Any] = {
        "v9": {
            "consensus_status": status,
            "tsi": {
                "current": signal.tsi_current,
                "forecast_15m": signal.tsi_forecast_15m,
                "window_size": signal.window_size,
                "pass_rate": signal.pass_rate,
                "trend_slope": signal.trend_slope,
            },
            "recovery": decision.to_dict() if decision else None,
            "policy_id": policy.get("policy_id"),
            "policy_version": policy.get("policy_version"),
        },
        "iv": asdict(iv),
    }
    return assistant_text, meta
