"""Policy loader tests — DSL YAML → ConsensusConfig."""
import pytest
from ecosphere.consensus.policy_loader import consensus_config_from_policy, _model_spec_from_string


def test_empty_policy_returns_defaults():
    cfg = consensus_config_from_policy({})
    assert cfg.primary is not None
    assert len(cfg.validators) > 0


def test_none_policy_returns_defaults():
    cfg = consensus_config_from_policy(None)
    assert cfg.primary is not None


def test_v9_nested_providers():
    policy = {
        "policy_id": "test_v9",
        "consensus": {
            "providers": {
                "primary": {"provider": "openai", "model": "gpt-4o"},
                "validators": [
                    {"provider": "groq", "model": "compound-beta"},
                    {"provider": "anthropic", "model": "claude-3-opus"},
                ],
            },
        },
    }
    cfg = consensus_config_from_policy(policy)
    assert cfg.primary.provider == "openai"
    assert cfg.primary.model == "gpt-4o"
    assert len(cfg.validators) == 2
    assert cfg.validators[0].provider == "groq"


def test_v8_flat_providers():
    policy = {
        "policy_id": "test_v8",
        "consensus": {
            "primary": {"provider": "openai", "model": "gpt-4o"},
            "validators": [{"provider": "groq", "model": "compound-beta"}],
        },
    }
    cfg = consensus_config_from_policy(policy)
    assert cfg.primary.provider == "openai"
    assert len(cfg.validators) == 1


def test_profile_name_from_policy_id():
    cfg = consensus_config_from_policy({"policy_id": "enterprise_v9"})
    assert "enterprise_v9" in cfg.profile_name


def test_model_spec_from_string():
    ms = _model_spec_from_string("openai:gpt-4o")
    assert ms is not None
    assert ms.provider == "openai"
    assert ms.model == "gpt-4o"


def test_model_spec_from_string_no_colon():
    ms = _model_spec_from_string("nocolon")
    assert ms is None
