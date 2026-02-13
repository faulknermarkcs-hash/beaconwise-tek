# BeaconWise Governance Use Cases
**Product:** BeaconWise Transparency Ecosphere Kernel (TEK)  
**Shorthand:** BeaconWise TEK

**Product:** BeaconWise Transparency Ecosphere Kernel (TEK)  
**Version:** 1.9.0  
**Audience:** Enterprise evaluators, compliance officers, domain architects, researchers

---

## Overview

The Transparency Ecosphere Kernel (TEK) is a governance runtime, not an AI model. It wraps any language model with deterministic safety screening, role-based output filtering, cryptographic interaction gates, and tamper-evident audit chains.

This document presents four concrete deployment scenarios. Each maps a real governance problem to specific TEK enforcement mechanisms, shows the information flow, and identifies what an auditor can verify.

---

## Use Case 1: Medical AI Oversight

### The Problem

A hospital network deploys an AI assistant for clinical staff. Nurses need general guidance. Physicians need diagnostic-level detail. Patients browsing the public portal must never receive content that could be mistaken for a diagnosis.

The same underlying language model serves all three audiences. Without governance, the model treats every question the same — a patient asking about symptoms gets the same depth as an attending physician.

### How TEK Handles This

**Credential verification** establishes the user's role before any AI output is generated:

| User | Credential | role_level | Config Preset |
|------|------------|------------|---------------|
| Patient (public portal) | None / expired | 1 | FAST |
| Registered nurse | Verified NPI, role="nurse" | 2 | HIGH_ASSURANCE |
| Attending physician | Verified NPI, role="physician" | 3 | CONSENSUS |
| Research specialist | Verified + institutional | 4 | CONSENSUS |

**Scope gate** screens every AI output before delivery. The compiled regex rules enforce:

- "diagnosis", "prognosis", "treatment plan" → requires role_level 3+. A nurse sees a REWRITE with the diagnostic language removed. A patient sees a REFUSE.
- "p-value", "statistical significance", "replication" → requires role_level 4+. Even a physician gets a REWRITE stripping advanced statistical claims unless they hold specialist credentials.
- Missing disclaimer → Any output to role_level 1-2 without the required disclaimer snippet ("This is general information only...") is automatically REFUSED.

**EPACK audit trail** records every scope gate decision with the user's role_level, the patterns triggered, and the decision (PASS/REWRITE/REFUSE). A compliance officer can query:

```
"Show me all REWRITE events for role_level 2 users in the last 30 days"
→ EPACK filter: stage_prefix="tecl.scope_gate.violation", role_level=2
```

**High-stakes gating** prevents premature escalation. A patient cannot receive physician-tier responses even if they claim expertise — the TSV belief system caps self-assertion evidence at E1 strength, and the `high_stakes_ready()` gate requires externally-verified E3 evidence.

### What an Auditor Can Verify

1. Every output to a patient was either PASSED with disclaimer or REFUSED — never REWRITE (patients don't get rewritten medical content, they get blocked).
2. Every REWRITE for a nurse included the specific violation patterns and a rewrite prompt.
3. The EPACK chain is unbroken from session start to end.
4. No credential was accepted after expiry (the verifier stub returns PUBLIC_CONTEXT for expired credentials — tested in `test_verifier_stub.py`).

---

## Use Case 2: Financial Compliance

### The Problem

A wealth management firm uses AI to help advisors draft client communications. Regulatory bodies (SEC, FINRA) require that investment advice is only provided by licensed professionals, that recommendations include appropriate disclaimers, and that all client-facing communications are archived and auditable.

### How TEK Handles This

**Input screening** catches prompt injection attempts by clients who interact with the AI through a client portal. Stage 1 regex and Stage 2 semantic embeddings block attempts to manipulate the system into providing unlicensed advice.

**Scope gate rules** for the financial domain:

| Pattern | min_level | Effect |
|---------|-----------|--------|
| "expected return N%", "portfolio allocation" | 3 | Only licensed advisors see projections |
| "buy TICKER", "sell TICKER", "tax strategy" | 3 | Trade recommendations gated |
| Statistical claims | 4 | Quantitative analysis restricted to analysts |

**Profile escalation** protects against consistency failures. If the AI generates output that fails alignment validation twice in a row, the profile escalates from FAST → STANDARD → HIGH_ASSURANCE, increasing retry counts and tightening alignment thresholds. This ensures that under pressure (high query volume, complex questions), the system becomes more cautious, not less.

**EPACK chain** provides the regulatory archive. Each interaction record contains:

- SHA-256 hash of the user input (redacted for privacy)
- SHA-256 hash of the AI output
- The scope gate decision and any violations
- The user's verified role_level at the time of the interaction
- Build manifest (kernel version, configuration hashes)

A compliance audit can reconstruct the complete decision history:

```
"For client account X, show that every AI-assisted communication 
was generated under advisor role_level 3, passed scope gate, 
and the EPACK chain is intact."
```

### What an Auditor Can Verify

1. No output containing trade recommendations was delivered to role_level < 3.
2. All client-facing outputs for role_level 1-2 included the required disclaimer.
3. Profile escalations correlate with validation failures (the system got stricter when outputs were uncertain).
4. The EPACK chain provides a complete, hash-linked, tamper-evident record of every interaction.

---

## Use Case 3: Research Reproducibility

### The Problem

An academic lab uses AI to assist with literature review, hypothesis generation, and data analysis. The lab's IRB (Institutional Review Board) requires that AI-assisted research is reproducible — meaning that given the same inputs, the governance decisions must be deterministic and verifiable. The lab also needs to demonstrate that AI outputs involving human subjects data were appropriately gated.

### How TEK Handles This

**Deterministic design** is TEK's core architectural principle. Every governance decision is reproducible:

- Stage 1 safety uses compiled regex patterns (no randomness).
- Stage 2 safety uses frozen exemplar embeddings with cosine similarity (deterministic for the same exemplar set).
- Routing is a pure function of the InputVector fields (`safe`, `domain`, `complexity`, `requires_reflect`, `requires_scaffold`).
- Gate tokens are derived from `stable_hash(payload)` — same payload, same token.
- EPACK hashes use `stable_hash()` (SHA-256 over sorted JSON) — deterministic across Python versions and platforms.

**Provenance manifests** embed kernel version, Python version, and feature flags in every EPACK record. A reviewer can verify exactly which version of TEK governed each interaction.

**High-stakes gating** for human subjects data. Research involving patient data, genetic information, or vulnerable populations triggers HIGH_STAKES domain detection. The TSV belief system requires E3 verification evidence (externally confirmed IRB approval) before the AI provides detailed analysis. Without E3, the system DEFERs:

```
"DEFER: This is high-stakes. I need strong verification evidence (E3) 
before proceeding."
```

**REFLECT gates** for complex analyses. When a researcher asks for a comprehensive analysis (high complexity score), the kernel pauses and presents a structured summary of what it understood, requiring explicit confirmation before proceeding. This prevents the AI from running with a misunderstood request on sensitive data.

### What an Auditor Can Verify

1. Every governance decision is deterministic — replaying the same inputs through the same kernel version produces identical routing, gate tokens, and EPACK hashes.
2. The provenance manifest in each EPACK record identifies the exact kernel configuration.
3. Human subjects queries were DEFERRED until E3 verification was established.
4. Complex analyses went through REFLECT confirmation gates, and the confirmation token in the EPACK record proves the researcher explicitly approved the approach.

---

## Use Case 4: Content Moderation Pipeline

### The Problem

A platform deploys AI to generate content summaries, recommendations, and responses. The platform needs to prevent the AI from generating harmful, manipulative, or policy-violating content — and needs to prove to regulators that it has systematic controls, not just guidelines.

### How TEK Handles This

**Two-stage safety screening** catches harmful inputs before they reach the language model:

- Stage 1 (regex): Blocks structural prompt injection patterns ("ignore previous instructions", "you are now", system prompt extraction attempts).
- Stage 2 (embeddings): Catches semantic similarity to known harmful prompts even when surface wording is changed. The cosine similarity threshold (default 0.50) is configurable per deployment.

**BOUND routing** is the fail-closed response. If either safety stage flags the input, the router forces `["BOUND"]` — the language model is never called. The user receives a deterministic redirect message. No exceptions, no overrides, no edge cases where a flagged input reaches the model.

**Tool sandbox** prevents indirect code execution. The `safe_calc` tool uses an AST-based evaluator that permits only arithmetic nodes — not a charset-gated `eval()`, but a structural parser that cannot execute arbitrary code even if the charset gate is loosened.

**Recursive redaction** ensures that user-generated content in EPACK logs cannot be reconstructed. The `_redact_recursive()` function walks nested structures to any depth, replacing every string with `{"_redacted": True, "sha256": ...}`. This preserves verifiability (you can prove a redacted field matched a known value) without exposing personal data in audit logs.

**Profile escalation** provides adaptive caution. Under normal operation, the system runs in FAST mode (lower latency, fewer retries). If outputs start failing validation, the profile automatically escalates to STANDARD and then HIGH_ASSURANCE, increasing alignment thresholds and retry counts. A sustained clean streak allows gradual de-escalation. This means the system is strictest when it's least certain.

### What an Auditor Can Verify

1. No flagged input ever reached the language model — the EPACK record shows `route: ["BOUND"]` with safety scores, and no generation metadata.
2. All EPACK records contain redacted user content (SHA-256 hashes, not plaintext).
3. Profile escalation events correlate with validation failures — the system was demonstrably more cautious when outputs were uncertain.
4. The EPACK chain is cryptographically intact, and provenance manifests identify the exact kernel and safety configuration for each interaction.

---

## Cross-Cutting Governance Properties

These properties hold across all four use cases:

| Property | Mechanism | Verification |
|----------|-----------|--------------|
| **Fail-closed defaults** | `PUBLIC_CONTEXT` for unverified users, `BOUND` for unsafe inputs | Test: `test_verifier_stub.py`, `test_router.py` |
| **Deterministic routing** | Pure function of InputVector | Test: `test_router.py` (8 tests, all paths) |
| **Tamper-evident audit** | SHA-256 hash-chained EPACK with GENESIS sentinel | Test: `test_epack_chain_integrity.py` (22 tests), `test_redaction_epack_provenance.py` |
| **Evidence-gated escalation** | E3 verification required for high-stakes, self-assertion capped at E1 | Test: `test_tsv_state.py` (21 tests) |
| **Replay prevention** | Session-scoped nonces, consumed-nonce tracking | Test: `test_gates_full.py::test_replay_detection` |
| **Recursive privacy** | All strings redacted at any nesting depth | Test: `test_redaction_epack_provenance.py` |
| **Zero eval()** | AST-based tool sandbox (v6) | Test: `test_safe_calc_hardened.py` (23 tests) |

---

## Getting Started

To see these governance mechanisms in action with no setup:

```bash
cd transparency-ecosphere-kernel-main
PYTHONPATH=src python3 examples/minimal_demo.py
```

This runs 7 turns through the kernel — safe input, prompt injection, calculator, injection attempt, REFLECT gate, gate confirmation, and high-stakes DEFER — and verifies the EPACK chain integrity at the end.

---

## Related Documentation

- `ARCHITECTURE.md` — System architecture specification
- `REPLAY_PROTOCOL.md` — Deterministic replay protocol
- `EVIDENCE_LIFECYCLE.md` — Evidence governance specification
- `VALIDATOR_GOVERNANCE.md` — Validator authority and oversight
- `COMPLIANCE_MAPPING.md` — Regulatory framework alignment
- `ADOPTION_GUIDE.md` — Deployment guidance