# Contributing to BeaconWise

**Project:** BeaconWise Transparency Ecosphere Kernel (TEK)  
**License:** Apache 2.0

Thank you for your interest in contributing to BeaconWise. This project is governance infrastructure — contributions directly affect how AI systems are audited and verified. We take that seriously, and we want contributions to reflect the same care.

---

## What We're Looking For

**High-value contributions:**
- Bug fixes with reproduction steps and regression tests
- Test coverage improvements (target areas: meta_validation, replay, epack chain)
- Documentation improvements — especially clarifying normative language, fixing ambiguities in specs, or correcting the compliance mapping
- New sector-specific governance profiles (healthcare, legal, financial)
- Security hardening (see `SECURITY.md` for the disclosure process)

**Please discuss first (open an issue before a PR):**
- New constitutional invariants or changes to existing ones
- Changes to EPACK schema or replay protocol — these affect audit record compatibility
- New validator adapter integrations
- Any change that affects determinism guarantees

**Out of scope:**
- Features that add AI capabilities (this is governance infrastructure, not an AI product)
- Changes that reduce auditability, disable governance paths, or bypass validation gates
- Dependencies that cannot be audited or that introduce supply chain risk without justification

---

## Development Setup

```bash
# Clone and set up environment
git clone https://github.com/beaconwise-tek/beaconwise
cd beaconwise
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Verify everything works
make verify                     # full test suite (355 tests)
make demo                       # offline reproducible demo
```

---

## Before Submitting a PR

1. **Run the full test suite** — `make verify` must pass. Do not submit PRs that break existing tests without explicit justification.

2. **Run the demo** — `make demo` should still output `VERIFIED / TAMPER_DETECTED / DRIFT` in that order. If your change affects this, explain why in the PR.

3. **Write tests** — new behavior without tests will not be merged. Governance infrastructure correctness is validated through the test suite.

4. **Update documentation** — if your change affects normative behavior, update the relevant spec in `docs/`. If it affects the compliance mapping, update `COMPLIANCE_MAPPING.md`. If it affects the package structure, `FILETREE.md` will be regenerated automatically on release.

5. **Check for determinism regressions** — if your change touches routing, validation, or EPACK generation, confirm that the same inputs still produce identical outputs across repeated runs.

---

## Commit Style

- Use imperative mood: "Add circuit breaker cooldown test" not "Added..."
- Reference issues: `Fixes #123` or `Related to #456`
- Keep commits focused — one logical change per commit
- Do not commit generated files (FILETREE.md, conformance reports) — these are regenerated on release

---

## Specification Changes

Changes to normative specifications in `docs/` follow a higher bar:

- Open an issue describing the proposed change and its rationale
- Constitutional changes (any edit to `CONSTITUTION.md` or `CONSTITUTION`) require documented public justification per Invariant I8
- EPACK schema changes must preserve backward compatibility or provide an explicit migration path
- Replay protocol changes must include a test demonstrating the new behavior against the golden fixture in `testdata/`

---

## Code of Conduct

All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Questions

Open a GitHub Discussion or issue. If your question involves a potential security issue, use the process in `SECURITY.md` instead.
