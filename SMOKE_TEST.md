# Smoke Test — 5-Minute Verification

This is the fastest path to validate basic BeaconWise governance integrity.

## Run

```bash
# 1) Constitutional Integrity
pytest tests/test_v7_governance.py::test_constitution_invariants_cannot_be_overridden -v

# 2) Basic Replay Roundtrip
pytest tests/test_kernel_replay_roundtrip.py::test_simple_input_output_replay -v

# 3) EPACK Chain Integrity
pytest tests/test_epack_chain_integrity.py::test_append_only_hash_chain -v

# 4) Challenger Escalation
pytest tests/test_v8_challenger.py::test_challenger_can_escalate_dispute -v

# 5) V9 Resilience / Circuit Breaker
pytest tests/test_v9_circuit_breaker.py::test_circuit_breaker_activates_on_corruption -v
```

## Expected Result

All 5 should pass.

If any fail:
1. Stop and record the first failure
2. Fill out **TEST_RESULTS_TEMPLATE.md**
3. Include the full traceback and your environment details
