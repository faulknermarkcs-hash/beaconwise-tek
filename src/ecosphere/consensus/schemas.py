# src/ecosphere/consensus/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


class PrimaryOutput(BaseModel):
    """
    Primary TE-CL output schema.

    NOTE: This is intentionally lightweight for the kernel demo.
    Fields are chosen to support deterministic parsing + scope gating.
    """
    run_id: str
    epack: str
    aru: str = Field(..., description="ARU label (e.g., ANSWER)")
    answer: str
    reasoning_trace: List[str] = Field(default_factory=list)
    claims: List[Dict[str, Any]] = Field(default_factory=list)
    overall_confidence: float = Field(0.5, ge=0.0, le=1.0)
    uncertainty_flags: List[str] = Field(default_factory=list)
    next_step: Optional[str] = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ValidatorOutput(BaseModel):
    run_id: str
    epack: str
    aru: str
    verdict: Literal["AGREE", "DISAGREE", "UNCERTAIN"] = "UNCERTAIN"
    notes: str = ""
    confidence: float = Field(0.5, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SynthesizerOutput(BaseModel):
    run_id: str
    epack: str
    aru: str
    answer: str
    reasoning_trace: List[str] = Field(default_factory=list)
    overall_confidence: float = Field(0.5, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
