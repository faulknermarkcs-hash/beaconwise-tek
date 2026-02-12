# TEK Kernel Freeze Checklist

**Target version:** v1.9.1  
**Freeze date:** TBD (after all items complete)  
**Status:** Pre-freeze

---

## Why Freeze Now?

External parties (auditors, ImaginAIrium) are ready to depend on TEK's interface. Once they do, changing the interface becomes expensive. Freezing forces:

1. **Interface stability** — External tools don't break
2. **Product velocity** — ImaginAIrium moves fast without kernel churn
3. **Academic credibility** — Published results remain reproducible

---

## Freeze Criteria (All Must Pass)

### 1. Interface Contract Published ✅

- [x] `INTERFACE_CONTRACT.md` created in TEK repo
- [x] Contract defines stable boundaries
- [x] Breaking change policy documented
- [x] Deprecation process specified

**Location:** `tek/INTERFACE_CONTRACT.md`

---

### 2. Versioned Schemas Available ✅

- [x] `schemas/epack/chain_export_v1.json` — EPACK chain format
- [x] `schemas/epack/key_registry_export_v1.json` — Key registry format

**Purpose:** External tools validate against these schemas

---

### 3. Auditor Toolkit Works End-to-End ⚠️

**Required tests:**

- [ ] Generate real signed chain in Commons
- [ ] Export chain using `export_chain.py`
- [ ] Export keys using `export_keys.py`
- [ ] Verify with `verify_chain.py` → Exit 0 (PASS)
- [ ] Tamper with chain → Exit 1 (FAIL with forensics)

**Current status:** Toolkit exists but needs integration test with real Commons chains

**Action:** Test full verification flow before freeze

---

### 4. Control Register Complete ✅

**Required:**

- [x] All controls documented
- [x] Test coverage for each control
- [x] Examples for each control

**Status:** Control register in `docs/CONTROL_REGISTER.md` is complete

---

### 5. Backward Compatibility Guaranteed ⚠️

**Required:**

- [ ] Test that v1.9.0 chains verify with v1.9.1 code
- [ ] Test that v1.9.1 exports conform to v1 schemas
- [ ] No breaking changes to EPACK format

**Current status:** Need to generate test chains from v1.9.0

**Action:** Create reference test chains before freeze

---

### 6. Documentation Complete ✅

**Required:**

- [x] INTERFACE_CONTRACT.md
- [x] AUDITOR_QUICKSTART.md (in Commons/tek-audit)
- [x] Control register
- [x] Architecture docs
- [x] Threat model

**Status:** Documentation is comprehensive

---

### 7. Zero External Dependencies for Verification ✅

**Required:**

- [x] `verify_chain.py` works with Python stdlib + cryptography only
- [x] No database required
- [x] No network required
- [x] No TEK installation required

**Status:** Verifier is standalone

---

### 8. Migration Path Exists for Breaking Changes 🔄

**Required:**

- [ ] Process for adding new validators (non-breaking)
- [ ] Process for deprecating validators (with notice)
- [ ] Process for changing hash/signature algorithms

**Current status:** INTERFACE_CONTRACT defines process, needs tooling

**Action:** Create deprecation warning system before freeze

---

## Freeze Blockers (Must Fix Before v1.9.1)

### Blocker 1: End-to-End Verification Test ⚠️

**Problem:** Auditor toolkit hasn't been tested with real Commons chains

**Fix:**
1. Start Commons service
2. Create workspace + session
3. Post messages + checkpoint
4. Export chain + keys
5. Verify with CLI
6. Confirm PASS

**Timeline:** 1-2 hours

---

### Blocker 2: Reference Test Chains 🔄

**Problem:** No versioned reference chains for backward compatibility testing

**Fix:**
1. Generate 3 test chains with different governance outcomes
2. Store as `testdata/chains/v1_9_0/*.json`
3. Verify they pass with v1.9.1 code

**Timeline:** 1 hour

---

## Post-Freeze Actions

Once TEK is frozen at v1.9.1:

### 1. Tag and Release

```bash
cd tek/
git tag -a v1.9.1 -m "Kernel freeze: stable interface for external verification"
git push origin v1.9.1
```

### 2. Publish Auditor Toolkit

- GitHub: `imaginairium/tek/tek-audit/`
- Website: Link from main TEK docs
- Announce: "TEK now supports independent verification"

### 3. Update Commons Integration

- Commons imports TEK at `v1.9.1` (pinned)
- Commons changelog notes TEK freeze
- Commons tests verify against frozen schemas

### 4. Pivot to ImaginAIrium

**After freeze, no more kernel changes unless:**
- Security vulnerability
- Interface-breaking bug
- Versioned addition (minor/patch bump)

**Product development continues in ImaginAIrium without kernel dependency**

---

## Freeze Testing Protocol

### Test 1: Fresh Chain Verification

```bash
# Start Commons
cd commons/
uvicorn src.api.main:app --port 8080

# Create workspace + session (via ImaginAIrium or curl)
# Post messages
# Checkpoint publish

# Export
cd commons/
python tek-audit/export_chain.py --session-id <sid> --output /tmp/chain.json
python tek-audit/export_keys.py --output /tmp/keys.json

# Verify
python tek-audit/verify_chain.py /tmp/chain.json /tmp/keys.json
# Expected: Exit 0 (PASS)
```

### Test 2: Tamper Detection

```bash
# Edit chain.json (change a hash)
# Re-verify
python tek-audit/verify_chain.py /tmp/chain_tampered.json /tmp/keys.json
# Expected: Exit 1 (FAIL with forensic detail)
```

### Test 3: Schema Validation

```bash
# Validate exports against schemas
jsonschema -i /tmp/chain.json tek/schemas/epack/chain_export_v1.json
jsonschema -i /tmp/keys.json tek/schemas/epack/key_registry_export_v1.json
# Expected: Both pass
```

---

## Sign-Off Checklist

Before tagging v1.9.1, confirm:

- [ ] All freeze criteria met
- [ ] No blockers remain
- [ ] End-to-end verification tested
- [ ] Reference chains generated
- [ ] Schemas validated
- [ ] Documentation reviewed
- [ ] ImaginAIrium can build without kernel changes

---

## Freeze Decision

**Freeze authority:** Mark (kernel maintainer)

**Process:**
1. Complete all checklist items
2. Run full test protocol
3. Review with ImaginAIrium team
4. Tag v1.9.1
5. Announce freeze

**After freeze:** All kernel changes require RFC + version bump

---

## Current Status Summary

| Item | Status | Blocker? |
|------|--------|----------|
| Interface contract | ✅ Done | No |
| Versioned schemas | ✅ Done | No |
| Auditor toolkit | ⚠️ Exists, untested | **Yes** |
| Control register | ✅ Complete | No |
| Backward compat | 🔄 Needs test chains | **Yes** |
| Documentation | ✅ Complete | No |
| Zero dependencies | ✅ Verified | No |
| Migration path | 🔄 Process defined | No |

**Recommendation:** Fix 2 blockers (end-to-end test + reference chains), then freeze immediately.

---

**Next Steps:**

1. **Test full verification flow** (1-2 hours)
2. **Generate reference test chains** (1 hour)
3. **Tag v1.9.1** (immediate)
4. **Pivot to ImaginAIrium MVP** (now moving fast without kernel dependency)

---

**End of Checklist**
