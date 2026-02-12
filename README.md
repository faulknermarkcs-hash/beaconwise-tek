# BeaconWise v1.9.0 — Enterprise Governance Kernel

**By The Transparency Ecosphere**

[![CI](https://github.com/beaconwise-tek/beaconwise/actions/workflows/ci.yml/badge.svg)](https://github.com/beaconwise-tek/beaconwise/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-355%20passing-brightgreen.svg)](tests/)
[![Governance](https://img.shields.io/badge/governance-auditable-informational.svg)](docs/ARCHITECTURE.md)

Deterministic AI governance infrastructure with multi-model consensus,
adversarial review, and closed-loop resilience recovery.

## Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────────┐
│  Kernel Engine (kernel/engine.py)           │
│  ├── Input Vector → Safety → Routing        │
│  ├── Consensus Pipeline (V8)                │
│  │   ├── Primary (OpenAI GPT)               │
│  │   ├── Validator (Grok/xAI, Groq)        │
│  │   └── Challenger (adversarial critique)   │
│  └── Resilience Loop (V9)                   │
│      ├── TSI Tracker (sliding window)        │
│      ├── Recovery Engine (plan selection)    │
│      ├── Damping Stabilizer (PID rollout)   │
│      ├── Circuit Breaker (failure tracking) │
│      └── Post-Recovery Verifier (closed-loop)│
├─────────────────────────────────────────────┤
│  EPACK Audit Chain (cryptographic)          │
│  ├── Governance decisions                   │
│  ├── Recovery events                        │
│  └── Replay verification                   │
└─────────────────────────────────────────────┘
```

## Quick Start

```bash
# (recommended) create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# install (dependencies are declared in pyproject.toml)
pip install -e .

# run the Streamlit app
streamlit run app.py

# or run the API (FastAPI)
uvicorn api.main:app --reload --port 8000

# run tests
pytest -q tests
```


## Key Components

| Module | Purpose |
|--------|---------|
| `kernel/engine.py` | Main governance pipeline |
| `consensus/` | Multi-model consensus with 7 adapters |
| `challenger/` | Adversarial governance pressure |
| `meta_validation/` | Resilience control plane (V9) |
| `replay/engine.py` | Deterministic replay verification (6-step) |
| `governance/` | DSL loader, schema validation, constitution |
| `epack/` | Audit chain with hash linkage |
| `safety/` | Two-stage safety screening |

## Resilience Control Plane (V9)

The resilience system forms a closed loop:

1. **TSI Tracker** monitors interaction outcomes (pass/refuse/error, agreement, latency)
2. **Recovery Engine** evaluates trigger conditions and selects recovery plans
3. **Damping Stabilizer** controls rollout velocity to prevent oscillation
4. **Circuit Breaker** blocks plans that fail repeatedly
5. **Post-Recovery Verifier** confirms TSI improved; recommends rollback if not
6. **MVI** validates the governance pipeline itself is behaving deterministically

Configure via `policies/enterprise_v9.yaml`. Enable V9 runtime: `BW_KERNEL_MODE=v9`.

## Test Suite

355 tests across 34 files. Run: `pytest tests/ -v`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, contribution scope, and PR requirements.

To report a security vulnerability, see [SECURITY.md](SECURITY.md) — do not open a public issue.

All participants are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Reproducible Demo (No API Keys)

BeaconWise includes an **offline reproducible demo** that validates governance-kernel properties without requiring model-provider keys.

```bash
python examples/run_demo.py
# or: make demo
```

Expected output:

- `VERIFIED` — golden EPACK chain, all hashes intact
- `TAMPER_DETECTED` — deliberately corrupted chain
- `DRIFT` — environment-fingerprint mismatch

Demo fixtures live in `testdata/`. CI runs this on every push.

## Documentation

Full documentation for regulators, enterprise evaluators, and developers:

```
docs/INDEX.md              — canonical reading order
docs/REGULATOR_BRIEFING.md — plain-language governance summary
docs/ARCHITECTURE.md       — layered architecture specification
docs/COMPLIANCE_MAPPING.md — EU AI Act, NIST AI RMF, ISO/IEC 42001
docs/CONSTITUTION.md       — 13 governance invariants
enterprise/PILOT_PACKAGE.md — 30-day enterprise pilot guide
```

## License

Apache 2.0 — See [LICENSE](LICENSE)

