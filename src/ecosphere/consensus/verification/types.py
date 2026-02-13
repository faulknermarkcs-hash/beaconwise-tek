from __future__ import annotations

from typing import Dict, Literal, Optional, Any

from pydantic import BaseModel, ConfigDict, Field

Role = Literal[
    "public",
    "assistant",
    "nurse",
    "physician",
    "specialist",
    "attorney",
    "advisor",
    "engineer",
]


class VerificationContext(BaseModel):
    """Universal credential verification context (domain-agnostic).

    Fail-closed defaults: unverified public tier if any upstream verifier is missing/invalid.
    """
    verified: bool = Field(False, description="Whether credentials were successfully verified")
    role: Role = Field("public", description="Verified role or 'public'")
    role_level: int = Field(
        1,
        ge=1,
        le=5,
        description="Tier: 1=public, 2=mid-level pro, 3=licensed pro, 4=senior, 5=expert/specialist"
    )
    scope: Optional[str] = Field(None, description="Jurisdiction, specialty, department, etc.")
    expires_ts: Optional[int] = Field(None, description="Unix epoch seconds when verification expires")
    credential_hash: Optional[str] = Field(None, description="SHA-256 hash of credential identifier (never store raw IDs)")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Domain-specific claims")

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @property
    def is_public(self) -> bool:
        return (not self.verified) and self.role == "public" and self.role_level == 1

    @property
    def is_verified_pro(self) -> bool:
        """Verified and at least licensed professional tier."""
        return self.verified and self.role_level >= 3

    @property
    def requires_full_detail(self) -> bool:
        """Policy hook: unlock professional-grade detail/reasoning."""
        return self.verified and self.role_level >= 3

    def __str__(self) -> str:
        return f"VerificationContext(verified={self.verified}, role={self.role}, level={self.role_level})"


PUBLIC_CONTEXT = VerificationContext(verified=False, role="public", role_level=1)
