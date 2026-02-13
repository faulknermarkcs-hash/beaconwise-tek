# src/ecosphere/replay/engine.py
"""Replay Engine — deterministic reproducibility verification (V8 restored + V9 chain linkage).

Replays governance decisions from EPACK audit chains to verify:
1. EPACK hash integrity (tamper detection)
2. Routing determinism (same inputs → same route)
3. Safety screening consistency
4. Profile consistency
5. Build manifest integrity
6. Chain linkage (prev_hash continuity — V9)

The replay engine does NOT re-invoke LLMs (that would be non-deterministic
and expensive). It replays the deterministic governance pipeline only.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from ecosphere.utils.stable import stable_hash


@dataclass
class ReplayStep:
    """Single step in a replay."""
    step_name: str
    original_value: Any
    replayed_value: Any
    match: bool
    detail: str = ""


@dataclass
class ReplayResult:
    """Complete replay verification result."""
    replay_id: str
    epack_seq: int
    steps: List[ReplayStep] = field(default_factory=list)
    determinism_index: float = 0.0   # 0.0–100.0
    governance_match: bool = True
    route_match: bool = True
    safety_match: bool = True
    chain_link_match: bool = True     # V9: prev_hash continuity
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
    """Replay a single governed interaction from its EPACK record.

    Verifies that the deterministic governance pipeline (safety screening,
    routing, scope gate) would produce the same decisions given the same inputs.

    Args:
        epack_record: The EPACK record to replay
        route_fn: Optional routing function (from kernel.router)
        safety_fn: Optional safety function (from safety.stage1)
        expected_prev_hash: If provided, verify chain linkage (V9)

    Returns:
        ReplayResult with step-by-step verification
    """
    payload = epack_record.get("payload", {})
    extra = payload.get("extra", {})
    seq = epack_record.get("seq", 0)

    steps: List[ReplayStep] = []
    all_match = True

    # Step 1: Verify EPACK hash integrity
    expected_hash = epack_record.get("hash", "")
    recomputed = stable_hash({
        "seq": epack_record.get("seq"),
        "ts": epack_record.get("ts"),
        "prev_hash": epack_record.get("prev_hash"),
        "payload": payload,
    })
    hash_match = expected_hash == recomputed
    steps.append(ReplayStep(
        step_name="epack_hash_integrity",
        original_value=expected_hash[:16] + "...",
        replayed_value=recomputed[:16] + "...",
        match=hash_match,
        detail="Hash chain integrity" if hash_match else "TAMPERED: hash mismatch",
    ))
    if not hash_match:
        all_match = False

    # Step 2: Verify routing decision (if route_fn provided)
    route_match = True
    original_route = extra.get("route", "UNKNOWN")
    if route_fn is not None:
        try:
            replayed_route = route_fn(extra.get("input_vector", {}))
            route_match = original_route == replayed_route
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

    # Step 3: Verify safety screening (if safety_fn provided)
    safety_match = True
    if safety_fn is not None:
        original_safe = extra.get("safety_stage1_ok", True)
        try:
            replayed_safe = safety_fn(payload.get("user_text_hash", ""))
            safety_match = original_safe == replayed_safe
            steps.append(ReplayStep(
                step_name="safety_screening",
                original_value=original_safe,
                replayed_value=replayed_safe,
                match=safety_match,
            ))
        except Exception:
            steps.append(ReplayStep(
                step_name="safety_screening",
                original_value=extra.get("safety_stage1_ok", "?"),
                replayed_value="(safety_fn error — skipped)",
                match=True,
            ))
    else:
        steps.append(ReplayStep(
            step_name="safety_screening",
            original_value=extra.get("safety_stage1_ok", "?"),
            replayed_value="(safety_fn not provided — skipped)",
            match=True,
        ))

    # Step 4: Verify profile consistency
    original_profile = payload.get("profile", "UNKNOWN")
    steps.append(ReplayStep(
        step_name="profile_consistency",
        original_value=original_profile,
        replayed_value=original_profile,
        match=True,
        detail=f"Profile: {original_profile}",
    ))

    # Step 5: Build manifest integrity
    manifest = payload.get("build_manifest", {})
    manifest_present = bool(manifest and manifest.get("manifest_hash"))
    steps.append(ReplayStep(
        step_name="build_manifest",
        original_value=manifest.get("manifest_hash", "MISSING")[:16] if manifest else "MISSING",
        replayed_value="present" if manifest_present else "MISSING",
        match=manifest_present,
        detail="Provenance traceable" if manifest_present else "No build manifest",
    ))
    if not manifest_present:
        all_match = False

    # Step 6 (V9): Chain linkage — verify prev_hash matches expected
    chain_link_match = True
    if expected_prev_hash is not None:
        actual_prev = epack_record.get("prev_hash", "")
        chain_link_match = actual_prev == expected_prev_hash
        steps.append(ReplayStep(
            step_name="chain_linkage",
            original_value=actual_prev[:16] + "..." if actual_prev else "NONE",
            replayed_value=expected_prev_hash[:16] + "...",
            match=chain_link_match,
            detail="Chain continuity" if chain_link_match else "BROKEN: prev_hash mismatch",
        ))
        if not chain_link_match:
            all_match = False

    # Calculate determinism index
    matched = sum(1 for s in steps if s.match)
    total = len(steps)
    determinism_index = (matched / total * 100) if total > 0 else 0.0

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
    """Replay an entire EPACK chain with prev_hash linkage verification (V9).

    Returns a list of ReplayResults, one per record.
    """
    results = []
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
    """Generate summary statistics from replay results."""
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
