"""Tests for consensus.gates.scope_gate — content guard decisions.

Covers: PASS for verified pros, REWRITE for mid-tier violations,
REFUSE for public-tier violations, disclaimer checks, ledger events.
"""
import pytest

from ecosphere.consensus.gates.scope_gate import ScopeGateConfig, scope_gate_v1
from ecosphere.consensus.schemas import PrimaryOutput
from ecosphere.consensus.verification.types import VerificationContext, PUBLIC_CONTEXT
from ecosphere.consensus.ledger.reader import clear_epack_events_for_test, get_recent_events


@pytest.fixture(autouse=True)
def _reset_ledger():
    clear_epack_events_for_test()
    yield
    clear_epack_events_for_test()


def _output(answer: str, reasoning: list = None) -> PrimaryOutput:
    return PrimaryOutput(
        run_id="run-test",
        epack="epack-test",
        aru="ANSWER",
        answer=answer,
        reasoning_trace=reasoning or [],
    )


def _config() -> ScopeGateConfig:
    return ScopeGateConfig(domain="healthcare")


# ── PASS for verified physician ───────────────────────────────────

def test_pass_for_verified_physician():
    ctx = VerificationContext(verified=True, role="physician", role_level=3, scope="general")
    output = _output("The diagnosis shows improvement. Your treatment plan should continue.")
    result = scope_gate_v1(output=output, verification=ctx, config=_config(), epack="ep", run_id="r")
    assert result["decision"] == "PASS"

    events = get_recent_events(epack_id="ep", stage_prefix="tecl.scope_gate.", limit=10)
    assert any(e["stage"] == "tecl.scope_gate.pass" for e in events)


# ── REWRITE for mid-tier nurse ────────────────────────────────────

def test_rewrite_for_nurse_with_diagnostic_language():
    ctx = VerificationContext(verified=True, role="nurse", role_level=2, scope="nursing")
    output = _output("The diagnosis shows the patient has condition X. Treatment plan includes Y.")
    result = scope_gate_v1(output=output, verification=ctx, config=_config(), epack="ep", run_id="r")
    assert result["decision"] == "REWRITE"
    assert "violations" in result["details"]

    events = get_recent_events(epack_id="ep", stage_prefix="tecl.scope_gate.", limit=10)
    assert any(e["stage"] == "tecl.scope_gate.violation" for e in events)


# ── REFUSE for public user ────────────────────────────────────────

def test_refuse_for_public_with_diagnostic_language():
    output = _output("You are diagnosed with condition X. Your prognosis is poor.")
    result = scope_gate_v1(output=output, verification=PUBLIC_CONTEXT, config=_config(), epack="ep", run_id="r")
    assert result["decision"] == "REFUSE"


# ── PASS with safe content for public ─────────────────────────────

def test_pass_for_public_with_safe_content():
    disclaimer = ScopeGateConfig().low_tier_disclaimer_snippet
    output = _output(f"{disclaimer} Eating vegetables is good for health.")
    result = scope_gate_v1(output=output, verification=PUBLIC_CONTEXT, config=_config(), epack="ep", run_id="r")
    assert result["decision"] == "PASS"


# ── Missing disclaimer triggers issue ─────────────────────────────

def test_missing_disclaimer_for_low_tier():
    output = _output("Eating vegetables is good for health.")  # no disclaimer
    result = scope_gate_v1(output=output, verification=PUBLIC_CONTEXT, config=_config(), epack="ep", run_id="r")
    # Should trigger disclaimer_issue even without pattern violations
    assert result["decision"] == "REFUSE"
    assert result["details"].get("disclaimer_issue")


# ── Financial pattern detection ───────────────────────────────────

def test_financial_pattern_rewrite_for_mid_tier():
    ctx = VerificationContext(verified=True, role="advisor", role_level=2, scope="finance")
    output = _output("Expected return 12% if you buy AAPL with this tax strategy.")
    result = scope_gate_v1(output=output, verification=ctx, config=_config(), epack="ep", run_id="r")
    assert result["decision"] == "REWRITE"


# ── Legal pattern detection ───────────────────────────────────────

def test_legal_pattern_refuse_for_public():
    output = _output("You should sue the company. Your liability exposure is high.")
    result = scope_gate_v1(output=output, verification=PUBLIC_CONTEXT, config=_config(), epack="ep", run_id="r")
    assert result["decision"] == "REFUSE"


# ── High-level specialist passes advanced content ─────────────────

def test_specialist_passes_statistical_content():
    ctx = VerificationContext(verified=True, role="specialist", role_level=4, scope="research")
    output = _output("The p-value was 0.03, below the confidence interval threshold for statistical significance.")
    result = scope_gate_v1(output=output, verification=ctx, config=_config(), epack="ep", run_id="r")
    assert result["decision"] == "PASS"


def test_physician_blocked_on_statistical_content():
    """Level 3 physician blocked by level-4 statistical pattern."""
    ctx = VerificationContext(verified=True, role="physician", role_level=3, scope="general")
    output = _output("The p-value was 0.03, showing statistical significance with replication.")
    result = scope_gate_v1(output=output, verification=ctx, config=_config(), epack="ep", run_id="r")
    assert result["decision"] == "REWRITE"
