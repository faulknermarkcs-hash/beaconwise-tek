# BeaconWise Test Suite Overview

This repository’s test suite validates **governance infrastructure correctness** — not “Is the AI safe?”
BeaconWise is a governance kernel: these tests verify that the kernel’s **deterministic routing**, **evidence validation**,
**tamper-evident audit continuity (EPACK)**, and **replay/verification** behave exactly as specified.

> If you are a tester: start with **SMOKE_TEST.md**.

---

## Test Categories

- **Constitutional Invariants** (`test_v7_governance.py`, `test_gates_full.py`)
  - Ensures governance rules are enforced and cannot be silently overridden

- **Replay Integrity** (`test_replay_engine.py`, `test_replay_package.py`, `test_kernel_replay_roundtrip.py`)
  - Verifies deterministic reconstruction and explicit divergence classification

- **Evidence Chain (EPACK)** (`test_epack_chain_integrity.py`, `test_redaction_epack_provenance.py`, `test_epack_reader*.py`)
  - Validates append-only hash chaining, tamper detection, and provenance behavior

- **Validator Consensus + Challenger Oversight** (`test_consensus_orchestrator.py`, `test_consensus_config.py`, `test_v8_challenger.py`)
  - Tests independent oversight mechanisms and escalation behavior

- **Resilience + Recovery** (`test_v9_resilience*.py`, `test_v9_recovery_events.py`, `test_v9_post_recovery.py`, `test_v9_circuit_breaker.py`)
  - Ensures graceful degradation, recovery behavior, and circuit breaker activation on corruption

- **Security Utilities + Sandboxing** (`test_pr510_tool_sandbox.py`, `test_safe_calc_hardened.py`, `test_hash_agility.py`, `test_pr6_hardening.py`)
  - Validates hardened components, sandbox behavior, and integrity primitives

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run key categories (examples)
pytest tests/test_v7_governance.py tests/test_gates_full.py -v
pytest tests/test_replay_*.py -v
pytest tests/test_epack_*.py -v
pytest tests/test_v8_challenger.py tests/test_consensus_*.py -v
pytest tests/test_v9_*.py -v

# Run with coverage (if configured)
pytest --cov=src/ecosphere tests/ -v
```

---

## What We’re Testing For (Core Properties)

- **Deterministic routing**
  - Same inputs + same system state ⇒ same governance decisions

- **Evidence validation**
  - No unvalidated output can be delivered through governance paths

- **Cryptographic chain integrity**
  - EPACK audit chains are tamper-evident and append-only

- **Validator independence + oversight**
  - No single-point control; challenger escalation remains functional

- **Failure transparency**
  - No silent “permissive fallback” under uncertainty, corruption, or partial failure

- **Replay accuracy**
  - Historical reconstruction yields explicit outcomes (e.g., VERIFIED / DRIFT / TAMPER_DETECTED)

---

## Notes for Testers

- If you encounter failures, please use **TEST_RESULTS_TEMPLATE.md** to report environment details and reproduction steps.
- If running in constrained environments (CI, minimal containers), prefer the **SMOKE_TEST.md** path first.
