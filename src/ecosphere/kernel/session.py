from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Set

from ecosphere.tsv.state import TSVState


class Profile(str, Enum):
    A_FAST = "A_FAST"
    A_STANDARD = "A_STANDARD"
    A_HIGH_ASSURANCE = "A_HIGH_ASSURANCE"


class PendingGate(str, Enum):
    NONE = "NONE"
    REFLECT_CONFIRM = "REFLECT_CONFIRM"
    SCAFFOLD_APPROVE = "SCAFFOLD_APPROVE"


@dataclass
class StateTrace:
    state_before: str
    state_after: str
    event: str
    gate: str
    interaction: int
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PendingGateState:
    gate: str = PendingGate.NONE.value
    created_at_interaction: int = 0
    expires_after_turns: int = 3

    payload: Dict[str, Any] = field(default_factory=dict)
    payload_hash: str = ""

    confirm_token: str = ""
    require_token_binding: bool = False
    nonce: str = ""
    consumed_nonces: Set[str] = field(default_factory=set)

    prompt_cache_hash: str = ""

    def is_active(self) -> bool:
        return self.gate != PendingGate.NONE.value

    def is_expired(self, interaction_count: int) -> bool:
        if not self.is_active():
            return False
        return (interaction_count - self.created_at_interaction) >= int(self.expires_after_turns)


@dataclass
class SessionState:
    session_id: str
    interaction_count: int = 0
    current_profile: str = Profile.A_STANDARD.value

    pending_gate: PendingGateState = field(default_factory=PendingGateState)
    traces: List[StateTrace] = field(default_factory=list)

    reflect_confirmed: bool = False
    scaffold_approved: bool = False

    workflow_queue: List[str] = field(default_factory=list)

    tsv: TSVState = field(default_factory=TSVState)

    epack_seq: int = 0
    epack_prev_hash: str = "GENESIS"
    epacks: List[Dict[str, Any]] = field(default_factory=list)

    last_persisted_seq: int = 0

    # PR6 helpers
    last_failure_interaction: int = 0
