# Changelog

All notable changes to BeaconWise are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.9.0] — February 2026

### Added — V9 Resilience Control Plane

Nine new modules in `src/ecosphere/meta_validation/` that close the gap between anomaly detection and recovery action:

- **TSI Tracker** (`tsi_tracker.py`) — sliding-window Trust-Signal Index with exponential decay weighting, outcome scoring (PASS/WARN/REFUSE/ERROR), and 15-minute linear forecast
- **Recovery Engine** (`recovery_engine.py`) — deterministic plan selection over tiered recovery policy with budget enforcement and oscillation penalty
- **Circuit Breaker** (`circuit_breaker.py`) — per-plan failure tracking with CLOSED → OPEN → HALF_OPEN → CLOSED state machine; auditable state snapshots for EPACK logging
- **Damping Stabilizer** (`damping_stabilizer.py`) — PID-inspired rollout velocity control preventing yo-yo recovery oscillation
- **Post-Recovery Verifier** (`post_recovery_verifier.py`) — closed-loop verification: confirms TSI improved after recovery; recommends rollback with structured reasons if not
- **Meta-Validation Index** (`mvi.py`) — "validate the validator"; three checks (replay stability, recovery consistency, TSI coherence); pass threshold 0.80
- **Recovery EPACK Events** (`recovery_events.py`) — 6 event types hash-chained into EPACK audit continuity
- **Policy Compiler** (`policy_compiler.py`) — compiles `resilience_policy` YAML to ResilienceRuntime; supports V8 flat and V9 nested provider shapes
- **Resilience Runtime** (`resilience_runtime.py`) — orchestration: trigger check, plan decision, damping, circuit breaker, outcome feedback, dependency metrics

### Added — Test Documentation

- `SMOKE_TEST.md` — 5-minute verification (5 canonical tests)
- `TEST_SUITE_OVERVIEW.md` — test categories, running instructions, core properties
- `TEST_RESULTS_TEMPLATE.md` — standardized failure reporting template
- `FAQ.md` — common questions with explicit Non-Goals section

### Added — Compliance and Enterprise Documentation

- `docs/INDEX.md` — canonical reading order for regulators and enterprise evaluators
- `docs/CONFORMANCE_REPORT.md` — conformance baseline and manual generation instructions
- `enterprise/PILOT_PACKAGE.md` — full 30-day enterprise pilot guide with success criteria, evidence artifact table, and evaluation checklist
- `docs/REGULATOR_LINT_REPORT.md` — documentation quality audit (0 broken links, 0 contradictions)

### Added — GitHub Release Infrastructure

- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1, modified for governance mission
- `CONTRIBUTING.md` — contribution scope, development setup, PR requirements, spec change process
- `SECURITY.md` — vulnerability disclosure process with governance-kernel-specific severity classification
- `CHANGELOG.md` (this file)
- `Makefile` — `make verify` and `make demo`
- `.github/workflows/ci.yml` — matrix CI on Python 3.10 and 3.11

### Added — Reproducible Demo

- `examples/run_demo.py` — zero-dependency offline demo; no API keys required
- `testdata/golden_epack_chain.jsonl` — 4-record valid EPACK chain
- `testdata/drift_epack_chain.jsonl` — same decisions, changed env fingerprint → DRIFT
- `testdata/tampered_epack_chain.jsonl` — corrupted prev_hash → TAMPER_DETECTED

### Changed

- `pyproject.toml` — dependencies now fully declared; `[dev]` extras defined (`pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`); project URLs and classifiers added
- `README.md` — badges added (CI, license, Python, tests); venv instructions; demo and documentation sections surfaced before license
- Removed `setup.cfg` (redundant with `pyproject.toml`)

### Fixed

- `docs/REGULATOR_BRIEFING.md` — test count corrected from "430+" to "355 passing tests across 34 files"

### Test Suite

- **355 tests** across **34 files**, **468 parametrized assertions**
- 63 new V9 tests (circuit breaker, TSI tracker, post-recovery verifier, MVI, policy loader, recovery events, runtime integration, recovery engine, damping + policy compiler)
- 1 known fixture isolation skip (`test_epack_reader`) — passes under standard `pytest`

---

## [1.8.0] — January 2026

### Added — V8 Challenger and Multi-Provider Consensus

- Challenger layer: independent adversarial review of primary + validator consensus
- Multi-provider consensus pipeline: Primary, Validator, Challenger adapters
- 7 provider adapters (OpenAI, Anthropic, Grok/xAI, Groq, symbolic, mock, retrieval)
- V8 flat provider configuration schema
- Consensus arbitration with agreement scoring and escalation

### Added — EPACK Chain

- Hash-chained audit records (SHA-256)
- Tamper detection via chain verification
- Governance receipts (HMAC-signed)
- Replay engine: 6-step deterministic replay with VERIFIED / DRIFT / TAMPER_DETECTED classification

---

## [1.7.0] — December 2025

### Added — Constitutional Governance

- `CONSTITUTION.md` and machine-readable `CONSTITUTION` schema
- 13 governance invariants including determinism, anti-capture, audit permanence
- Constitutional routing: decisions traceable to invariants
- DSL loader and schema validation
- Safety screening (two-stage: pattern matching + Bayesian belief tracking)
- Role-based content tiering for regulated domains

### Test Suite

- 292 tests across 28 files at v1.7.0

---

## [Pre-1.7] — Earlier Versions

Earlier development phases (PR1–PR5.3) established the core governance pipeline: input vectorization, belief tracking, routing (BLOCK / DEFER / CONFIRM / PLAN / PROCEED), evidence validation gate, and the initial EPACK logging infrastructure. These phases are documented in `PATCH_NOTES.md`.

---

[1.9.0]: https://github.com/beaconwise-tek/beaconwise/releases/tag/v1.9.0
[1.8.0]: https://github.com/beaconwise-tek/beaconwise/releases/tag/v1.8.0
[1.7.0]: https://github.com/beaconwise-tek/beaconwise/releases/tag/v1.7.0
