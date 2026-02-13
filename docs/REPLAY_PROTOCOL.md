# BeaconWise Deterministic Replay Protocol (DRP)
**Product:** BeaconWise Transparency Ecosphere Kernel (TEK)  
**Shorthand:** BeaconWise TEK
**Product:** BeaconWise Transparency Ecosphere Kernel (TEK)  
**Document Level:** Regulator / Compliance + Engineering Specification  
**Status:** Normative  
**Version:** 1.0.0  
**Last Updated:** February 2026
---
## 0. Executive Summary (Plain Language)
The BeaconWise Deterministic Replay Protocol (DRP) defines how any governed output produced under BeaconWise can be **reconstructed and verified** later.
This is required because many AI systems are probabilistic and opaque. Without replay, oversight bodies cannot reliably answer:
- What happened?
- What evidence was used?
- Were records modified after the fact?
- Would the system produce the same result under the same governed conditions?
DRP solves this by requiring BeaconWise to create a **Replay Package** for each governed run. The package includes:
1. The **exact inputs** that were governed  
2. The **exact governance configuration** in force  
3. The **evidence audit chain** (EPACK chain) that cryptographically binds records  
4. The **validator decisions** and consensus result  
5. Sufficient **environment metadata** to explain and detect replay drift
A replay is successful if it produces:
- an identical governed output, and
- identical validator consensus results,
**or** produces an explicit, auditable divergence report (never silent drift).
---
## 1. Scope
This protocol governs the replayability and audit verifiability of BeaconWise-governed runs, including:
- model outputs routed through BeaconWise governance
- tool or retrieval outputs recorded as evidence
- validator decision sequences
- consensus outcomes
- the cryptographic audit chain connecting evidence over time
This protocol does **not** mandate:
- any specific model provider
- any specific hosting environment
- any content moderation policy
- any “truth authority” about disputed content
It mandates **verifiability, integrity, and reproducibility** of the governed process.
---
## 2. Normative Language
The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted as described in RFC 2119.
---
## 3. Terminology
### 3.1 Governed Run
A “governed run” is an execution where BeaconWise governance is applied to produce an output, and the run is recorded to the audit system.
### 3.2 EPACK
An EPACK (Evidence PACKet) is the atomic unit of governance audit. EPACK records are cryptographically linked in an append-only chain.  
(See `SCHEMA_SPECIFICATION.md`.)
### 3.3 Replay Package (RP)
A Replay Package is the minimal set of artifacts required to reproduce and verify a governed run.
### 3.4 Determinism
Determinism means: given the same Replay Package and equivalent replay conditions, the governed output and validator results are reproducible.
### 3.5 Drift
Drift is any replay mismatch attributable to environment or dependency differences rather than tampering.
### 3.6 Tamper Event
Any unauthorized modification attempt (delete, insert, reorder, mutate fields) that breaks audit integrity.
---
## 4. Protocol Objectives
DRP MUST ensure:
1. **Integrity:** tampering is detectable, not deniable  
2. **Replayability:** runs can be reconstructed from recorded artifacts  
3. **Non-silent divergence:** mismatches produce explicit divergence reports  
4. **Regulator legibility:** replay steps and outcomes are understandable without reading application code  
5. **Chain continuity:** evidence chain integrity is preserved across time  
---
## 5. Required Artifacts
For each governed run, BeaconWise MUST persist a Replay Package containing:
### 5.1 Input Artifacts
- `input_payload` (the governed input)
- `input_payload_hash` (cryptographic hash of the input)
- `input_metadata` (timestamp, requester context, policy context)
### 5.2 Governance Configuration Snapshot
- `kernel_version` (semantic version + build hash)
- `governance_profile_id` (which ruleset applied)
- `validator_set_id` (which validators were active)
- `determinism_policy` (e.g., deterministic mode, allowed nondeterminism exceptions)
- `routing_decisions` (what path was taken and why, as auditable metadata)
### 5.3 Evidence Chain State
- `epack_head_id` (the last EPACK id for this run)
- `epack_head_hash`
- `epack_chain_proof` (sufficient linking fields to verify continuity)
- `evidence_records` or references to them (see storage models in §10)
### 5.4 Validator Decisions and Consensus
- ordered validator outputs (including hashes)
- consensus result
- any dissent or challenge records
### 5.5 Environment Fingerprint (Minimum)
BeaconWise MUST store an environment fingerprint sufficient to detect drift:
- `dependency_manifest_hash` (lockfile hash, e.g., requirements/poetry/uv)
- `runtime_signature` (python/runtime version)
- `container_signature` OR `host_signature` (when container absent)
- `tool_provider_versions` (if tools were used)
BeaconWise SHOULD include:
- `hardware_class` (cpu/gpu class) when relevant
- `network_isolation` status (online/offline)
- `locale/timezone` when it affects outputs
---
## 6. Replay Procedure (Normative)
Given a Replay Package RP:
### Step 1 — Integrity Verification
A replay engine MUST first verify:
- the EPACK chain links are valid
- the input hashes match
- the governance snapshot hashes match
- validator outputs hashes match recorded forms
If any integrity verification fails, the replay MUST terminate with:
**REPLAY_RESULT = TAMPER_DETECTED**
and produce a Tamper Report (§8.2).
### Step 2 — Environment Equivalence Check
The replay engine MUST compare RP environment fingerprint against the current replay environment.
If there are differences:
- the replay engine MUST record them as **potential drift factors**
- the replay MAY continue, but MUST set replay status to **DRIFT_RISK**
### Step 3 — Deterministic Execution
The replay engine MUST execute the governed run using:
- the recorded routing decisions
- the recorded determinism policy
- the validator sequence as recorded
If the original run used nondeterministic components, the replay MUST:
- document where nondeterminism is permitted
- document expected variance bounds
- produce a variance report (§8.3)
### Step 4 — Output Comparison
The replay engine MUST compare:
- final governed output
- validator decisions and consensus
Replay outcomes:
- **REPLAY_MATCH**: output and validator consensus match
- **REPLAY_DIVERGENCE**: mismatch with no integrity failure
- **TAMPER_DETECTED**: integrity failure
- **REPLAY_INDETERMINATE**: nondeterminism exceeds declared bounds
### Step 5 — Persist Replay Result
Replay results MUST be persisted as evidence (EPACK) linked to the original run so that the replay itself becomes auditable.
---
## 7. Determinism Requirements
BeaconWise MUST support a determinism policy that:
- defines whether strict determinism is required for the run
- defines allowed nondeterminism exceptions (if any)
- defines how exceptions are recorded and bounded
BeaconWise MUST NOT claim determinism if:
- nondeterminism is present but undeclared, or
- replay mismatch is not explicitly reported.
---
## 8. Required Reports
### 8.1 Replay Report (All Runs)
A Replay Report MUST be produced containing:
- replay timestamp
- replay engine version
- comparison results
- environment differences (if any)
- final replay outcome code
### 8.2 Tamper Report (If Tamper Detected)
A Tamper Report MUST include:
- which integrity check failed
- which EPACK link failed (or which record hash mismatch occurred)
- whether failure indicates deletion, insertion, reorder, or mutation
- the earliest point in the chain where continuity breaks
### 8.3 Drift / Variance Report (If Drift Risk or Allowed Nondeterminism)
If DRIFT_RISK is set or nondeterminism is permitted, the system MUST:
- list all environment differences
- identify components likely to influence output
- state whether replay mismatch plausibly arises from drift
- if variance bounds are defined, report whether mismatch is within bounds
---
## 9. Dispute Resolution / Arbitration
If a replay yields divergence without tamper detection:
- The system MUST allow challenger escalation per `CONSTITUTION.md` and `VALIDATOR_GOVERNANCE.md`
- A challenger MAY request:
  - replay under the original environment (e.g., container image pin)
  - replay using a certified replay environment
  - additional validation passes
All arbitration actions MUST be recorded to the evidence chain.
---
## 10. Storage Models (Compliance Note)
BeaconWise MAY store Replay Packages in either:
### 10.1 Full Materialization
All evidence content stored directly with the Replay Package.
### 10.2 Content-Addressed References
Evidence stored externally with immutable references (hash-addressed blobs).  
If using references:
- the referenced content MUST be retrievable for the retention period
- missing evidence MUST result in **REPLAY_INDETERMINATE** (not silent success)
---
## 11. Privacy and Redaction
If evidence includes sensitive data, the system MAY apply redaction, but:
- redactions MUST be recorded as auditable transformations
- original hash continuity MUST remain verifiable (e.g., via redaction proofs or dual-hash strategy)
- redaction MUST NOT enable undetected alteration of meaning without audit visibility
(See `PUBLIC_TRANSPARENCY_GUIDE.md`.)
---
## 12. Security Considerations
DRP is designed to mitigate:
- record deletion
- record insertion
- record reordering
- payload mutation
- post-hoc audit rewriting
Threats and mitigations are detailed in `THREAT_MODEL.md`.
---
## 13. Conformance Requirements
An implementation is DRP-conformant only if it can demonstrate:
1. tamper detection for:
   - delete / insert / reorder / mutate
2. reproducible replay for strict determinism runs
3. explicit divergence reporting for any mismatch
4. replay result persistence into the audit chain
BeaconWise test suites MAY serve as evidence of conformance, but a regulator review MUST be possible using this document alone.
---
## 14. Implementation Notes (Non-Normative)
- In practice, replay determinism benefits from:
  - container pinning
  - dependency lockfiles
  - deterministic validator sequencing
- Certified replay environments are recommended for regulated deployments.
---
## 15. Document Relationships
This protocol is used with:
- `SCHEMA_SPECIFICATION.md` (EPACK schemas)
- `VALIDATOR_GOVERNANCE.md` (consensus/oversight)
- `THREAT_MODEL.md` (adversarial framing)
- `CONSTITUTION.md` (governance authority & dispute escalation)
- `PUBLIC_TRANSPARENCY_GUIDE.md` (human-facing transparency and redaction)

## Non-Goals
- This protocol does not guarantee model correctness or factual truth.
- This protocol does not require AI models to be deterministic; it requires governed runs to be replay-verifiable or explicitly divergent.
- This protocol does not replace organizational compliance programs or legal obligations.
