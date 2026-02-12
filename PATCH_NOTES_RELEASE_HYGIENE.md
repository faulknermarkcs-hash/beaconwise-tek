# Patch Notes — Release Hygiene (v1.9.0)

This document covers the release hygiene changes made alongside the v1.9.0 technical release. These changes do not affect runtime behavior or test outcomes — they address the project's GitHub presence, installability, and community infrastructure.

---

## Changes

### New: GitHub Community Files

Four files added to satisfy GitHub's community health checklist and signal project maturity to enterprise evaluators and regulators reviewing the repository:

**`CODE_OF_CONDUCT.md`**
Adapted from Contributor Covenant 2.1 with modifications reflecting the governance mission of this project. Establishes expected behavior, enforcement process, and the principle that the project community should meet the same standards it builds infrastructure to enforce.

**`CONTRIBUTING.md`**
Documents the development setup, contribution scope, PR requirements, and the higher bar applied to normative specification changes. Explicitly states what is out of scope (AI capabilities, auditability reductions, governance bypasses) alongside what is in scope.

**`SECURITY.md`**
Defines the vulnerability disclosure process, severity classification for governance-infrastructure-specific threat categories (audit integrity, governance determinism, operational security), and the coordinated disclosure policy. Contact: `beaconwise-tek [at] transparencyecosphere.org`.

**`PATCH_NOTES_RELEASE_HYGIENE.md`** (this file)
Documents the release hygiene changes separately from the technical patch notes to keep `PATCH_NOTES.md` focused on system behavior changes.

---

### Changed: `pyproject.toml` — Dependencies Declared

Previously `dependencies = []`. Now correctly declares runtime dependencies matching `requirements.txt`:

```
fastapi, uvicorn, gunicorn, psycopg2-binary, httpx,
pydantic, pyyaml, numpy, streamlit, python-dotenv,
groq, requests>=2.31.0
```

This means `pip install -e .` now works correctly without requiring a separate `pip install -r requirements.txt` step. The `[dev]` extras group (pytest, etc.) is declared in `pyproject.toml` as well and installable via `pip install -e ".[dev]"`.

---

### Changed: `README.md` — Installation Clarity

Added explicit venv setup instructions before the install step. Added `--reload` flag to the uvicorn command (appropriate for development). Minor label improvements for clarity.

Before:
```bash
pip install -r requirements.txt
# Streamlit UI
streamlit run app.py
# FastAPI API
uvicorn api.main:app --host 0.0.0.0 --port 8000
# Tests
pytest tests/ -v
```

After:
```bash
python -m venv .venv
source .venv/bin/activate

pip install -e .

# run the Streamlit app
streamlit run app.py

# or run the API (FastAPI)
uvicorn api.main:app --reload --port 8000

# run tests
pytest -q tests
```

---

### Removed: `setup.cfg`

Redundant with `pyproject.toml`. Removing it eliminates the ambiguity about which file is authoritative for package metadata. No behavioral change.

---

## What Did Not Change

- Runtime behavior, routing logic, EPACK chain, replay protocol
- Test suite (355 tests, 34 files)
- Constitutional invariants
- Normative documentation in `docs/`
- `testdata/` fixtures
- Demo script output

`make verify` and `make demo` produce identical results before and after these changes.

---

### Added: `CHANGELOG.md`

Standard Keep-a-Changelog format covering v1.7.0 through v1.9.0, with summary entries for pre-1.7 development phases. Linked from `pyproject.toml` project URLs.

### Changed: `pyproject.toml` — Project Metadata Expanded

Added `readme`, `license`, `keywords`, `classifiers`, `[project.optional-dependencies].dev`, and `[project.urls]` sections. `pip install -e ".[dev]"` now works correctly without the `|| pip install -e .` fallback in CI.

### Changed: `.github/workflows/ci.yml` — Demo Step Added

CI now runs `python examples/run_demo.py` as a final step after the full test suite, confirming the VERIFIED / TAMPER_DETECTED / DRIFT output on every push.

### Changed: `README.md` — Badges and Structure

Five badges added (CI status, license, Python version, test count, governance). Demo and Documentation sections moved above License. Documentation section added pointing to `docs/INDEX.md` and key documents.
