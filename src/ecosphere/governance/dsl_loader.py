# src/ecosphere/governance/dsl_loader.py
"""Governance DSL Loader — YAML policy parsing + validation.

Loads governance policies from YAML files and validates them
against the BeaconWise governance schema.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

# PyYAML is optional — fall back to JSON if not available
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

import json


# ── Policy Schema (inline) ───────────────────────────────────

POLICY_DEFAULTS = {
    "policy_id": "default",
    "consensus": {
        "min_validators": 1,
        "independence_min": 0.6,
        "primary": {"provider": "openai", "model": "gpt-4o-mini"},
        "validators": [{"provider": "grok", "model": "grok-2"}],
    },
    "challenger": {
        "enabled": True,
        "provider": "groq",
        "model": "compound-beta",
        "triggers": {
            "high_stakes": True,
            "disagreement_threshold": 0.22,
            "on_gate": True,
            "low_evidence": True,
        },
        "limits": {
            "timeout_s": 6,
            "max_tokens": 400,
            "max_challenges": 10,
        },
    },
    "evidence_rules": {
        "min_strength": "E1",
    },
    "replay": {
        "strict_required": False,
        "retention_years": 7,
    },
    "resilience_policy": {
        "version": "0.1",
        "enabled": False,
        "targets": {
            "tsi": {"target": 0.75, "min": 0.70, "critical": 0.55},
            "recovery": {"max_minutes": 15, "verify_after_minutes": 15}
        },
        "budgets": {"latency_ms_max": 800, "cost_usd_max": 0.50},
        "dependency_caps": {"max_mass": 0.70, "min_diversity": 0.30, "max_density": 0.40},
        "triggers": [
            {"id": "tsi_forecast_drop", "when": "tsi_forecast_15m < targets.tsi.min"},
            {"id": "concentration_high", "when": "concentration_index >= 0.70 and tsi_forecast_15m < targets.tsi.target"},
            {"id": "system_degraded", "when": "system_status in ['degraded','incident']"},
        ],
        "plans": {"tier_1": [], "tier_2": [], "tier_3": []},
        "scoring": {
            "weights": {
                "diversity_bonus": 0.15,
                "latency_penalty_per_ms": 0.0005,
                "cost_penalty_per_usd": 0.25,
                "confidence_low_penalty": 0.30
            },
            "tier_penalties": {1: 0.00, 2: 0.05, 3: 0.12},
            "tie_breakers": ["predicted_independence_gain", "-tier"]
        },
        "damping": {
            "enabled": True,
            "max_oscillation": 0.15,
            "cooldown_seconds": 60,
            "pid": {"kp": 0.5, "ki": 0.2, "kd": 0.1, "integral_cap": 2.0}
        },
        "adaptive_tuning": {"enabled": False, "method": "heuristic", "max_delta": 0.10},
        "human_override": {"enabled": True, "approvers": ["ciso","sre_oncall"], "break_glass": True},
        "audit": {
            "epack_event_types": ["RECOVERY_DECISION","RECOVERY_APPLIED","RECOVERY_VERIFIED","TUNING_EVENT"],
            "verify_with_replay": True,
            "verify_with_mvi": True
        }
    },
}


def load_policy(path: str) -> Dict[str, Any]:
    """Load a governance policy from a YAML or JSON file.

    Falls back to defaults for any missing fields.
    """
    if not os.path.exists(path):
        return dict(POLICY_DEFAULTS)

    with open(path, "r") as f:
        raw = f.read()

    if path.endswith(".json"):
        data = json.loads(raw)
    elif _HAS_YAML:
        data = yaml.safe_load(raw) or {}
    else:
        # Try JSON as fallback
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return dict(POLICY_DEFAULTS)

    return _merge_defaults(data, POLICY_DEFAULTS)


def _merge_defaults(data: Dict, defaults: Dict) -> Dict:
    """Deep-merge data over defaults."""
    result = dict(defaults)
    for key, value in data.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_defaults(value, result[key])
        else:
            result[key] = value
    return result


def validate_policy(policy: Dict[str, Any]) -> list:
    """Validate a policy against required fields.

    Returns list of error strings (empty = valid).
    """
    errors = []

    if "policy_id" not in policy:
        errors.append("Missing required field: policy_id")

    consensus = policy.get("consensus", {})
    if consensus.get("min_validators", 0) < 1:
        errors.append("consensus.min_validators must be >= 1")

    indep = consensus.get("independence_min", 0)
    if not (0.0 <= indep <= 1.0):
        errors.append("consensus.independence_min must be between 0.0 and 1.0")

    challenger = policy.get("challenger", {})
    if challenger.get("enabled"):
        limits = challenger.get("limits", {})
        if limits.get("timeout_s", 6) < 1:
            errors.append("challenger.limits.timeout_s must be >= 1")
        if limits.get("max_tokens", 400) < 50:
            errors.append("challenger.limits.max_tokens must be >= 50")

    return errors


def get_challenger_rules_from_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ChallengerRules-compatible dict from policy."""
    ch = policy.get("challenger", {})
    triggers = ch.get("triggers", {})
    limits = ch.get("limits", {})

    return {
        "enabled": ch.get("enabled", True),
        "trigger_on_high_stakes": triggers.get("high_stakes", True),
        "trigger_on_disagreement": triggers.get("disagreement_threshold", 0.22) > 0,
        "disagreement_threshold": triggers.get("disagreement_threshold", 0.22),
        "trigger_on_gate": triggers.get("on_gate", True),
        "trigger_on_low_evidence": triggers.get("low_evidence", True),
        "max_challenges_per_session": limits.get("max_challenges", 10),
        "timeout_s": limits.get("timeout_s", 6),
        "max_tokens": limits.get("max_tokens", 400),
    }
