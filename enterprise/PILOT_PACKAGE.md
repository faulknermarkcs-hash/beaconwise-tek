[PILOT_PACKAGE.md](https://github.com/user-attachments/files/25276598/PILOT_PACKAGE.md)
# BeaconWise Enterprise Pilot Deployment Package

**Product:** BeaconWise Transparency Ecosphere Kernel (TEK)  
**Version:** 1.9.0  
**Audience:** Enterprise evaluators, pilot program leads, IT/compliance teams  
**Status:** Production-ready pilot configuration  
**Date:** February 2026

---

## What This Package Contains

This package provides everything needed to deploy BeaconWise as an internal advisory governance layer, validate its core invariants, and generate evidence for compliance or audit use cases.

**Recommended pilot scope:** Internal AI-assisted tool (document review, policy drafting, internal search) with a defined user group (5–50 users) and a 30-day evaluation window.

---

## Pilot Success Criteria

| Metric | Target | How Measured |
|--------|--------|--------------|
| Hallucination drop | ≥ 30% reduction vs. ungoverned baseline | EPACK evidence validation gate rejections |
| Routing determinism | ≥ 90% identical routing on repeated inputs | Replay engine VERIFIED rate |
| Validator independence | Independence score ≥ 0.70 | TSI Tracker `dependency_metrics()` HHI output |
| Audit completeness | 100% of governed interactions produce EPACK records | EPACK chain continuity check |
| Replay fidelity | ≥ 95% VERIFIED (not DRIFT or TAMPER_DETECTED) | `replay_summary()` chain_link_rate |
| MVI health | MVI score ≥ 0.80 | Meta-Validation Index weekly snapshot |

---

## Deployment Steps

### 1. Prerequisites

```bash
# Runtime
Python 3.11+
PostgreSQL 14+ (for EPACK persistence) OR file-based JSONL (dev/pilot)
Docker (optional, recommended for isolated deployment)

# API Keys (at least one required for live testing)
OPENAI_API_KEY     # Primary provider
ANTHROPIC_API_KEY  # Secondary validator (recommended)
# OR use mock adapters for isolated evaluation
```

### 2. Install

```bash
git clone https://github.com/beaconwise-tek/beaconwise
cd beaconwise
pip install -r requirements.txt

# Verify installation
pytest tests/ -v --tb=short
# Expected: 355 passing, 1 known fixture-isolation skip (test_epack_reader)
```

### 3. Smoke Test (5 Minutes)

Run the five canonical smoke tests before any configuration:

```bash
pytest tests/test_v7_governance.py::test_constitution_invariants_cannot_be_overridden -v
pytest tests/test_kernel_replay_roundtrip.py::test_simple_input_output_replay -v
pytest tests/test_epack_chain_integrity.py::test_append_only_hash_chain -v
pytest tests/test_v8_challenger.py::test_challenger_can_escalate_dispute -v
pytest tests/test_v9_circuit_breaker.py::test_circuit_breaker_activates_on_corruption -v
```

All five must pass. If any fail, stop and file a bug with `TEST_RESULTS_TEMPLATE.md`.

### 4. Configure Policy

Copy and edit the enterprise policy template:

```bash
cp policies/enterprise_v9.yaml policies/pilot.yaml
```

Key configuration sections in `pilot.yaml`:

```yaml
# Validator configuration — minimum 2 for independence requirement
providers:
  primary:
    adapter: openai
    model: gpt-4o
  validator:
    adapter: anthropic
    model: claude-opus-4-5-20250929
  challenger:
    adapter: mock        # Use mock if budget-constrained

# Resilience targets
resilience_policy:
  targets:
    tsi_target: 0.75     # Raise to 0.82 for high-stakes domains
    tsi_critical: 0.55   # Below this: circuit breaker activates
  budgets:
    latency_ms_max: 800
    cost_usd_max: 0.50

# Domain-specific overrides (remove unused domains)
domain_overrides:
  healthcare:
    tsi_target: 0.85
    require_credential_verification: true
```

### 5. Launch

```bash
# Development / pilot (file-based EPACK storage)
python app.py

# Production (Docker + Postgres)
docker-compose -f docker/docker-compose.yml up

# API health check
curl http://localhost:8000/
# Expected: {"status": "ok", "version": "1.9.0", "kernel": "TEK"}
```

### 6. Verify Governance Is Active

```bash
# Check constitution is loaded
curl http://localhost:8000/constitution

# Check build manifest (V9 flags should be true)
curl http://localhost:8000/manifest | python3 -m json.tool | grep v9

# Check current policy
curl http://localhost:8000/policy
```

---

## Generating Pilot Evidence

### Weekly Audit Report

```bash
# Replay the last 7 days of EPACK records
python -c "
from src.ecosphere.replay.engine import ReplayEngine
engine = ReplayEngine()
summary = engine.replay_summary(days=7)
print(summary)
"
# Output: {verified: N, drift: N, tamper_detected: 0, chain_link_rate: 0.99+}
```

### Resilience Health Snapshot

```bash
curl http://localhost:8000/metrics
# Returns: TSI current, TSI forecast, MVI score, circuit breaker states, dependency HHI
```

### EPACK Chain Integrity Check

```bash
python -c "
from src.ecosphere.epack.chain import EPACKChain
chain = EPACKChain.load()
result = chain.verify_integrity()
print('Chain intact:', result.passed)
print('Records:', result.record_count)
print('Earliest:', result.earliest_timestamp)
"
```

---

## Pilot Evaluation Checklist

**Week 1 — Baseline**
- [ ] Smoke test passes (all 5)
- [ ] Constitution loaded and visible via API
- [ ] V9 capability flags confirmed in manifest
- [ ] First EPACK records generated and chain verified
- [ ] Routing determinism confirmed (run same input 3x, verify identical routing)

**Week 2 — Coverage**
- [ ] All five routing outcomes exercised (BLOCK, DEFER, CONFIRM, PLAN, PROCEED)
- [ ] At least one Challenger escalation triggered (inject disagreement scenario)
- [ ] TSI tracker producing 15-min forecasts
- [ ] MVI score ≥ 0.80 baseline established

**Week 3 — Resilience**
- [ ] Inject a circuit-breaker scenario (repeat failures on one plan)
- [ ] Confirm circuit breaker OPEN state appears in EPACK records
- [ ] Recovery action triggered and verified via Post-Recovery Verifier
- [ ] Replay of Week 1–2 EPACK records: confirm VERIFIED rate ≥ 95%

**Week 4 — Evidence Package**
- [ ] Full audit report generated (replay_summary for 30 days)
- [ ] Compliance mapping reviewed against target regulatory framework
- [ ] MVI weekly snapshots documented (target: all ≥ 0.80)
- [ ] REGULATOR_LINT_REPORT.md reviewed; any open items addressed
- [ ] Pilot report drafted using evidence collected above

---

## Evidence Artifacts for Compliance Purposes

The following artifacts are available at the end of a successful pilot:

| Artifact | Source | Regulatory Relevance |
|----------|--------|---------------------|
| EPACK chain export (JSONL) | `epack/chain.py` | EU AI Act Art. 12 automatic logging |
| Replay summary report | `replay/engine.py replay_summary()` | NIST AI RMF MEASURE 2.5 testability |
| Governance receipts (HMAC-signed) | Kernel routing certificates | Third-party audit verification |
| MVI weekly snapshots | `meta_validation/mvi.py` | ISO/IEC 42001 Cl. 9.2 internal audit |
| Circuit breaker state log | EPACK CIRCUIT_BREAKER events | Incident documentation |
| Constitution version record | `docs/CONSTITUTION.md` + hash | Governance policy documentation |
| Build manifest | `GET /manifest` | Software version traceability |

---

## Known Constraints

- **EPACK reader fixture isolation:** One test (`test_epack_reader`) has a known fixture isolation issue when run in certain parallel test environments; it passes under standard `pytest`. This does not affect runtime behavior.
- **Validator consensus requires ≥ 2 live adapters** for independence score to exceed minimum. Pilot configurations using only mock adapters will report independence = 0.0 (expected; not a defect).
- **Recovery engine requires resilience policy YAML** to be present and parseable at startup. Missing policy results in graceful degradation (kernel operates without recovery capability, logged explicitly).
- **Cost budgets** in enterprise_v9.yaml are set for evaluation; adjust for production load.

---

## Support and Escalation

- Technical issues: Use `TEST_RESULTS_TEMPLATE.md` for structured bug reports
- Architecture questions: See `docs/ARCHITECTURE.md` and `docs/FAQ.md`
- Compliance questions: See `docs/COMPLIANCE_MAPPING.md` and `docs/REGULATOR_BRIEFING.md`
- Source: Apache 2.0 — fork, audit, and modify freely

---

*BeaconWise is governance infrastructure. It provides the process integrity layer that makes AI systems auditable. Compliance, quality, and safety outcomes depend on how deployers integrate governance infrastructure into their broader organizational and technical context.*
