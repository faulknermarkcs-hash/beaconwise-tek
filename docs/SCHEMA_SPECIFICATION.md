# BeaconWise Governance Schema Specification
**Product:** BeaconWise Transparency Ecosphere Kernel (TEK)  
**Shorthand:** BeaconWise TEK

**Version:** 1.0.0  
**Schema Family:** `beaconwise-governance`  
**Document Level:** Engineering Specification  

---

## Overview

This document defines the open, versioned data formats used by BeaconWise governance infrastructure. All schemas are designed for interoperability — any system that produces or consumes governance data can validate against these specifications.

---

## 1. EPACK Record Schema

**Schema ID:** `beaconwise-governance/epack`

An EPACK (Evidence PACKet) is the atomic unit of governance audit. Each governed interaction produces exactly one EPACK record.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `seq` | integer | Monotonic sequence number (1-indexed) |
| `ts` | float | Unix timestamp of record creation |
| `prev_hash` | string | SHA-256 hash of previous record. First record uses `"GENESIS"` |
| `hash` | string | SHA-256 of canonical JSON: `{seq, ts, prev_hash, payload}` |
| `payload` | object | Governed interaction data (see Payload Fields) |

### Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `interaction` | integer | Yes | Interaction counter |
| `profile` | string | Yes | `A_FAST`, `A_STANDARD`, or `A_HIGH_ASSURANCE` |
| `user_text_hash` | string | Yes | SHA-256 of user input (never raw text) |
| `assistant_text_hash` | string | Yes | SHA-256 of assistant output |
| `pending_gate` | object | Yes | Gate state (confirm token, nonce, expiry) |
| `traces_tail` | array | Yes | Last 20 routing/gate trace events |
| `tsv_snapshot` | object | Yes | Bayesian belief state at decision time |
| `build_manifest` | object | Yes | Kernel version, features, manifest hash |
| `extra` | object | No | Route info, generation metadata, validation results |

### Hash Algorithm

```
hash = SHA-256(canonical_json({seq, ts, prev_hash, payload}))
```

Canonical JSON: sorted keys, no whitespace, `separators=(",", ":")`, UTF-8 encoding.

### Chain Integrity Rule

For record `n` where `n > 1`: `record[n].prev_hash == record[n-1].hash`

---

## 2. Governance Telemetry Schema

**Schema ID:** `beaconwise-governance/telemetry`

Normalized telemetry events for governance observability.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | string | Event category (e.g., `interaction`, `gate`, `escalation`) |
| `timestamp` | float | Unix timestamp |
| `session_id` | string | Session identifier |
| `epack_seq` | integer | Corresponding EPACK sequence number |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `route` | string | Route taken (BOUND, DEFER, REFLECT, SCAFFOLD, TDM) |
| `profile` | string | Active profile at event time |
| `safety_stage1_ok` | boolean | Stage 1 safety result |
| `safety_stage2_ok` | boolean | Stage 2 safety result |
| `scope_gate_decision` | string | PASS, REWRITE, or REFUSE |
| `validation_ok` | boolean | Output validation result |
| `latency_ms` | float | Processing latency in milliseconds |

---

## 3. Routing Proof Schema

**Schema ID:** `beaconwise-governance/routing-proof`

Deterministic proof that a specific governance route was taken.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `input_hash` | string | SHA-256 of user input |
| `route_sequence` | array[string] | Ordered list of routes taken |
| `route_reason` | string | Human-readable routing rationale |
| `safety_stage1_ok` | boolean | Stage 1 result |
| `safety_stage2_ok` | boolean | Stage 2 result |
| `safety_stage2_score` | float | Cosine similarity score |
| `domain` | string | Detected domain (GENERAL, TECHNICAL, HIGH_STAKES) |
| `complexity` | integer | Estimated complexity (2-8) |
| `profile` | string | Active governance profile |
| `timestamp` | float | Proof generation timestamp |

### Verification Rule

A routing proof is valid if:
1. Unsafe inputs (`safety_stage1_ok=false` OR `safety_stage2_ok=false`) route to `BOUND`
2. The proof seal (SHA-256 of all fields) is non-empty
3. All required fields are present

---

## 4. Governance Receipt Schema

**Schema ID:** `beaconwise-governance/receipt`

Tamper-evident signed receipt proving governance occurred.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `receipt_id` | string | Unique receipt identifier |
| `epack_hash` | string | Hash of the governed EPACK |
| `routing_proof_hash` | string | Hash of the routing proof |
| `manifest_hash` | string | Build manifest hash |
| `tsv_snapshot_hash` | string | Hash of belief state |
| `scope_gate_decision` | string | PASS, REWRITE, REFUSE, or N/A |
| `profile` | string | Active governance profile |
| `mode` | string | `lightweight`, `standard`, or `forensic` |
| `timestamp` | float | Receipt creation timestamp |
| `signature` | string | HMAC-SHA256 over all other fields |

### Signature Algorithm

```
payload = canonical_json({receipt_id, epack_hash, routing_proof_hash,
                          manifest_hash, tsv_snapshot_hash,
                          scope_gate_decision, profile, mode, timestamp})
signature = HMAC-SHA256(key, payload)
```

---

## 5. Backward Compatibility

### Compatible Versions

| Schema Version | Compatible With |
|----------------|-----------------|
| 1.0.0 | 1.0.0 |

### Compatibility Rules

1. New optional fields may be added without version bump
2. Removing required fields requires major version bump
3. Changing hash algorithms requires major version bump
4. All version transitions must include migration tooling

---

## 6. Integration Guide

### Producing Governance Data

Any system can produce BeaconWise-compatible governance data by:
1. Generating EPACK records matching the schema
2. Computing SHA-256 hashes using canonical JSON serialization
3. Maintaining hash chain integrity between records

### Consuming Governance Data

Third-party verifiers can:
1. Validate records against schemas using `validate_epack_record()`
2. Verify chain integrity using `verify_epack_chain()`
3. Verify governance receipts using `verify_receipt(receipt, key)`
4. Replay audit chains using `replay_audit_chain(chain)`

### Reference Implementation

The canonical reference implementation is in `src/ecosphere/governance/schema.py` (schemas) and `src/ecosphere/governance/proof.py` (verification).