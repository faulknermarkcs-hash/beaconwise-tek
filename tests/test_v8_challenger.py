"""Tests for BeaconWise V8 — Challenger Architecture + Full Stack.

Covers all V8 capabilities:
  1. Challenger config (ChallengerRules, ChallengePack)
  2. Challenger engine (trigger, disagreement, parsing, arbitration)
  3. Three-role consensus (7 adapters)
  4. Replay engine
  5. Governance DSL loader
  6. Build manifest V8
  7. Cost-aware triggers
  8. EPACK events
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ecosphere.challenger.config import (
    ChallengerRules, ChallengePack, CriticalClaim, Conflict,
    MissingEvidence, DEFAULT_CHALLENGER_RULES,
    CHALLENGER_SYSTEM_PROMPT, build_challenger_prompt,
)
from ecosphere.challenger.engine import (
    TriggerReason, ChallengerTriggerResult,
    compute_disagreement_score, should_trigger_challenger,
    parse_challenge_pack, arbitrate, ArbitrationResult,
    challenger_event_triggered, challenger_event_skipped,
    challenger_event_output,
)
from ecosphere.replay.engine import (
    replay_governance_decision, replay_chain, replay_summary,
)
from ecosphere.governance.dsl_loader import (
    load_policy, validate_policy, get_challenger_rules_from_policy,
    POLICY_DEFAULTS,
)
from ecosphere.consensus.adapters.factory import get_registered_providers
from ecosphere.kernel.provenance import current_manifest
from ecosphere.utils.stable import stable_hash


# ══════════════════════════════════════════════════════════════
# 1. CHALLENGER CONFIG
# ══════════════════════════════════════════════════════════════

def test_challenger_rules_defaults():
    rules = DEFAULT_CHALLENGER_RULES
    assert rules.enabled is True
    assert rules.disagreement_threshold == 0.22
    assert rules.timeout_s == 6.0
    assert rules.max_tokens == 400


def test_challenger_rules_to_dict():
    rules = ChallengerRules(enabled=False, max_tokens=200)
    d = rules.to_dict()
    assert d["enabled"] is False
    assert d["max_tokens"] == 200


def test_challenger_rules_from_dict():
    d = {"enabled": True, "disagreement_threshold": 0.3, "timeout_s": 10.0}
    rules = ChallengerRules.from_dict(d)
    assert rules.disagreement_threshold == 0.3
    assert rules.timeout_s == 10.0


def test_challenge_pack_empty():
    pack = ChallengePack()
    assert pack.recommended_action == "PASS"
    assert pack.is_clean is True
    assert pack.has_high_risk_claims is False
    assert pack.has_conflicts is False


def test_challenge_pack_with_claims():
    pack = ChallengePack(
        attack_surface=["unsafe_medical_dx"],
        critical_claims=[
            CriticalClaim(claim="take 500mg ibuprofen", risk="high",
                          why="dosage advice", evidence_needed="E2"),
        ],
        recommended_action="REWRITE",
    )
    assert pack.has_high_risk_claims is True
    assert pack.forces_rewrite is True
    assert pack.is_clean is False


def test_challenge_pack_to_dict_roundtrip():
    pack = ChallengePack(
        attack_surface=["injection"],
        critical_claims=[CriticalClaim("claim1", "high", "reason", "E2")],
        conflicts=[Conflict(["primary", "validator_1"], "dosage", "high")],
        missing_evidence=[MissingEvidence("claim1", ["pubmed"])],
        questions_for_primary=["Why no disclaimer?"],
        recommended_action="REWRITE",
        rewrite_instructions=["Add disclaimer"],
    )
    d = pack.to_dict()
    assert d["recommended_action"] == "REWRITE"
    assert len(d["critical_claims"]) == 1
    assert d["critical_claims"][0]["risk"] == "high"

    # Roundtrip
    pack2 = ChallengePack.from_dict(d)
    assert pack2.recommended_action == "REWRITE"
    assert len(pack2.critical_claims) == 1
    assert pack2.critical_claims[0].risk == "high"
    assert pack2.has_conflicts is True


def test_challenge_pack_from_dict_empty():
    pack = ChallengePack.from_dict({})
    assert pack.recommended_action == "PASS"
    assert pack.is_clean is True


def test_challenger_system_prompt_exists():
    assert "adversarial" in CHALLENGER_SYSTEM_PROMPT.lower()
    assert "JSON" in CHALLENGER_SYSTEM_PROMPT
    assert "REFUSE" in CHALLENGER_SYSTEM_PROMPT


def test_build_challenger_prompt():
    prompt = build_challenger_prompt(
        user_query="What drug should I take?",
        primary_response="Take ibuprofen 200mg.",
        validator_response="Consult a doctor.",
        role="public",
        role_level=0,
        domain="HIGH_STAKES",
    )
    assert "What drug" in prompt
    assert "ibuprofen" in prompt
    assert "Consult" in prompt
    assert "role=public" in prompt
    assert "HIGH_STAKES" in prompt


# ══════════════════════════════════════════════════════════════
# 2. CHALLENGER ENGINE — TRIGGER LOGIC
# ══════════════════════════════════════════════════════════════

def test_trigger_disabled():
    rules = ChallengerRules(enabled=False)
    result = should_trigger_challenger(rules=rules, domain="HIGH_STAKES")
    assert result.should_trigger is False


def test_trigger_max_challenges_reached():
    rules = ChallengerRules(max_challenges_per_session=5)
    result = should_trigger_challenger(rules=rules, challenges_this_session=5)
    assert result.should_trigger is False
    assert "max_challenges_reached" in result.reasons


def test_trigger_high_stakes():
    result = should_trigger_challenger(
        rules=DEFAULT_CHALLENGER_RULES, domain="HIGH_STAKES",
    )
    assert result.should_trigger is True
    assert TriggerReason.HIGH_STAKES in result.reasons


def test_trigger_disagreement():
    result = should_trigger_challenger(
        rules=DEFAULT_CHALLENGER_RULES, disagreement_score=0.35,
    )
    assert result.should_trigger is True
    assert TriggerReason.DISAGREEMENT in result.reasons


def test_trigger_disagreement_below_threshold():
    result = should_trigger_challenger(
        rules=DEFAULT_CHALLENGER_RULES, disagreement_score=0.1,
    )
    assert TriggerReason.DISAGREEMENT not in result.reasons


def test_trigger_gate_hit():
    result = should_trigger_challenger(
        rules=DEFAULT_CHALLENGER_RULES, scope_gate_decision="REFUSE",
    )
    assert result.should_trigger is True
    assert TriggerReason.GATE_HIT in result.reasons


def test_trigger_low_evidence():
    result = should_trigger_challenger(
        rules=DEFAULT_CHALLENGER_RULES,
        domain="HIGH_STAKES", evidence_level="E0",
    )
    assert result.should_trigger is True
    assert TriggerReason.LOW_EVIDENCE in result.reasons


def test_trigger_low_evidence_not_high_stakes():
    result = should_trigger_challenger(
        rules=DEFAULT_CHALLENGER_RULES,
        domain="GENERAL", evidence_level="E0",
    )
    assert TriggerReason.LOW_EVIDENCE not in result.reasons


def test_trigger_multiple_reasons():
    result = should_trigger_challenger(
        rules=DEFAULT_CHALLENGER_RULES,
        domain="HIGH_STAKES",
        disagreement_score=0.5,
        scope_gate_decision="REWRITE",
        evidence_level="E1",
    )
    assert result.should_trigger is True
    assert len(result.reasons) >= 3


def test_no_trigger_on_clean_general():
    result = should_trigger_challenger(
        rules=DEFAULT_CHALLENGER_RULES,
        domain="GENERAL",
        disagreement_score=0.05,
        scope_gate_decision="PASS",
        evidence_level="E2",
    )
    assert result.should_trigger is False


# ══════════════════════════════════════════════════════════════
# 3. DISAGREEMENT SCORING
# ══════════════════════════════════════════════════════════════

def test_disagreement_identical():
    score = compute_disagreement_score("hello world", "hello world")
    assert score == 0.0


def test_disagreement_completely_different():
    score = compute_disagreement_score(
        "the cat sat on the mat",
        "purple elephants dancing wildly",
    )
    assert score >= 0.7


def test_disagreement_negation_mismatch():
    score1 = compute_disagreement_score(
        "you should take ibuprofen",
        "you should take ibuprofen",
    )
    score2 = compute_disagreement_score(
        "you should take ibuprofen",
        "you should not take ibuprofen",
    )
    assert score2 > score1


def test_disagreement_empty_inputs():
    assert compute_disagreement_score("", "hello") == 0.0
    assert compute_disagreement_score("hello", "") == 0.0


def test_disagreement_length_penalty():
    short = "yes"
    long = "This is a very long response with many words explaining the detailed reasoning behind the answer"
    score = compute_disagreement_score(short, long)
    assert score >= 0.5  # Length ratio < 0.3 adds penalty


# ══════════════════════════════════════════════════════════════
# 4. CHALLENGEPACK PARSING
# ══════════════════════════════════════════════════════════════

def test_parse_valid_json():
    raw = json.dumps({
        "attack_surface": ["injection"],
        "critical_claims": [{"claim": "x", "risk": "high", "why": "y", "evidence_needed": "E2"}],
        "conflicts": [],
        "missing_evidence": [],
        "questions_for_primary": [],
        "recommended_action": "REWRITE",
        "rewrite_instructions": ["Add disclaimer"],
    })
    pack, err = parse_challenge_pack(raw)
    assert pack is not None
    assert err == ""
    assert pack.recommended_action == "REWRITE"
    assert len(pack.critical_claims) == 1


def test_parse_with_markdown_fences():
    raw = "```json\n{\"recommended_action\": \"PASS\", \"attack_surface\": []}\n```"
    pack, err = parse_challenge_pack(raw)
    assert pack is not None
    assert pack.recommended_action == "PASS"


def test_parse_invalid_json():
    pack, err = parse_challenge_pack("this is not json")
    assert pack is None
    assert "parse error" in err.lower() or "json" in err.lower()


def test_parse_non_object():
    pack, err = parse_challenge_pack("[1, 2, 3]")
    assert pack is None
    assert "not a JSON object" in err


def test_parse_empty_object():
    pack, err = parse_challenge_pack("{}")
    assert pack is not None
    assert pack.recommended_action == "PASS"


# ══════════════════════════════════════════════════════════════
# 5. ARBITRATION
# ══════════════════════════════════════════════════════════════

def test_arbitrate_clean_pack():
    pack = ChallengePack(recommended_action="PASS")
    result = arbitrate(pack=pack)
    assert result.final_action == "PASS"
    assert result.challenger_applied is True
    assert result.constraints_applied == []


def test_arbitrate_refuse_enforced():
    pack = ChallengePack(recommended_action="REFUSE")
    result = arbitrate(pack=pack, role_level=0)
    assert result.final_action == "REFUSE"
    assert "challenger_refuse_enforced" in result.constraints_applied


def test_arbitrate_refuse_downgraded_for_expert():
    pack = ChallengePack(recommended_action="REFUSE")
    result = arbitrate(pack=pack, role_level=3, scope_gate_decision="PASS")
    assert result.final_action == "REWRITE"
    assert "challenger_refuse_downgraded_for_expert" in result.constraints_applied


def test_arbitrate_high_risk_low_tier():
    pack = ChallengePack(
        critical_claims=[CriticalClaim("x", "high", "y", "E2")],
        recommended_action="PASS",
    )
    result = arbitrate(pack=pack, role_level=0)
    assert result.final_action == "REWRITE"
    assert "high_risk_claims_for_low_tier" in result.constraints_applied


def test_arbitrate_high_risk_high_tier_passes():
    pack = ChallengePack(
        critical_claims=[CriticalClaim("x", "high", "y", "E2")],
        recommended_action="PASS",
    )
    result = arbitrate(pack=pack, role_level=3)
    assert result.final_action == "PASS"


def test_arbitrate_conflicts_high_stakes():
    pack = ChallengePack(
        conflicts=[Conflict(["primary", "validator_1"], "dosage", "high")],
        recommended_action="PASS",
    )
    result = arbitrate(pack=pack, domain="HIGH_STAKES")
    assert result.final_action == "REWRITE"
    assert "conflicts_on_high_stakes" in result.constraints_applied


def test_arbitrate_missing_evidence():
    pack = ChallengePack(
        missing_evidence=[MissingEvidence("drug interaction", ["pubmed"])],
        recommended_action="PASS",
    )
    result = arbitrate(pack=pack, domain="HIGH_STAKES")
    assert result.final_action == "REWRITE"
    assert "missing_evidence_high_stakes" in result.constraints_applied


def test_arbitrate_rewrite_instructions_collected():
    pack = ChallengePack(
        recommended_action="REWRITE",
        rewrite_instructions=["Add disclaimer", "Remove dosage"],
    )
    result = arbitrate(pack=pack)
    assert "Add disclaimer" in result.rewrite_instructions
    assert "Remove dosage" in result.rewrite_instructions


# ══════════════════════════════════════════════════════════════
# 6. EPACK EVENTS
# ══════════════════════════════════════════════════════════════

def test_challenger_event_triggered():
    trigger = ChallengerTriggerResult(
        should_trigger=True,
        reasons=["high_stakes_domain"],
        disagreement_score=0.35,
    )
    event = challenger_event_triggered(trigger)
    assert event["stage"] == "tecl.challenger.triggered"
    assert "high_stakes_domain" in event["reasons"]
    assert event["disagreement_score"] == 0.35


def test_challenger_event_skipped():
    event = challenger_event_skipped("not_triggered")
    assert event["stage"] == "tecl.challenger.skipped"


def test_challenger_event_output():
    pack = ChallengePack(recommended_action="REWRITE", attack_surface=["injection"])
    arb = ArbitrationResult(
        final_action="REWRITE", challenger_applied=True,
        constraints_applied=["challenger_rewrite_recommended"],
    )
    event = challenger_event_output(pack, arb)
    assert event["stage"] == "tecl.arbitration.applied_constraints"
    assert event["final_action"] == "REWRITE"
    assert "challenge_pack_hash" in event
    assert len(event["challenge_pack_hash"]) == 64


# ══════════════════════════════════════════════════════════════
# 7. ADAPTER REGISTRY (7 PROVIDERS)
# ══════════════════════════════════════════════════════════════

def test_adapter_registry_seven_providers():
    providers = get_registered_providers()
    assert "openai" in providers
    assert "anthropic" in providers
    assert "mock" in providers
    assert "symbolic" in providers
    assert "retrieval" in providers
    assert "grok" in providers
    assert "groq" in providers
    assert len(providers) >= 7


# ══════════════════════════════════════════════════════════════
# 8. REPLAY ENGINE
# ══════════════════════════════════════════════════════════════

def _make_epack_record(seq, prev_hash="GENESIS"):
    payload = {
        "interaction": seq,
        "profile": "A_STANDARD",
        "user_text_hash": stable_hash(f"user-{seq}"),
        "assistant_text_hash": stable_hash(f"assistant-{seq}"),
        "pending_gate": {},
        "traces_tail": [],
        "tsv_snapshot": {},
        "build_manifest": {"manifest_hash": "abc123"},
        "extra": {"route": "TDM", "safety_stage1_ok": True},
    }
    ts = 1000.0 + seq
    h = stable_hash({"seq": seq, "ts": ts, "prev_hash": prev_hash, "payload": payload})
    return {"seq": seq, "ts": ts, "prev_hash": prev_hash, "hash": h, "payload": payload}


def test_replay_single_valid_record():
    record = _make_epack_record(1)
    result = replay_governance_decision(epack_record=record)
    assert result.determinism_index == 100.0
    assert result.governance_match is True


def test_replay_tampered_record():
    record = _make_epack_record(1)
    record["hash"] = "TAMPERED"
    result = replay_governance_decision(epack_record=record)
    assert result.governance_match is False
    assert result.determinism_index < 100.0


def test_replay_chain_all_valid():
    chain = []
    prev = "GENESIS"
    for i in range(1, 4):
        rec = _make_epack_record(i, prev)
        chain.append(rec)
        prev = rec["hash"]

    results = replay_chain(chain)
    assert len(results) == 3
    assert all(r.governance_match for r in results)


def test_replay_summary():
    chain = []
    prev = "GENESIS"
    for i in range(1, 6):
        rec = _make_epack_record(i, prev)
        chain.append(rec)
        prev = rec["hash"]

    results = replay_chain(chain)
    summary = replay_summary(results)
    assert summary["total"] == 5
    assert summary["determinism_index"] == 100.0
    assert summary["governance_match_rate"] == 1.0
    assert summary["tampered_records"] == []


def test_replay_missing_manifest():
    record = _make_epack_record(1)
    record["payload"]["build_manifest"] = {}
    # Recompute hash
    record["hash"] = stable_hash({
        "seq": record["seq"], "ts": record["ts"],
        "prev_hash": record["prev_hash"], "payload": record["payload"],
    })
    result = replay_governance_decision(epack_record=record)
    assert result.governance_match is False  # Missing manifest hash


# ══════════════════════════════════════════════════════════════
# 9. GOVERNANCE DSL LOADER
# ══════════════════════════════════════════════════════════════

def test_load_policy_defaults():
    policy = load_policy("nonexistent_file.yaml")
    assert policy["policy_id"] == "default"
    assert policy["consensus"]["min_validators"] == 1
    assert policy["challenger"]["enabled"] is True


def test_load_policy_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({
            "policy_id": "test_policy",
            "consensus": {"min_validators": 3},
        }, f)
        f.flush()
        policy = load_policy(f.name)

    assert policy["policy_id"] == "test_policy"
    assert policy["consensus"]["min_validators"] == 3
    # Defaults filled in
    assert policy["challenger"]["enabled"] is True
    os.unlink(f.name)


def test_validate_policy_valid():
    errors = validate_policy(POLICY_DEFAULTS)
    assert errors == []


def test_validate_policy_missing_id():
    errors = validate_policy({"consensus": {"min_validators": 1}})
    assert any("policy_id" in e for e in errors)


def test_validate_policy_bad_validators():
    errors = validate_policy({"policy_id": "x", "consensus": {"min_validators": 0}})
    assert any("min_validators" in e for e in errors)


def test_get_challenger_rules_from_policy():
    rules = get_challenger_rules_from_policy(POLICY_DEFAULTS)
    assert rules["enabled"] is True
    assert rules["disagreement_threshold"] == 0.22
    assert rules["timeout_s"] == 6
    assert rules["max_tokens"] == 400


# ══════════════════════════════════════════════════════════════
# 10. BUILD MANIFEST V8
# ══════════════════════════════════════════════════════════════

def test_manifest_v8_version():
    m = current_manifest()
    assert m["kernel_version"] in ("v9.0.0", "v1.9.0")
    assert m["product_name"] == "BeaconWise Transparency Ecosphere Kernel (TEK)"


def test_manifest_v8_capabilities():
    m = current_manifest()
    v8_flags = [k for k in m if k.startswith("v8_")]
    assert len(v8_flags) == 10
    for flag in v8_flags:
        assert m[flag] is True, f"{flag} should be True"


def test_manifest_v7_backward_compat():
    m = current_manifest()
    v7_flags = [k for k in m if k.startswith("v7_")]
    assert len(v7_flags) == 10
    for flag in v7_flags:
        assert m[flag] is True


def test_manifest_hash_present():
    m = current_manifest()
    assert "manifest_hash" in m
    assert len(m["manifest_hash"]) == 64


def test_manifest_hash_stable():
    m1 = current_manifest()
    m2 = current_manifest()
    assert m1["manifest_hash"] == m2["manifest_hash"]
