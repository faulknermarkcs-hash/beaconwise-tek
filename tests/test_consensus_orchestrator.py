"""Tests for consensus.orchestrator.flow.run_consensus.

Covers: PASS flow, REFUSE flow (scope violation), parse failure,
anchor mismatch, rewrite cycle, ledger events, auto-generated run_id.
All tests use MockAdapter via factory — no API keys needed.
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ecosphere.consensus.adapters import factory as adapter_factory
from ecosphere.consensus.adapters.mock_adapter import MockAdapter
from ecosphere.consensus.config import ConsensusConfig, ModelSpec, PromptBundle
from ecosphere.consensus.orchestrator import flow as flow_module
from ecosphere.consensus.orchestrator import stage_rewrite as rewrite_module
from ecosphere.consensus.orchestrator.flow import run_consensus
from ecosphere.consensus.verification.types import VerificationContext, PUBLIC_CONTEXT
from ecosphere.consensus.ledger.reader import clear_epack_events_for_test, get_recent_events


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


_PROMPTS = PromptBundle(
    primary_template=(
        "RUN_ID={RUN_ID} EPACK={EPACK} ARU={ARU}\n"
        "VERIFIED={VERIFIED} ROLE={ROLE} ROLE_LEVEL={ROLE_LEVEL} SCOPE={SCOPE}\n"
        "User query:\n{USER_QUERY}\n"
    ),
    repair_template=(
        "RUN_ID={RUN_ID} EPACK={EPACK} ARU={ARU}\n"
        "Fix this:\n{BAD_TEXT}\n"
    ),
)


def _cfg():
    return ConsensusConfig(
        profile_name="TEST",
        primary=ModelSpec(provider="mock", model="mock-v1"),
        validators=[],
        primary_temperature=0.0,
        primary_timeout_s=30,
        max_repair_attempts=1,
        prompts=_PROMPTS,
    )


def _patch_adapter(responses=None, default_answer="Mock response for testing."):
    originals = (
        adapter_factory.build_adapter,
        flow_module.build_adapter,
        rewrite_module.build_adapter,
    )
    def _mock_build(spec):
        return MockAdapter(provider="mock", model="mock-v1",
                           responses=responses, default_answer=default_answer)
    adapter_factory.build_adapter = _mock_build
    flow_module.build_adapter = _mock_build
    rewrite_module.build_adapter = _mock_build
    return originals


def _unpatch_adapter(originals):
    adapter_factory.build_adapter = originals[0]
    flow_module.build_adapter = originals[1]
    rewrite_module.build_adapter = originals[2]


# ── PASS: verified physician ──────────────────────────────────────

def test_consensus_pass_verified_physician():
    clear_epack_events_for_test()
    ctx = VerificationContext(verified=True, role="physician", role_level=3, scope="general")
    result = _run(run_consensus(
        user_query="How is the patient doing?",
        epack="ep-pass",
        config=_cfg(),
        verification=ctx,
        run_id="r-pass",
    ))
    assert result.status == "PASS", f"Expected PASS, got {result.status}: {result.error}"
    assert result.output is not None
    assert result.run_id == "r-pass"
    assert result.timings is not None
    assert "primary_s" in result.timings

    events = get_recent_events(epack_id="ep-pass", stage_prefix="tecl.", limit=20)
    stages = [e["stage"] for e in events]
    assert "tecl.start" in stages
    assert "tecl.primary.raw" in stages
    clear_epack_events_for_test()


# ── PASS: public with disclaimer ──────────────────────────────────

def test_consensus_pass_public_with_disclaimer():
    clear_epack_events_for_test()
    from ecosphere.consensus.gates.scope_gate import ScopeGateConfig
    disclaimer = ScopeGateConfig().low_tier_disclaimer_snippet

    orig = _patch_adapter(default_answer=f"{disclaimer} Eating vegetables is healthy.")
    try:
        result = _run(run_consensus(
            user_query="Is eating vegetables good?",
            epack="ep-pub",
            config=_cfg(),
            verification=PUBLIC_CONTEXT,
            run_id="r-pub",
        ))
        assert result.status == "PASS", f"Expected PASS, got {result.status}: {result.gate}"
    finally:
        _unpatch_adapter(orig)
    clear_epack_events_for_test()


# ── REFUSE: diagnostic language for public ────────────────────────

def test_consensus_refuse_scope_violation_public():
    clear_epack_events_for_test()
    orig = _patch_adapter(default_answer="You are diagnosed with condition X. Your prognosis is poor.")
    try:
        result = _run(run_consensus(
            user_query="What is wrong with me?",
            epack="ep-refuse",
            config=_cfg(),
            verification=PUBLIC_CONTEXT,
            run_id="r-refuse",
        ))
        assert result.status == "REFUSE", f"Expected REFUSE, got {result.status}"
        assert result.gate is not None
        scope_result = result.gate.get("scope", {})
        assert scope_result.get("decision") in ("REFUSE", "REWRITE"), f"Unexpected scope: {scope_result}"
    finally:
        _unpatch_adapter(orig)

    events = get_recent_events(epack_id="ep-refuse", stage_prefix="tecl.scope_gate.", limit=10)
    assert any(e["stage"] == "tecl.scope_gate.violation" for e in events)
    clear_epack_events_for_test()


# ── REWRITE → REFUSE: nurse with diagnostic language ──────────────

def test_consensus_rewrite_then_refuse_for_nurse():
    clear_epack_events_for_test()
    orig = _patch_adapter(default_answer="The diagnosis shows condition X. Treatment plan includes Y.")
    try:
        ctx = VerificationContext(verified=True, role="nurse", role_level=2, scope="nursing")
        result = _run(run_consensus(
            user_query="What does the chart say?",
            epack="ep-rw",
            config=_cfg(),
            verification=ctx,
            run_id="r-rw",
        ))
        assert result.status == "REFUSE"
    finally:
        _unpatch_adapter(orig)
    clear_epack_events_for_test()


# ── Parse failure → REFUSE ────────────────────────────────────────

def test_consensus_parse_failure():
    clear_epack_events_for_test()
    bad_responses = ["not json at all {{{", "still not json }}}"]
    orig = _patch_adapter(responses=bad_responses)
    try:
        result = _run(run_consensus(
            user_query="test",
            epack="ep-parse",
            config=_cfg(),
            verification=PUBLIC_CONTEXT,
            run_id="r-parse",
        ))
        assert result.status == "REFUSE"
        assert "parse" in (result.error or "").lower() or "failed" in (result.error or "").lower()
    finally:
        _unpatch_adapter(orig)
    clear_epack_events_for_test()


# ── Anchor mismatch → REFUSE ─────────────────────────────────────

def test_consensus_anchor_mismatch():
    clear_epack_events_for_test()
    bad_json = json.dumps({
        "run_id": "wrong-id",
        "epack": "ep-anchor",
        "aru": "ANSWER",
        "answer": "test",
        "reasoning_trace": [],
        "claims": [],
        "overall_confidence": 0.8,
        "uncertainty_flags": [],
        "next_step": None,
    })
    orig = _patch_adapter(responses=[bad_json])
    try:
        result = _run(run_consensus(
            user_query="test",
            epack="ep-anchor",
            config=_cfg(),
            verification=PUBLIC_CONTEXT,
            run_id="r-anchor",
        ))
        assert result.status == "REFUSE"
        gate_str = str(result.gate) + str(result.error or "")
        assert "anchor" in gate_str.lower() or "mismatch" in gate_str.lower()
    finally:
        _unpatch_adapter(orig)
    clear_epack_events_for_test()


# ── Timings present ───────────────────────────────────────────────

def test_consensus_result_has_timings():
    clear_epack_events_for_test()
    ctx = VerificationContext(verified=True, role="physician", role_level=3, scope="general")
    result = _run(run_consensus(
        user_query="status check",
        epack="ep-time",
        config=_cfg(),
        verification=ctx,
        run_id="r-time",
    ))
    assert result.timings is not None
    assert result.timings["primary_s"] >= 0
    assert result.timings["total_s"] >= result.timings["primary_s"]
    clear_epack_events_for_test()


# ── Default verification = PUBLIC ─────────────────────────────────

def test_consensus_default_verification_is_public():
    clear_epack_events_for_test()
    result = _run(run_consensus(
        user_query="what is health?",
        epack="ep-def",
        config=_cfg(),
        run_id="r-def",
    ))
    assert result.status in ("PASS", "REFUSE")
    clear_epack_events_for_test()


# ── Auto-generated run_id ─────────────────────────────────────────

def test_consensus_run_id_auto_generated():
    clear_epack_events_for_test()
    ctx = VerificationContext(verified=True, role="physician", role_level=3, scope="general")
    result = _run(run_consensus(
        user_query="test",
        epack="ep-auto",
        config=_cfg(),
        verification=ctx,
    ))
    assert result.run_id
    assert len(result.run_id) > 0
    clear_epack_events_for_test()


# ── Ledger events complete ────────────────────────────────────────

def test_consensus_ledger_events_complete():
    clear_epack_events_for_test()
    ctx = VerificationContext(verified=True, role="physician", role_level=3, scope="general")
    _run(run_consensus(
        user_query="audit me",
        epack="ep-audit",
        config=_cfg(),
        verification=ctx,
        run_id="r-audit",
    ))

    events = get_recent_events(epack_id="ep-audit", stage_prefix="tecl.", limit=20)
    stages = [e["stage"] for e in events]

    assert "tecl.start" in stages
    assert "tecl.primary.raw" in stages
    assert any("scope_gate" in s for s in stages)
    clear_epack_events_for_test()
