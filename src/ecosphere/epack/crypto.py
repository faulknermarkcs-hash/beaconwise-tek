from __future__ import annotations

import hashlib
import hmac
import os


def _key_bytes() -> bytes:
    # NOTE: In production, set EPACK_SIGNING_KEY to a high-entropy secret.
    # This key never leaves the server; signatures enable tamper detection
    # for replay verification.
    return os.getenv("EPACK_SIGNING_KEY", "dev-key").encode("utf-8")


def sign_payload_hash(payload_hash: str) -> str:
    """Create an HMAC-SHA256 signature over a 64-hex payload hash."""
    return hmac.new(_key_bytes(), payload_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(payload_hash: str, signature: str) -> bool:
    """Constant-time verification for replay checks."""
    expected = sign_payload_hash(payload_hash)
    return hmac.compare_digest(expected, signature)
