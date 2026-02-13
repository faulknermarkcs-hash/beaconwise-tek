# BeaconWise Documentation Index

**Product:** BeaconWise Transparency Ecosphere Kernel (TEK)  
**Version:** 1.9.0 | **License:** Apache 2.0 | **Status:** Production

## Canonical Reading Order

### For Regulators

1. [`REGULATOR_BRIEFING.md`](REGULATOR_BRIEFING.md) — one-page governance summary
2. [`FAQ.md`](FAQ.md) — common questions: what BeaconWise is and is not
3. [`COMPLIANCE_MAPPING.md`](COMPLIANCE_MAPPING.md) — EU AI Act, NIST AI RMF, ISO/IEC 42001 mapping
4. [`THREAT_MODEL.md`](THREAT_MODEL.md) — formal threat model with mitigations
5. [`EVIDENCE_LIFECYCLE.md`](EVIDENCE_LIFECYCLE.md) — how audit records are created and preserved
6. [`REPLAY_PROTOCOL.md`](REPLAY_PROTOCOL.md) — deterministic replay: VERIFIED / DRIFT / TAMPER_DETECTED

### For Enterprise Evaluators

1. [`ARCHITECTURE.md`](ARCHITECTURE.md) — layered architecture, principles, deployment archetypes
2. [`CONSTITUTION.md`](CONSTITUTION.md) — 13 constitutional invariants (machine-readable: `CONSTITUTION`)
3. [`VALIDATOR_GOVERNANCE.md`](VALIDATOR_GOVERNANCE.md) — multi-validator, Challenger layer, anti-capture
4. [`SECURITY_MODEL.md`](SECURITY_MODEL.md) — cryptographic chains, key management, tamper detection
5. [`ADOPTION_GUIDE.md`](ADOPTION_GUIDE.md) — integration patterns, deployment configuration
6. [`GOVERNANCE_USE_CASES.md`](GOVERNANCE_USE_CASES.md) — sector-specific governance scenarios
7. [`PUBLIC_TRANSPARENCY_GUIDE.md`](PUBLIC_TRANSPARENCY_GUIDE.md) — communicating governance to stakeholders

### Enterprise Deployment

- [`../enterprise/PILOT_PACKAGE.md`](../enterprise/PILOT_PACKAGE.md) — 30-day pilot guide: deployment steps, success criteria, evidence artifacts, evaluation checklist

### Reference

- [`SCHEMA_SPECIFICATION.md`](SCHEMA_SPECIFICATION.md) — EPACK and policy YAML schemas
- [`FILETREE.md`](FILETREE.md) — full repository structure
- [`../governance_schema.json`](../governance_schema.json) — machine-readable JSON Schema (resilience_policy included)
- [`../CHANGELOG.md`](../CHANGELOG.md) — version history (v1.7.0 → v1.9.0)

## Non-Goals (Repository Scope)

This documentation describes governance infrastructure. It does not:

- Specify AI model safety requirements
- Constitute legal compliance advice
- Replace organizational compliance programs
- Certify factual accuracy of AI outputs

Deployers remain responsible for regulatory obligations in their jurisdictions.

## Lint Status

Last lint: February 2026 — 0 broken links, 0 contradictory claims, 0 duplicate files.  
See [`REGULATOR_LINT_REPORT.md`](REGULATOR_LINT_REPORT.md) for details.
