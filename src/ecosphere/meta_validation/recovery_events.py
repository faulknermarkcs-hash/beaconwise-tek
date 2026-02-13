"""Recovery EPACK Event Emitter.

Wires recovery decisions, applications, verifications, and rollbacks
into the existing EPACK audit chain via emit_stage_event.

Event types (matching enterprise policy audit.epack_event_types):
  RECOVERY_TRIGGERED  — trigger condition met
  RECOVERY_DECISION   — engine selected (or rejected) a plan
  RECOVERY_APPLIED    — routing patch applied to consensus config
  RECOVERY_VERIFIED   — post-recovery verification result
  RECOVERY_ROLLBACK   — verification failed, rollback recommended
  CIRCUIT_BREAKER     — breaker state change (open/close/half-open)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ecosphere.consensus.ledger.hooks import emit_stage_event


def emit_recovery_triggered(
    *,
    epack: str,
    run_id: str,
    reason: str,
    tsi_before: float,
    tsi_forecast: float,
    prev_hash: Optional[str] = None,
) -> str:
    return emit_stage_event(
        epack=epack, run_id=run_id, stage="RECOVERY_TRIGGERED",
        payload={"reason": reason, "tsi_before": tsi_before, "tsi_forecast": tsi_forecast},
        prev_hash=prev_hash,
    )


def emit_recovery_decision(
    *,
    epack: str,
    run_id: str,
    decision: Dict[str, Any],
    prev_hash: Optional[str] = None,
) -> str:
    return emit_stage_event(
        epack=epack, run_id=run_id, stage="RECOVERY_DECISION",
        payload=decision,
        prev_hash=prev_hash,
    )


def emit_recovery_applied(
    *,
    epack: str,
    run_id: str,
    plan_name: str,
    routing_patch: Dict[str, Any],
    prev_hash: Optional[str] = None,
) -> str:
    return emit_stage_event(
        epack=epack, run_id=run_id, stage="RECOVERY_APPLIED",
        payload={"plan_name": plan_name, "routing_patch": routing_patch},
        prev_hash=prev_hash,
    )


def emit_recovery_verified(
    *,
    epack: str,
    run_id: str,
    verification: Dict[str, Any],
    prev_hash: Optional[str] = None,
) -> str:
    return emit_stage_event(
        epack=epack, run_id=run_id, stage="RECOVERY_VERIFIED",
        payload=verification,
        prev_hash=prev_hash,
    )


def emit_recovery_rollback(
    *,
    epack: str,
    run_id: str,
    plan_name: str,
    reasons: list,
    prev_hash: Optional[str] = None,
) -> str:
    return emit_stage_event(
        epack=epack, run_id=run_id, stage="RECOVERY_ROLLBACK",
        payload={"plan_name": plan_name, "reasons": reasons},
        prev_hash=prev_hash,
    )


def emit_circuit_breaker_event(
    *,
    epack: str,
    run_id: str,
    plan_name: str,
    breaker_state: str,
    consecutive_failures: int,
    prev_hash: Optional[str] = None,
) -> str:
    return emit_stage_event(
        epack=epack, run_id=run_id, stage="CIRCUIT_BREAKER",
        payload={
            "plan_name": plan_name,
            "breaker_state": breaker_state,
            "consecutive_failures": consecutive_failures,
        },
        prev_hash=prev_hash,
    )
