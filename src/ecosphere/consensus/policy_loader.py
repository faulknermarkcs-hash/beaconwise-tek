"""Build runtime consensus configuration from a governance DSL policy.

V9 goal: the policy file (YAML) is the *single source of truth* for
provider selection, consensus depth, and routing knobs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import (
    ConsensusConfig,
    DebateConfig,
    ModelSpec,
    PromptBundle,
    DEFAULT_PROMPTS,
    DEFAULT_PRIMARY,
    DEFAULT_VALIDATORS,
)


def _model_spec_from_dict(d: Dict[str, Any], fallback: Optional[ModelSpec] = None) -> Optional[ModelSpec]:
    """Build a ModelSpec from a policy dict entry like {provider: openai, model: gpt-4o}."""
    if not isinstance(d, dict):
        return fallback
    provider = d.get("provider")
    model = d.get("model")
    if not provider or not model:
        return fallback
    return ModelSpec(
        provider=str(provider),
        model=str(model),
        family=d.get("family"),
        timeout_s=d.get("timeout_s"),
        extra=dict(d.get("extra") or {}),
    )


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}
    return False


def consensus_config_from_policy(policy: Dict[str, Any]) -> ConsensusConfig:
    """Create a ConsensusConfig from a governance DSL policy dict.

    Supports policy shapes:
      - V8 flat:  consensus.primary.provider / consensus.validators[]
      - V9 nested: consensus.providers.primary / consensus.providers.validators[]
      - Debate: consensus.enable_debate + consensus.debate.{defender_model, critic_model, synthesizer_model}
               or consensus.providers.debate.{...}

    Unknown keys are silently ignored.
    """
    if not isinstance(policy, dict):
        return ConsensusConfig.preset_fast_default()

    consensus = policy.get("consensus", {})
    if not isinstance(consensus, dict):
        return ConsensusConfig.preset_fast_default()

    # --- Primary ---
    providers_block = consensus.get("providers", {}) or {}
    primary_dict = providers_block.get("primary") or consensus.get("primary") or {}
    primary = _model_spec_from_dict(primary_dict, fallback=DEFAULT_PRIMARY)

    # --- Validators ---
    validator_list = providers_block.get("validators") or consensus.get("validators") or []
    validators: List[ModelSpec] = []
    for v in validator_list:
        ms = _model_spec_from_dict(v) if isinstance(v, dict) else None
        if ms:
            validators.append(ms)
    if not validators:
        validators = list(DEFAULT_VALIDATORS)

    # --- Prompts ---
    prompts: PromptBundle = DEFAULT_PROMPTS

    # --- Numeric knobs ---
    timeout_s = int(consensus.get("primary_timeout_s", 60))
    timeout_s = max(5, min(300, timeout_s))
    max_repair = int(consensus.get("max_repair_attempts", 2))
    max_repair = max(0, min(5, max_repair))

    # --- Debate (Primary/Challenger/Arbiter) ---
    enable_debate = _truthy(consensus.get("enable_debate", False))

    debate_block = (
        providers_block.get("debate")
        or consensus.get("debate")
        or {}
    )
    debate_cfg: Optional[DebateConfig] = None
    if isinstance(debate_block, dict):
        defender = _model_spec_from_dict(debate_block.get("defender_model") or {})
        critic = _model_spec_from_dict(debate_block.get("critic_model") or {})
        synth = _model_spec_from_dict(debate_block.get("synthesizer_model") or {})
        if defender and critic and synth:
            debate_cfg = DebateConfig(
                defender_model=defender,
                critic_model=critic,
                synthesizer_model=synth,
            )
            enable_debate = True  # if debate models are present, force on

    return ConsensusConfig(
        profile_name=f"policy:{policy.get('policy_id', 'unknown')}",
        primary=primary,
        validators=validators,
        prompts=prompts,
        primary_temperature=0.0,
        primary_timeout_s=timeout_s,
        max_repair_attempts=max_repair,
        enable_debate=enable_debate,
        debate=debate_cfg,
    )
