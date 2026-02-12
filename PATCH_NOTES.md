# BeaconWise v1.9.0 Patch Notes — Resilience Control Plane

## Rebranding
- Product: **BeaconWise Transparency Ecosphere Kernel (TEK)**
- Version: 1.9.0
- Kernel: v1.9.0

## V9 New Capabilities — Resilience Control Plane

### 1. Recovery Engine (`meta_validation/recovery_engine.py`)
- Deterministic plan selection with configurable scoring weights
- Budget enforcement (latency_ms_max, cost_usd_max)
- Tier-based penalties ({1: 0.00, 2: 0.05, 3: 0.12})
- Oscillation penalty for high-volatility + aggressive plans
- Circuit breaker integration via `excluded_plans` parameter
- 5 trigger conditions: TSI forecast drop, concentration high, system degraded, incident, concentration+TSI combined
- Tie-breaking: (score, predicted_independence_gain, -tier)

### 2. Circuit Breaker (`meta_validation/circuit_breaker.py`)
- Per-plan failure tracking (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Configurable failure threshold (default: 3 consecutive)
- Cooldown-based OPEN→HALF_OPEN transition
- Probe retry in HALF_OPEN with automatic re-open on failure
- Auditable state_snapshot() for EPACK logging
- Manual reset (single plan or all — break-glass)

### 3. TSI Tracker (`meta_validation/tsi_tracker.py`)
- Sliding-window aggregation (configurable, default 20 interactions)
- Exponential decay weighting (recent outcomes matter more)
- Status-based scoring: PASS=0.90, WARN=0.70, REFUSE=0.45, ERROR=0.30
- Validator agreement bonus/penalty
- Latency penalty, challenger-fired penalty
- Linear trend slope + 15-minute forecast
- Replaces hardcoded 0.85/0.55 TSI in kernel

### 4. Damping Stabilizer (`meta_validation/damping_stabilizer.py`)
- PID-inspired rollout velocity control (kp=0.5, ki=0.2, kd=0.1)
- Canary rollout percentage [0.15, 1.0]
- High concentration → bump rollout
- High oscillation → reduce rollout (yo-yo prevention)
- Cooldown enforcement between recovery actions
- Integral capping to prevent windup

### 5. Post-Recovery Verification (`meta_validation/post_recovery_verifier.py`)
- Closed-loop verification: did recovery actually improve TSI?
- Configurable min_tsi_improvement and max_tsi_degradation thresholds
- MVI check: governance_match validation from replay samples
- Critical TSI threshold detection
- Rollback recommendation with structured reasons

### 6. Meta-Validation Index (`meta_validation/mvi.py`)
- "Validate the validator" — governance pipeline self-check
- Three checks: replay stability, recovery consistency, TSI coherence
- Replay stability: compare two replay runs for divergence
- Recovery consistency: N-trial determinism verification
- TSI coherence: bounds checking, NaN/inf detection, impossible jump detection
- Weighted MVI score (0.0–1.0) with configurable pass threshold

### 7. Recovery EPACK Events (`meta_validation/recovery_events.py`)
- 6 event types: RECOVERY_TRIGGERED, RECOVERY_DECISION, RECOVERY_APPLIED, RECOVERY_VERIFIED, RECOVERY_ROLLBACK, CIRCUIT_BREAKER
- Wired to existing emit_stage_event infrastructure
- Hash-chained via prev_hash for audit continuity
- Persisted to EPACK JSONL + in-memory store

### 8. Policy Compiler (`meta_validation/policy_compiler.py`)
- Compiles resilience_policy YAML → ResilienceRuntime
- Parses tier_1/tier_2/tier_3 plan blocks with predicted metrics
- Builds all components: engine, damping, circuit breaker, TSI tracker, verifier
- Graceful degradation on parse errors

### 9. Policy Loader (`consensus/policy_loader.py`)
- Builds real ConsensusConfig from governance DSL
- Supports V8 flat and V9 nested provider shapes
- Maps YAML providers → ModelSpec objects
- Falls back to defaults for missing fields

### 10. Resilience Runtime (`meta_validation/resilience_runtime.py`)
- Orchestration wiring: connects all resilience components
- maybe_recover(): trigger check → engine decide → damping → circuit breaker
- verify_recovery(): post-recovery TSI check → circuit breaker feedback
- record_outcome(): feeds TSI tracker from interaction results
- dependency_metrics(): HHI concentration + density from provider weights

### 11. Replay Engine Restored + Enhanced
- V8 5-step verification restored: hash integrity, routing determinism, safety screening, profile consistency, build manifest
- V9 enhancement: Step 6 chain linkage (prev_hash continuity verification)
- replay_chain() now validates prev_hash across entire EPACK chain
- replay_summary() includes chain_link_rate metric

## V8 Capabilities (Preserved)

### Challenger Architecture (`src/ecosphere/challenger/`)
- ChallengerRules, ChallengePack schema, CHALLENGER_SYSTEM_PROMPT
- Trigger logic, disagreement scoring, parsing, arbitration, EPACK events
- Deterministic trigger conditions: high-stakes, disagreement > 0.22, gate hit, low evidence
- 5 deterministic arbitration rules

### Three-Role Consensus (7 adapters)
- Primary: OpenAI GPT / Validator: Grok/xAI / Challenger: Groq Compound Beta
- Adapter registry: openai, anthropic, mock, symbolic, retrieval, grok, groq

### FastAPI Production Backend (`api/main.py`)
- GET `/` — Health + version
- GET `/constitution`, `/schema/{name}`, `/metrics`, `/manifest`, `/policy`
- POST `/resilience/decide` — Recovery decision endpoint (V9)

### Governance DSL
- YAML policy loading with schema validation
- Deep-merge defaults including resilience_policy section
- Domain-specific overrides (healthcare, legal, financial)

## Enterprise Policy (V9)
- `policies/enterprise_v9.yaml` — Full resilience policy with 3 tiers of recovery plans
- TSI targets, budgets, dependency caps, triggers, scoring weights
- Damping configuration, adaptive tuning stubs, human override controls
- Audit configuration: log decisions, applied, verified; replay samples + MVI check

## Build Manifest v1.9.0
- 4 new V9 capability flags: v9_resilience_policy, v9_recovery_engine, v9_damping_stabilizer, v9_adaptive_tuning
- 10 V8 flags preserved
- 12 V5-V7 PR flags preserved

## Test Coverage
- Total: 355 tests across 34 test files
- New V9 tests: 63 tests across 6 new test files
- Circuit breaker: 12 tests
- TSI tracker: 11 tests
- Post-recovery verifier: 7 tests
- MVI: 7 tests
- Policy loader: 6 tests
- Recovery events: 7 tests
- Runtime integration: 8 tests
- Recovery engine: 6 tests
- Damping + policy compiler: 6 tests
- 354 passing (1 pre-existing fixture isolation in test_epack_reader — passes under pytest)

## Documentation
- `governance_schema.json` — Full JSON Schema including resilience_policy
- `enterprise/PILOT_PACKAGE.md` — Enterprise deployment guide
- All V7 docs preserved

## GitHub Demo Additions

### Reproducible Demo (`examples/run_demo.py`)
- Zero-dependency offline demonstration of core governance-kernel claims
- Requires no API keys: uses deterministic JSONL fixtures only
- Demonstrates three canonical replay outcomes in sequence:
  - `golden_epack_chain.jsonl` → VERIFIED
  - `tampered_epack_chain.jsonl` → TAMPER_DETECTED (prev_hash mismatch)
  - `drift_epack_chain.jsonl` → DRIFT (env fingerprint mismatch)
- Run with: `python examples/run_demo.py` or `make demo`

### Test Data (`testdata/`)
- `golden_epack_chain.jsonl` — 4-record valid chain; all hashes correct, chain intact
- `drift_epack_chain.jsonl` — same governance decisions, env_fingerprint changed to `stub-v2`
- `tampered_epack_chain.jsonl` — record 3 prev_hash corrupted to `fff...` to simulate tampering
- Fixtures are deterministic and reproducible; expected outputs are hardcoded in demo

### CI / Build (`Makefile`, `.github/workflows/ci.yml`)
- `make verify` — runs full pytest suite
- `make demo` — runs reproducible demo
- GitHub Actions: matrix test on Python 3.10 and 3.11; smoke tests + full suite
- `BW_DEMO_MODE=1` env flag suppresses live API calls during CI

### Documentation
- `docs/INDEX.md` — canonical reading order for regulators and enterprise evaluators
- `docs/CONFORMANCE_REPORT.md` — placeholder for future CI-generated conformance output
- `docs/FAQ.md` — Non-Goals section added
- `docs/REGULATOR_BRIEFING.md` — test count corrected (355 / 34 files)
- `docs/REGULATOR_LINT_REPORT.md` — all previously-open items resolved

## Test File Count Correction
- PATCH_NOTES previously stated "28 test files" — corrected to **34 test files**
