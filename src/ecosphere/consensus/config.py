# src/ecosphere/consensus/config.py
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict

from ecosphere.consensus.verification.types import VerificationContext


class ARU(str, Enum):
    ANSWER = "ANSWER"
    VERIFY = "VERIFY"
    REFUSE = "REFUSE"
    CONSENSUS = "CONSENSUS"


class ModelSpec(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    family: Optional[str] = None
    timeout_s: Optional[int] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PromptBundle(BaseModel):
    # Minimal templates: output must be JSON matching PrimaryOutput
    primary_template: str
    repair_template: str

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DebateConfig(BaseModel):
    critic_model: ModelSpec
    defender_model: ModelSpec
    synthesizer_model: ModelSpec

    model_config = ConfigDict(extra="forbid")


class ConsensusConfig(BaseModel):
    profile_name: Optional[str] = None
    primary: ModelSpec
    validators: List[ModelSpec] = Field(default_factory=list)
    primary_temperature: float = Field(0.0, ge=0.0, le=2.0)
    primary_timeout_s: int = Field(60, ge=5, le=300)
    max_repair_attempts: int = Field(2, ge=0, le=5)
    prompts: PromptBundle

    # Future hooks (kept for forward compatibility)
    enable_debate: bool = False
    debate: Optional[DebateConfig] = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # -----------------------------
    # Presets
    # -----------------------------
    @staticmethod
    def preset_fast(*, prompts: PromptBundle, primary: ModelSpec, validators: List[ModelSpec]) -> "ConsensusConfig":
        return ConsensusConfig(
            profile_name="FAST",
            prompts=prompts,
            primary=primary,
            validators=validators[:1],
            primary_temperature=0.0,
            primary_timeout_s=35,
            max_repair_attempts=1,
            enable_debate=False,
            debate=None,
        )

    @staticmethod
    def preset_high_assurance(*, prompts: PromptBundle, primary: ModelSpec, validators: List[ModelSpec]) -> "ConsensusConfig":
        return ConsensusConfig(
            profile_name="HIGH_ASSURANCE",
            prompts=prompts,
            primary=primary,
            validators=validators[:2] if len(validators) >= 2 else validators,
            primary_temperature=0.0,
            primary_timeout_s=60,
            max_repair_attempts=2,
            enable_debate=False,
            debate=None,
        )

    @staticmethod
    def preset_consensus(*, prompts: PromptBundle, primary: ModelSpec, validators: List[ModelSpec], debate: Optional[DebateConfig]=None) -> "ConsensusConfig":
        return ConsensusConfig(
            profile_name="CONSENSUS",
            prompts=prompts,
            primary=primary,
            validators=validators[:3] if len(validators) >= 3 else validators,
            primary_temperature=0.0,
            primary_timeout_s=75,
            max_repair_attempts=2,
            enable_debate=bool(debate),
            debate=debate,
        )

    @staticmethod
    def preset_for_verification(
        *,
        prompts: PromptBundle,
        primary: ModelSpec,
        validators: List[ModelSpec],
        verification: VerificationContext,
        debate: Optional[DebateConfig] = None,
    ) -> "ConsensusConfig":
        if (not verification.verified) or verification.role_level <= 1:
            return ConsensusConfig.preset_fast(prompts=prompts, primary=primary, validators=validators)
        if verification.role_level == 2:
            return ConsensusConfig.preset_high_assurance(prompts=prompts, primary=primary, validators=validators)
        return ConsensusConfig.preset_consensus(prompts=prompts, primary=primary, validators=validators, debate=debate)

    # -----------------------------
    # Default wrappers for tests/demos
    # -----------------------------
    @staticmethod
    def preset_fast_default() -> "ConsensusConfig":
        return ConsensusConfig.preset_fast(prompts=DEFAULT_PROMPTS, primary=DEFAULT_PRIMARY, validators=DEFAULT_VALIDATORS)

    @staticmethod
    def preset_high_assurance_default() -> "ConsensusConfig":
        return ConsensusConfig.preset_high_assurance(prompts=DEFAULT_PROMPTS, primary=DEFAULT_PRIMARY, validators=DEFAULT_VALIDATORS)

    @staticmethod
    def preset_consensus_default(debate: Optional[DebateConfig] = None) -> "ConsensusConfig":
        return ConsensusConfig.preset_consensus(prompts=DEFAULT_PROMPTS, primary=DEFAULT_PRIMARY, validators=DEFAULT_VALIDATORS, debate=debate)

    @staticmethod
    def preset_for_verification_default(verification: VerificationContext) -> "ConsensusConfig":
        return ConsensusConfig.preset_for_verification(
            prompts=DEFAULT_PROMPTS, primary=DEFAULT_PRIMARY, validators=DEFAULT_VALIDATORS, verification=verification
        )


DEFAULT_PRIMARY = ModelSpec(provider="anthropic", model="claude-3-5-sonnet-20241022", family="claude")
DEFAULT_VALIDATORS = [
    ModelSpec(provider="openai", model="gpt-4o", family="gpt"),
    ModelSpec(provider="anthropic", model="claude-3-opus-20240229", family="claude"),
]

DEFAULT_PROMPTS = PromptBundle(
    primary_template=(
        "You are the Transparency Ecosphere Consensus Layer primary model.\n"
        "Return ONLY valid JSON for PrimaryOutput with fields: run_id, epack, aru, answer, reasoning_trace, claims, overall_confidence, uncertainty_flags, next_step.\n"
        "Use these context variables: VERIFIED={VERIFIED} ROLE={ROLE} ROLE_LEVEL={ROLE_LEVEL} SCOPE={SCOPE}.\n"
        "RUN_ID={RUN_ID} EPACK={EPACK} ARU={ARU}.\n"
        "User query:\n{USER_QUERY}\n"
    ),
    repair_template=(
        "The following text was supposed to be JSON for PrimaryOutput, but it was invalid.\n"
        "Rewrite it as valid JSON ONLY, matching PrimaryOutput exactly.\n"
        "RUN_ID={RUN_ID} EPACK={EPACK} ARU={ARU}.\n"
        "Invalid text:\n{BAD_TEXT}\n"
    ),
)
