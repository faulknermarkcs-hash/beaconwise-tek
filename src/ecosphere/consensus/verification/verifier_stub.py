# src/ecosphere/consensus/verification/verifier_stub.py
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional

from ecosphere.consensus.verification.types import VerificationContext, PUBLIC_CONTEXT
from ecosphere.consensus.ledger.hooks import emit_stage_event


def verify_from_file(
    *,
    user_id: str,
    credential_file: str = "mock_credentials.json",
    epack: Optional[str] = None,
    run_id: Optional[str] = None,
) -> VerificationContext:
    """
    Dev-only credential verifier.

    Looks up user_id in a JSON file, returning a VerificationContext.
    Falls back to PUBLIC_CONTEXT on any failure.
    """
    epack_id = epack or "dev-epack"
    rid = run_id or "dev-run"
    fp = Path(credential_file)

    if not fp.exists():
        emit_stage_event(epack=epack_id, run_id=rid, stage="tecl.verification.missing_file", payload={"file": str(fp)})
        return PUBLIC_CONTEXT

    try:
        creds_db: Dict[str, Dict] = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        emit_stage_event(epack=epack_id, run_id=rid, stage="tecl.verification.load_error", payload={"file": str(fp), "error": repr(e)})
        return PUBLIC_CONTEXT

    user_data = creds_db.get(user_id)
    if not user_data:
        emit_stage_event(epack=epack_id, run_id=rid, stage="tecl.verification.user_not_found", payload={"user_id": user_id})
        return PUBLIC_CONTEXT

    expires_ts = user_data.get("expires_ts")
    if expires_ts and int(expires_ts) < int(time.time()):
        emit_stage_event(epack=epack_id, run_id=rid, stage="tecl.verification.expired", payload={"user_id": user_id, "expires_ts": expires_ts})
        return PUBLIC_CONTEXT

    verification = VerificationContext(
        verified=bool(user_data.get("verified", False)),
        role=str(user_data.get("role", "public")),
        role_level=int(user_data.get("role_level", 1)),
        scope=user_data.get("scope"),
        expires_ts=int(expires_ts) if expires_ts else None,
        credential_hash=user_data.get("credential_hash"),
        extra=user_data.get("extra", {}),
    )

    emit_stage_event(
        epack=epack_id,
        run_id=rid,
        stage="tecl.verification.success",
        payload={"user_id": user_id, "role": verification.role, "role_level": verification.role_level, "verified": verification.verified, "scope": verification.scope},
    )
    return verification
