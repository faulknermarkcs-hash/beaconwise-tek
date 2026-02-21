# src/ecosphere/replay/engine.py
"""Replay Engine — deterministic reproducibility verification (Brick 4).

Replays governance decisions from EPACK audit chains to verify:
1. EPACK hash integrity (tamper detection)
2. Chain linkage (prev_hash continuity)
3. Brick 3 commitment integrity:
   - payload_hash equals payload.decision_hash when present
   - payload.decision_object canonical hash matches the commitment when present

This replay engine does NOT re-invoke LLMs.
"""
from __future__ import annotations

import time
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from ecosphere.utils.stable import stable_hash


def _canonical_dumps(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()


def _compute_decision_hash(decision_obj: Dict[str, Any]) -> str:
    """Mirror Commons/TEK decision canonical rule."""
    d = json.loads(_canonical_dumps(decision_obj).decode("utf-8"))
    integ = (d.get("integrity") or {})
    integ["canonical_payload_hash"] = ""
    d["integrity"] = integ
    return _sha256_hex(_canonical_dumps(d))


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
    chain_link_match: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["steps"] = [asdict(s) for s in self.steps]
        return d


def _recompute_epack_hash(epack_record: Dict[str, Any]) -> str:
    """Recompute EPACK chain hash per current EPACK schema (Brick 3+).

    TEK epack.chain hashes:
      stable_hash({seq, ts, prev_hash, payload_hash, payload})
    """
    payload = epack_record.get("payload", {})
    return stable_hash({
        "seq": epack_record.get("seq"),
        "ts": epack_record.get("ts"),
        "prev_hash": epack_record.get("prev_hash"),
        "payload_hash": epack_record.get("payload_hash"),
        "payload": payload,
    })


def replay_governance_decision(
    *,
    epack_record: Dict[str, Any],
    expected_prev_hash: Optional[str] = None,
) -> ReplayResult:
    payload = epack_record.get("payload", {})
    seq = int(epack_record.get("seq", 0))

    steps: List[ReplayStep] = []
    all_match = True

    # 1) EPACK hash integrity
    expected_hash = epack_record.get("hash", "")
    recomputed = _recompute_epack_hash(epack_record)
    hash_match = (expected_hash == recomputed)
    steps.append(ReplayStep(
        step_name="epack_hash_integrity",
        original_value=(expected_hash[:16] + "...") if expected_hash else "MISSING",
        replayed_value=(recomputed[:16] + "...") if recomputed else "MISSING",
        match=hash_match,
        detail="Hash chain integrity" if hash_match else "TAMPERED: hash mismatch",
    ))
    if not hash_match:
        all_match = False

    # 2) Chain linkage (prev_hash continuity)
    chain_link_match = True
    if expected_prev_hash is not None:
        actual_prev = epack_record.get("prev_hash", "")
        chain_link_match = (actual_prev == expected_prev_hash)
        steps.append(ReplayStep(
            step_name="chain_linkage",
            original_value=(actual_prev[:16] + "...") if actual_prev else "NONE",
            replayed_value=(expected_prev_hash[:16] + "...") if expected_prev_hash else "NONE",
            match=chain_link_match,
            detail="Chain continuity" if chain_link_match else "BROKEN: prev_hash mismatch",
        ))
        if not chain_link_match:
            all_match = False

    # 3) Brick 3 commitment check: payload_hash == decision_hash
    payload_hash = epack_record.get("payload_hash")
    decision_hash = payload.get("decision_hash")
    commit_ok = True
    if isinstance(decision_hash, str) and decision_hash:
        commit_ok = (isinstance(payload_hash, str) and payload_hash == decision_hash)
        steps.append(ReplayStep(
            step_name="commitment_payload_hash_equals_decision_hash",
            original_value=str(payload_hash),
            replayed_value=str(decision_hash),
            match=commit_ok,
            detail="Brick 3 commitment" if commit_ok else "BROKEN: payload_hash != decision_hash",
        ))
        if not commit_ok:
            all_match = False

    # 4) Decision Object integrity (if present): recompute canonical hash matches commitment
    decision_obj = payload.get("decision_object")
    if isinstance(decision_obj, dict):
        recomputed_dec_hash = _compute_decision_hash(decision_obj)
        integrity_ok = (recomputed_dec_hash == decision_hash == payload_hash)
        steps.append(ReplayStep(
            step_name="decision_object_canonical_hash",
            original_value=str(decision_hash),
            replayed_value=str(recomputed_dec_hash),
            match=integrity_ok,
            detail="Decision object canonical hash" if integrity_ok else "BROKEN: decision object hash mismatch",
        ))
        if not integrity_ok:
            all_match = False

    matched = sum(1 for s in steps if s.match)
    total = len(steps)
    determinism_index = (matched / total * 100) if total else 0.0

    return ReplayResult(
        replay_id=stable_hash({"seq": seq, "ts": time.time()})[:16],
        epack_seq=seq,
        steps=steps,
        determinism_index=round(determinism_index, 1),
        governance_match=all_match,
        chain_link_match=chain_link_match,
    )


def replay_chain(epack_chain: List[Dict[str, Any]]) -> List[ReplayResult]:
    results: List[ReplayResult] = []
    prev_hash: Optional[str] = None
    for record in epack_chain:
        result = replay_governance_decision(epack_record=record, expected_prev_hash=prev_hash)
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
        "chain_link_rate": sum(1 for r in results if r.chain_link_match) / total,
        "tampered_records": [r.epack_seq for r in results if not r.governance_match],
    }
