"""Build runtime consensus configuration from a governance DSL policy.

V9 goal: the policy file (YAML) is the *single source of truth* for
provider selection, consensus depth, and basic routing knobs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import (
    ConsensusConfig,
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
    )


def _model_spec_from_string(spec: str) -> Optional[ModelSpec]:
    """Parse 'provider:model' string into ModelSpec."""
    if ":" not in spec:
        return None
    provider, model = spec.split(":", 1)
    return ModelSpec(provider=provider.strip(), model=model.strip())


def consensus_config_from_policy(policy: Dict[str, Any]) -> ConsensusConfig:
    """Create a ConsensusConfig from a governance DSL policy dict.

    Supports two policy shapes:
      - V8 flat:  consensus.primary.provider / consensus.validators[]
      - V9 nested: consensus.providers.primary / consensus.providers.validators[]

    Unknown keys are silently ignored.
    """
    if not isinstance(policy, dict):
        return ConsensusConfig.preset_fast_default()

    consensus = policy.get("consensus", {})
    if not isinstance(consensus, dict):
        return ConsensusConfig.preset_fast_default()

    # --- Primary ---
    # Try V9 nested first, then V8 flat
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

    # --- Prompts (use defaults; overridable via policy but rare) ---
    prompts = DEFAULT_PROMPTS

    # --- Numeric knobs ---
    timeout_s = int(consensus.get("primary_timeout_s", 60))
    timeout_s = max(5, min(300, timeout_s))
    max_repair = int(consensus.get("max_repair_attempts", 2))

    return ConsensusConfig(
        profile_name=f"policy:{policy.get('policy_id', 'unknown')}",
        primary=primary,
        validators=validators,
        prompts=prompts,
        primary_temperature=0.0,
        primary_timeout_s=timeout_s,
        max_repair_attempts=max_repair,
    )
