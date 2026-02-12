# Security Policy

**Project:** BeaconWise Transparency Ecosphere Kernel (TEK)  
**Version:** 1.0.0

---

## Supported Versions

| Version | Security Fixes |
|---------|---------------|
| 1.9.x   | ✅ Active      |
| < 1.9   | ❌ Not supported |

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report security issues by email to:

```
beaconwise-tek [at] transparencyecosphere.org
```

Include `[SECURITY]` in the subject line.

**What to include:**
- Description of the vulnerability and its potential impact
- Steps to reproduce or proof-of-concept (a minimal test case is ideal)
- Which component is affected (kernel routing, EPACK chain, replay engine, validator consensus, API, etc.)
- Your assessment of severity (critical / high / medium / low)
- Whether you believe it affects audit integrity, governance determinism, or tamper-evidence guarantees — these are highest priority

**What to expect:**
- Acknowledgment within 72 hours
- Initial assessment within 7 days
- A fix or documented mitigation within 30 days for confirmed high/critical issues
- Credit in the release notes and `NOTICE` file (unless you prefer to remain anonymous)

---

## Scope

Security issues of particular concern for a governance kernel:

**Critical — affects audit integrity:**
- Vulnerabilities that allow EPACK records to be modified without hash chain breakage
- Attacks that enable governance decisions to be made without audit recording
- Replay protocol weaknesses that produce false VERIFIED results for tampered chains

**High — affects governance determinism:**
- Inputs that cause non-deterministic routing outcomes for the same system state
- Bypasses of the evidence validation gate that allow unvalidated output delivery
- Validator independence violations (single entity gaining effective control over consensus)

**Medium — affects operational security:**
- Denial-of-service against the governance kernel or EPACK storage
- Information disclosure of governance configuration or policy details
- Authentication weaknesses in the API layer

**Lower priority (but still welcome):**
- Dependency vulnerabilities (report via standard channels if non-critical)
- Documentation errors in security-relevant specs
- Test coverage gaps in security-sensitive code paths

---

## What Is Out of Scope

- Vulnerabilities in underlying AI model providers (OpenAI, Anthropic, etc.) — report directly to them
- Issues requiring physical access to the deployment environment
- Social engineering attacks against operators
- Theoretical issues with no practical exploit path

---

## Disclosure Policy

BeaconWise follows coordinated disclosure. We ask that you give us 30 days to address confirmed vulnerabilities before public disclosure. We will work with you on timing if the issue requires more time to fix safely. We will not pursue legal action against researchers who follow this policy in good faith.

---

## Security Design Notes

BeaconWise's security model is documented in `docs/SECURITY_MODEL.md`. Key properties:

- EPACK hash chains use SHA-256; chain integrity is verifiable by any party with chain access
- Governance decisions are deterministic — any non-deterministic outcome is classifiable as a governance anomaly
- Validator independence is structurally enforced — see `docs/VALIDATOR_GOVERNANCE.md`
- The kernel operates in zero-trust stance toward all AI model outputs (Invariant I4)

Understanding these properties will help scope any potential vulnerability report accurately.
