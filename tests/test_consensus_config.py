"""Tests for consensus.config — preset selection and verification routing.

Covers: preset_fast, preset_high_assurance, preset_consensus,
preset_for_verification routing by role_level.
"""
import pytest

from ecosphere.consensus.config import ConsensusConfig, DEFAULT_PROMPTS, DEFAULT_PRIMARY, DEFAULT_VALIDATORS
from ecosphere.consensus.verification.types import VerificationContext, PUBLIC_CONTEXT


# ── Preset basics ─────────────────────────────────────────────────

def test_preset_fast():
    cfg = ConsensusConfig.preset_fast_default()
    assert cfg.profile_name == "FAST"
    assert cfg.max_repair_attempts == 1
    assert cfg.primary_timeout_s == 35
    assert len(cfg.validators) <= 1
    assert cfg.enable_debate is False


def test_preset_high_assurance():
    cfg = ConsensusConfig.preset_high_assurance_default()
    assert cfg.profile_name == "HIGH_ASSURANCE"
    assert cfg.max_repair_attempts == 2
    assert cfg.primary_timeout_s == 60


def test_preset_consensus():
    cfg = ConsensusConfig.preset_consensus_default()
    assert cfg.profile_name == "CONSENSUS"
    assert cfg.primary_timeout_s == 75


# ── Verification-based selection ──────────────────────────────────

def test_preset_for_public_selects_fast():
    cfg = ConsensusConfig.preset_for_verification_default(PUBLIC_CONTEXT)
    assert cfg.profile_name == "FAST"


def test_preset_for_unverified_selects_fast():
    ctx = VerificationContext(verified=False, role="public", role_level=1)
    cfg = ConsensusConfig.preset_for_verification_default(ctx)
    assert cfg.profile_name == "FAST"


def test_preset_for_nurse_selects_high_assurance():
    ctx = VerificationContext(verified=True, role="nurse", role_level=2, scope="nursing")
    cfg = ConsensusConfig.preset_for_verification_default(ctx)
    assert cfg.profile_name == "HIGH_ASSURANCE"


def test_preset_for_physician_selects_consensus():
    ctx = VerificationContext(verified=True, role="physician", role_level=3, scope="general")
    cfg = ConsensusConfig.preset_for_verification_default(ctx)
    assert cfg.profile_name == "CONSENSUS"


def test_preset_for_specialist_selects_consensus():
    ctx = VerificationContext(verified=True, role="specialist", role_level=4, scope="research")
    cfg = ConsensusConfig.preset_for_verification_default(ctx)
    assert cfg.profile_name == "CONSENSUS"


# ── VerificationContext properties ────────────────────────────────

def test_public_context_is_public():
    assert PUBLIC_CONTEXT.is_public is True
    assert PUBLIC_CONTEXT.is_verified_pro is False
    assert PUBLIC_CONTEXT.requires_full_detail is False


def test_physician_context_properties():
    ctx = VerificationContext(verified=True, role="physician", role_level=3, scope="general")
    assert ctx.is_public is False
    assert ctx.is_verified_pro is True
    assert ctx.requires_full_detail is True


def test_nurse_context_properties():
    ctx = VerificationContext(verified=True, role="nurse", role_level=2, scope="nursing")
    assert ctx.is_verified_pro is False
    assert ctx.requires_full_detail is False
