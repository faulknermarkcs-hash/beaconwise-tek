import json
import time

import pytest

from ecosphere.consensus.ledger.reader import clear_epack_events_for_test, get_recent_events
from ecosphere.consensus.verification.types import PUBLIC_CONTEXT
from ecosphere.consensus.verification.verifier_stub import verify_from_file


@pytest.fixture(autouse=True)
def _reset_epack_store():
    """Isolate in-memory EPACK between tests."""
    clear_epack_events_for_test()


def test_verifier_missing_file_returns_public_and_logs(tmp_path):
    epack = "epack-test"
    run_id = "run-test"

    missing_file = tmp_path / "does_not_exist.json"

    ctx = verify_from_file(
        user_id="any@example.com",
        credential_file=str(missing_file),
        epack=epack,
        run_id=run_id,
    )

    assert ctx == PUBLIC_CONTEXT

    events = get_recent_events(epack_id=epack, stage_prefix="tecl.verification.", limit=10)
    assert any(e["stage"] == "tecl.verification.missing_file" for e in events)


def test_verifier_user_not_found_returns_public_and_logs(tmp_path):
    epack = "epack-test"
    run_id = "run-test"

    cred_file = tmp_path / "mock_credentials.json"
    cred_file.write_text(json.dumps({"known@example.com": {"role": "physician", "role_level": 3, "verified": True}}))

    ctx = verify_from_file(
        user_id="unknown@example.com",
        credential_file=str(cred_file),
        epack=epack,
        run_id=run_id,
    )

    assert ctx == PUBLIC_CONTEXT

    events = get_recent_events(epack_id=epack, stage_prefix="tecl.verification.", limit=10)
    assert any(e["stage"] == "tecl.verification.user_not_found" for e in events)


def test_verifier_expired_returns_public_and_logs(tmp_path):
    epack = "epack-test"
    run_id = "run-test"

    cred_file = tmp_path / "mock_credentials.json"
    cred_file.write_text(
        json.dumps(
            {
                "expired@example.com": {
                    "role": "physician",
                    "role_level": 3,
                    "verified": True,
                    "expires_ts": int(time.time()) - 60,
                    "scope": "test",
                }
            }
        )
    )

    ctx = verify_from_file(
        user_id="expired@example.com",
        credential_file=str(cred_file),
        epack=epack,
        run_id=run_id,
    )

    assert ctx == PUBLIC_CONTEXT

    events = get_recent_events(epack_id=epack, stage_prefix="tecl.verification.", limit=10)
    assert any(e["stage"] == "tecl.verification.expired" for e in events)


def test_verifier_success_returns_context_and_logs(tmp_path):
    epack = "epack-test"
    run_id = "run-test"

    cred_file = tmp_path / "mock_credentials.json"
    cred_file.write_text(
        json.dumps(
            {
                "physician@example.com": {
                    "role": "physician",
                    "role_level": 3,
                    "verified": True,
                    "scope": "general medicine",
                    "expires_ts": int(time.time()) + 60,
                    "credential_hash": "sha256:mock",
                    "extra": {"board_certified": ["internal medicine"]},
                }
            }
        )
    )

    ctx = verify_from_file(
        user_id="physician@example.com",
        credential_file=str(cred_file),
        epack=epack,
        run_id=run_id,
    )

    assert ctx.verified is True
    assert ctx.role == "physician"
    assert ctx.role_level == 3
    assert ctx.scope == "general medicine"

    events = get_recent_events(epack_id=epack, stage_prefix="tecl.verification.", limit=10)
    assert any(e["stage"] == "tecl.verification.success" for e in events)
