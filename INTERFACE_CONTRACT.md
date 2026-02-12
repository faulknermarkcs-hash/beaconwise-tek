# TEK Interface Contract v1.0

**Purpose:** Define the stable interface that external parties depend on.  
**Scope:** BeaconWise TEK (kernel) — governance runtime only  
**Status:** Pre-freeze (targeting v1.9.1)

---

## Contract Guarantee

Once TEK reaches v1.0.0, changes to this interface require:
1. **Semantic versioning** — Major version bump for breaking changes
2. **Migration path** — Documented upgrade procedure for dependents
3. **Deprecation notice** — 6-month warning before removal

**Current status:** Pre-1.0 (interface may change without notice)

---

## 1. EPACK Chain Format

**File:** `schemas/epack/chain_export_v1.json`

### Guaranteed Fields

```json
{
  "metadata": {
    "kernel_version": "string (semver)",
    "export_timestamp": "string (ISO 8601)",
    "hash_algorithm": "SHA256",
    "signature_algorithm": "Ed25519",
    "chain_length": "integer"
  },
  "blocks": [
    {
      "block_hash": "string (64-char hex)",
      "prev_block_hash": "string (64-char hex)",
      "payload_hash": "string (64-char hex)",
      "timestamp": "string (ISO 8601)",
      "signer": "string (format: type:id)",
      "signature": "string (base64)",
      "validator_results": "array"
    }
  ]
}
```

### Stability Guarantee

✅ **MUST NOT change:**
- Field names
- Field types
- Hash algorithm (SHA256)
- Signature algorithm (Ed25519)
- Block linkage semantics

✅ **MAY add:**
- Optional fields (must not break existing parsers)
- Metadata fields (in `metadata` object)

❌ **MUST NOT remove:**
- Any required field
- Hash chain linkage
- Signature verification capability

---

## 2. Key Registry Export

**File:** `schemas/epack/key_registry_export_v1.json`

### Guaranteed Structure

```json
{
  "signer_id": [
    {
      "public_pem": "string (PEM format)",
      "key_version": "integer",
      "created_at": "string (ISO 8601)",
      "revoked": "boolean",
      "revoked_at": "string | null (ISO 8601)"
    }
  ]
}
```

### Security Guarantee

✅ **MUST NEVER export:**
- Private keys
- Private key material in any form
- Key derivation parameters

✅ **MUST maintain:**
- Historical keys (for verifying old blocks)
- Revocation status
- Key version ordering

---

## 3. Verification API

**Purpose:** External auditors verify chains without trusting TEK

### Command-Line Interface

```bash
verify_chain.py <chain.json> <keys.json>
```

**Exit codes:**
- `0` — Chain verified (no tampering)
- `1` — Integrity violation detected
- `2` — Invalid input files

### Python API

```python
from verify_chain import verify_chain

result = verify_chain(chain_data, keys_data)

# result.valid: bool
# result.block_count: int
# result.signed_count: int
# result.errors: List[str]
```

### Stability Guarantee

✅ **MUST maintain:**
- Exit code semantics
- JSON input format
- Verification logic correctness

✅ **MAY change:**
- Performance optimizations
- Error message wording
- Internal implementation

❌ **MUST NOT:**
- Require TEK installation to verify
- Require network access to verify
- Require private keys to verify

---

## 4. Validator Contract

**File:** Each validator in `src/tek/validators/*.py`

### Required Interface

```python
def validate(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a deliberation context against a governance rule.
    
    Args:
        context: Deliberation context with:
            - policy: Policy configuration
            - proposal: Proposal metadata
            - challenges: Challenge records
            - evidence: Evidence records
            - arbitration: Arbitration record
    
    Returns:
        {
            "control": "string (control ID)",
            "outcome": "PASS" | "FAIL" | "DEFER",
            "message": "string (explanation)",
            "evidence": "any (optional)"
        }
    """
```

### Stability Guarantee

✅ **MUST maintain:**
- Function signature
- Return value structure
- Outcome semantics (PASS/FAIL/DEFER)

✅ **MAY change:**
- Internal logic
- Context field usage
- Performance characteristics

❌ **MUST NOT:**
- Remove required fields from return value
- Change PASS/FAIL semantics
- Require external network calls

---

## 5. Control Register

**File:** `docs/CONTROL_REGISTER.md`

### Guaranteed Controls

All controls in the register MUST remain:
- Semantically consistent
- Verifiable through tests
- Documented with examples

### Stability Guarantee

✅ **MAY add:**
- New controls
- Additional test cases
- Enhanced documentation

❌ **MUST NOT:**
- Remove controls without deprecation
- Change control semantics without major version bump
- Break existing governance policies

---

## 6. Cryptographic Primitives

### Hash Algorithm

**Current:** SHA256  
**Future:** Hash agility support required before changing

**Contract:**
- All hash functions MUST produce 64-character hex strings
- Hash algorithm MUST be specified in metadata
- Old chains MUST remain verifiable after hash upgrade

### Signature Algorithm

**Current:** Ed25519  
**Future:** Post-quantum migration required (SPHINCS+, Dilithium)

**Contract:**
- Signature algorithm MUST be specified in metadata
- Multiple signature schemes MUST coexist during migration
- Old blocks MUST remain verifiable with original algorithm

---

## 7. Breaking Changes Policy

### What Triggers a Major Version Bump

- Change to EPACK chain format (required fields)
- Change to key registry format
- Change to verification semantics
- Removal of any control
- Change to hash or signature algorithm

### What Requires Minor Version Bump

- Addition of optional EPACK fields
- Addition of new controls
- Addition of new validators
- Performance improvements

### What Requires Patch Version Bump

- Bug fixes
- Documentation updates
- Test improvements

---

## 8. Deprecation Process

### Step 1: Announce (6 months before removal)

- Add DEPRECATED notice to documentation
- Log warnings when deprecated feature is used
- Provide migration guide

### Step 2: Maintain (during deprecation period)

- Continue supporting deprecated feature
- Fix security issues only
- No new features for deprecated code

### Step 3: Remove (after 6 months)

- Major version bump
- Remove deprecated code
- Update migration guide with final instructions

---

## 9. External Dependencies

### Cryptography Library

**Current:** Python `cryptography` (Ed25519 implementation)

**Contract:**
- TEK MUST NOT depend on specific cryptography library versions
- All crypto operations MUST be wrapped in abstraction layer
- Alternative implementations MUST be verifiable against test vectors

### Zero External Runtime Dependencies

**Contract:**
- Verification tools MUST work with Python stdlib + cryptography only
- No database required for verification
- No network access required for verification

---

## 10. Compatibility Testing

### Before Release

All releases MUST pass:
1. **Chain verification tests** — Real chains verify correctly
2. **Backward compatibility tests** — Old chains verify with new code
3. **Schema validation tests** — Exports conform to JSON schema
4. **External auditor tests** — Zero-trust verification succeeds

### Continuous Verification

TEK MUST maintain:
- Reference test chains (versioned)
- Known-good exports (versioned)
- Verification test suite (comprehensive)

---

## 11. Interface Versioning

### Schema Files

All schemas are versioned:
- `chain_export_v1.json` — v1 chain format
- `key_registry_export_v1.json` — v1 key format

### API Versions

When breaking changes are required:
- New schema version created
- Old schema supported for 12 months
- Migration tool provided

---

## 12. External Auditor Toolkit

**Location:** `tek-audit/`

### Guaranteed Tools

- `verify_chain.py` — Standalone CLI verifier
- `export_chain.py` — Chain export utility
- `export_keys.py` — Key export utility

### Documentation

- `AUDITOR_QUICKSTART.md` — Zero-trust instructions
- `README.md` — Toolkit overview
- `chain_schema.json` — JSON schema specification

### Stability Guarantee

✅ **MUST maintain:**
- CLI interface
- Export formats
- Verification semantics

---

## 13. Governance Primitives

### Immutable Concepts

These concepts MUST NOT change semantics:

- **EPACK** — Evidence-Preserving Append Chain
- **Validator** — Governance rule verifier
- **Checkpoint** — Publish gate with TEK validation
- **Constitution** — High-level governance document
- **Deliberation** — Multi-agent adversarial reasoning

### Evolutionary Concepts

These MAY evolve with minor versions:

- Specific validator implementations
- Evidence type definitions
- Provider routing logic

---

## 14. Compliance

### Standards Alignment

TEK interface is designed for:
- IEEE P2863 (Governance of AI Systems)
- ISO/IEC 42001 (AI Management System)
- EU AI Act requirements

**Contract:** TEK MUST NOT break compliance mappings without major version bump

---

## 15. Contact & Governance

**Interface changes:** Requires approval from kernel maintainers  
**Breaking changes:** Require RFC + community review  
**Security fixes:** May break interface if necessary (with disclosure)

**Maintainers:**
- Mark (BeaconWise/ImaginAIrium)

**Process:**
- RFCs posted to GitHub discussions
- 14-day minimum review period
- Security fixes expedited

---

## Changelog

**v1.0 (Draft)** — 2026-02-11
- Initial interface contract
- EPACK chain format v1
- Key registry export v1
- Auditor toolkit interface

---

**End of Interface Contract**
