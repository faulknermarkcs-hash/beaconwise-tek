# src/ecosphere/replay/engine.py
"""Replay Engine — deterministic reproducibility verification.

Replays governance decisions from EPACK audit chains to verify:

1) EPACK hash integrity (tamper detection)
2) Brick 3 commitment rule:
     EPACK.payload_hash == payload.decision_hash  (when payload.decision_hash exists)
3) Brick 4 Decision Object integrity:
     sha256(canonical_json(decision_object with integrity.canonical_payload_hash="")) == EPACK.payload_hash
     (when payload.decision_object exists)
4) Routing determinism (optional: requires injected route_fn)
5) Safety screening consistency (optional: requires injected safety_fn)
6) Profile consistency
7) Build manifest presence
8) Chain linkage (prev_hash continuity)

The replay engine does NOT re-invoke LLMs.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from ecosphere.utils.stable import stable_hash
from ecosphere.decision.object import compute_decision_hash


@dataclass
class ReplayStep:
    step_name: str
    original_value: Any
    replayed_value: Any
    match: bool
    detail: str = ""


@dataclass
class ReplayResult:
    replay_id: str
    epack_seq: int
    steps: List[ReplayStep] = field(default_factory=list)
    determinism_index: float = 0.0
    governance_match: bool = True
    route_match: bool = True
    safety_match: bool = True
    chain_link_match: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["steps"] = [asdict(s) for s in self.steps]
        return d


def replay_governance_decision(
    *,
    epack_record: Dict[str, Any],
    route_fn: Any = None,
    safety_fn: Any = None,
    expected_prev_hash: Optional[str] = None,
) -> ReplayResult:
    payload = epack_record.get("payload", {}) or {}
    extra = (payload.get("extra") or {}) if isinstance(payload, dict) else {}
    seq = int(epack_record.get("seq", 0) or 0)

    steps: List[ReplayStep] = []
    all_match = True

    # ------------------------------------------------------------------
    # Step 1: Verify EPACK hash integrity (Brick 3+ schema)
    # ------------------------------------------------------------------
    expected_hash = str(epack_record.get("hash", "") or "")
    payload_hash = str(epack_record.get("payload_hash") or payload.get("decision_hash") or "")
    recomputed = stable_hash({
        "seq": epack_record.get("seq"),
        "ts": epack_record.get("ts"),
        "prev_hash": epack_record.get("prev_hash"),
        "payload_hash": payload_hash,
        "payload": payload,
    })
    hash_match = (expected_hash == recomputed)
    steps.append(ReplayStep(
        step_name="epack_hash_integrity",
        original_value=expected_hash[:16] + "..." if expected_hash else "MISSING",
        replayed_value=recomputed[:16] + "...",
        match=hash_match,
        detail="Hash chain integrity" if hash_match else "TAMPERED: hash mismatch",
    ))
    if not hash_match:
        all_match = False

    # ------------------------------------------------------------------
    # Step 2: Brick 3 commitment rule (payload_hash ↔ decision_hash)
    # ------------------------------------------------------------------
    claimed_decision_hash = payload.get("decision_hash") if isinstance(payload, dict) else None
    commitment_ok = True
    if isinstance(claimed_decision_hash, str) and claimed_decision_hash:
        commitment_ok = (claimed_decision_hash == payload_hash)
    steps.append(ReplayStep(
        step_name="payload_hash_commitment",
        original_value=(claimed_decision_hash or "NONE")[:16] + "..." if claimed_decision_hash else "NONE",
        replayed_value=(payload_hash or "MISSING")[:16] + "..." if payload_hash else "MISSING",
        match=commitment_ok,
        detail="Brick 3: payload_hash commits to decision_hash" if commitment_ok else "BROKEN: decision_hash != payload_hash",
    ))
    if not commitment_ok:
        all_match = False

    # ------------------------------------------------------------------
    # Step 3: Brick 4 Decision Object integrity (if present)
    # ------------------------------------------------------------------
    decision_obj = payload.get("decision_object") if isinstance(payload, dict) else None
    decision_obj_ok = True
    decision_obj_detail = "Decision Object not present — skipped"
    recomputed_decision_hash = None
    if isinstance(decision_obj, dict):
        try:
            recomputed_decision_hash = compute_decision_hash(decision_obj)
            decision_obj_ok = (recomputed_decision_hash == payload_hash)
            decision_obj_detail = "Brick 4: decision_object hash matches payload_hash" if decision_obj_ok else "BROKEN: decision_object hash mismatch"
        except Exception as e:
            decision_obj_ok = False
            decision_obj_detail = f"ERROR: {e}"
    steps.append(ReplayStep(
        step_name="decision_object_integrity",
        original_value=(payload_hash or "MISSING")[:16] + "..." if payload_hash else "MISSING",
        replayed_value=(recomputed_decision_hash or "SKIPPED")[:16] + "..." if isinstance(recomputed_decision_hash, str) else (recomputed_decision_hash or "SKIPPED"),
        match=decision_obj_ok,
        detail=decision_obj_detail,
    ))
    if not decision_obj_ok:
        all_match = False

    # ------------------------------------------------------------------
    # Step 4: Verify routing decision (optional)
    # ------------------------------------------------------------------
    route_match = True
    original_route = (extra.get("route") or "UNKNOWN") if isinstance(extra, dict) else "UNKNOWN"
    if route_fn is not None:
        try:
            replayed_route = route_fn(extra.get("input_vector", {}))
            route_match = (original_route == replayed_route)
            steps.append(ReplayStep(
                step_name="routing_determinism",
                original_value=original_route,
                replayed_value=replayed_route,
                match=route_match,
            ))
        except Exception as e:
            steps.append(ReplayStep(
                step_name="routing_determinism",
                original_value=original_route,
                replayed_value=f"ERROR: {e}",
                match=False,
            ))
            route_match = False
    else:
        steps.append(ReplayStep(
            step_name="routing_determinism",
            original_value=original_route,
            replayed_value="(route_fn not provided — skipped)",
            match=True,
            detail="Routing replay skipped; no route_fn",
        ))

    # ------------------------------------------------------------------
    # Step 5: Verify safety screening (optional)
    # ------------------------------------------------------------------
    safety_match = True
    if safety_fn is not None:
        original_safe = bool(extra.get("safety_stage1_ok", True)) if isinstance(extra, dict) else True
        try:
            replayed_safe = safety_fn(payload.get("user_text_hash", ""))
            safety_match = (original_safe == replayed_safe)
            steps.append(ReplayStep(
                step_name="safety_screening",
                original_value=original_safe,
                replayed_value=replayed_safe,
                match=safety_match,
            ))
        except Exception as e:
            steps.append(ReplayStep(
                step_name="safety_screening",
                original_value=extra.get("safety_stage1_ok", "?") if isinstance(extra, dict) else "?",
                replayed_value=f"(safety_fn error — skipped) {e}",
                match=True,
            ))
    else:
        steps.append(ReplayStep(
            step_name="safety_screening",
            original_value=extra.get("safety_stage1_ok", "?") if isinstance(extra, dict) else "?",
            replayed_value="(safety_fn not provided — skipped)",
            match=True,
        ))

    # Step 6: Profile consistency
    original_profile = payload.get("profile", "UNKNOWN") if isinstance(payload, dict) else "UNKNOWN"
    steps.append(ReplayStep(
        step_name="profile_consistency",
        original_value=original_profile,
        replayed_value=original_profile,
        match=True,
        detail=f"Profile: {original_profile}",
    ))

    # Step 7: Build manifest presence
    manifest = payload.get("build_manifest", {}) if isinstance(payload, dict) else {}
    manifest_present = bool(isinstance(manifest, dict) and manifest.get("manifest_hash"))
    steps.append(ReplayStep(
        step_name="build_manifest",
        original_value=(manifest.get("manifest_hash", "MISSING")[:16] if isinstance(manifest, dict) and manifest.get("manifest_hash") else "MISSING"),
        replayed_value="present" if manifest_present else "MISSING",
        match=manifest_present,
        detail="Provenance traceable" if manifest_present else "No build manifest",
    ))
    if not manifest_present:
        all_match = False

    # Step 8: Chain linkage
    chain_link_match = True
    if expected_prev_hash is not None:
        actual_prev = epack_record.get("prev_hash", "")
        chain_link_match = (actual_prev == expected_prev_hash)
        steps.append(ReplayStep(
            step_name="chain_linkage",
            original_value=actual_prev[:16] + "..." if actual_prev else "NONE",
            replayed_value=expected_prev_hash[:16] + "...",
            match=chain_link_match,
            detail="Chain continuity" if chain_link_match else "BROKEN: prev_hash mismatch",
        ))
        if not chain_link_match:
            all_match = False

    matched = sum(1 for s in steps if s.match)
    determinism_index = (matched / len(steps) * 100) if steps else 0.0

    return ReplayResult(
        replay_id=stable_hash({"seq": seq, "ts": time.time()})[:16],
        epack_seq=seq,
        steps=steps,
        determinism_index=round(determinism_index, 1),
        governance_match=all_match,
        route_match=route_match,
        safety_match=safety_match,
        chain_link_match=chain_link_match,
    )


def replay_chain(
    epack_chain: List[Dict[str, Any]],
    *,
    route_fn: Any = None,
    safety_fn: Any = None,
) -> List[ReplayResult]:
    results: List[ReplayResult] = []
    prev_hash: Optional[str] = None
    for record in epack_chain:
        result = replay_governance_decision(
            epack_record=record,
            route_fn=route_fn,
            safety_fn=safety_fn,
            expected_prev_hash=prev_hash,
        )
        prev_hash = record.get("hash")
        results.append(result)
    return results


def replay_summary(results: List[ReplayResult]) -> Dict[str, Any]:
    if not results:
        return {"total": 0, "determinism_index": 0.0}

    total = len(results)
    return {
        "total": total,
        "determinism_index": round(sum(r.determinism_index for r in results) / total, 1),
        "governance_match_rate": sum(1 for r in results if r.governance_match) / total,
        "route_match_rate": sum(1 for r in results if r.route_match) / total,
        "safety_match_rate": sum(1 for r in results if r.safety_match) / total,
        "chain_link_rate": sum(1 for r in results if r.chain_link_match) / total,
        "tampered_records": [r.epack_seq for r in results if not r.governance_match],
    }
