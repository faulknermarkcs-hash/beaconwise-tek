from __future__ import annotations

import secrets

from ecosphere.utils.stable import stable_hash


def new_session_secret() -> str:
    return secrets.token_hex(16)


def derive_scoped(session_id: str, session_secret: str, purpose: str) -> str:
    return stable_hash({"session_id": session_id, "session_secret": session_secret, "purpose": purpose})[:16]
