"""Compile resilience_policy DSL block into runtime objects.

Takes the resilience_policy section from a governance YAML and builds
the RecoveryEngine, DampingStabilizer, CircuitBreaker, TSITracker,
PostRecoveryVerifier, and plan objects needed by ResilienceRuntime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .recovery_engine import RecoveryEngine, RecoveryBudgets, RecoveryPlan, RecoveryTargets
from .damping_stabilizer import DampingStabilizer, PIDParams
from .circuit_breaker import CircuitBreaker, BreakerConfig
from .tsi_tracker import TSITracker
from .post_recovery_verifier import PostRecoveryVerifier, VerificationConfig
from .resilience_runtime import ResilienceRuntime


@dataclass
class CompiledResilience:
    enabled: bool
    runtime: Optional[ResilienceRuntime]
    raw: Dict[str, Any]
    errors: List[str]


def _parse_plans(plans_block: Dict[str, Any]) -> List[RecoveryPlan]:
    """Parse tier_1/tier_2/tier_3 plan blocks from policy YAML."""
    result: List[RecoveryPlan] = []
    for tier_key in ("tier_1", "tier_2", "tier_3"):
        tier_num = int(tier_key.split("_")[1])
        tier_plans = plans_block.get(tier_key, [])
        if not isinstance(tier_plans, list):
            continue
        for p in tier_plans:
            if not isinstance(p, dict):
                continue
            pred = p.get("predicted", {})
            result.append(RecoveryPlan(
                name=p.get("name", p.get("id", f"unnamed_{tier_key}")),
                tier=tier_num,
                predicted_tsi_median=float(pred.get("tsi_median", 0.72)),
                predicted_tsi_low=float(pred.get("tsi_low", 0.65)),
                predicted_tsi_high=float(pred.get("tsi_high", 0.80)),
                predicted_latency_ms=int(pred.get("latency_ms", 200)),
                predicted_cost_usd=float(pred.get("cost_usd", 0.01)),
                predicted_independence_gain=float(pred.get("independence_gain", 0.0)),
                routing_patch=p.get("routing_patch", {}),
            ))
    return result


def compile_resilience_policy(policy: Dict[str, Any]) -> CompiledResilience:
    """Compile the full resilience_policy section into a ResilienceRuntime."""
    res = (policy or {}).get("resilience_policy") or {}
    if not res.get("enabled", False):
        return CompiledResilience(enabled=False, runtime=None, raw=res, errors=[])

    errors: List[str] = []
    try:
        # Targets
        tsi_cfg = res.get("targets", {}).get("tsi", {})
        rec_cfg = res.get("targets", {}).get("recovery", {})
        targets = RecoveryTargets(
            tsi_target=float(tsi_cfg.get("target", 0.75)),
            tsi_min=float(tsi_cfg.get("min", 0.70)),
            tsi_critical=float(tsi_cfg.get("critical", 0.55)),
            max_recovery_minutes=int(rec_cfg.get("max_minutes", 15)),
        )

        # Budgets
        budgets = RecoveryBudgets(
            latency_ms_max=int(res.get("budgets", {}).get("latency_ms_max", 800)),
            cost_usd_max=float(res.get("budgets", {}).get("cost_usd_max", 0.50)),
        )

        # Scoring weights
        scoring = res.get("scoring", {}).get("weights", {})
        engine = RecoveryEngine(
            budgets=budgets,
            targets=targets,
            diversity_bonus_weight=float(scoring.get("diversity_bonus", 0.15)),
            penalty_latency_weight=float(scoring.get("latency_penalty_per_ms", 0.0005)),
            penalty_cost_weight=float(scoring.get("cost_penalty_per_usd", 0.25)),
            confidence_low_penalty_weight=float(scoring.get("confidence_low_penalty", 0.30)),
            tier_penalties=res.get("scoring", {}).get("tier_penalties") or None,
        )

        # Plans
        plans = _parse_plans(res.get("plans", {}))

        # Damping
        damping = None
        dcfg = res.get("damping", {})
        if dcfg.get("enabled", True):
            pid = PIDParams(
                kp=float(dcfg.get("pid", {}).get("kp", 0.5)),
                ki=float(dcfg.get("pid", {}).get("ki", 0.2)),
                kd=float(dcfg.get("pid", {}).get("kd", 0.1)),
                integral_cap=float(dcfg.get("pid", {}).get("integral_cap", 2.0)),
            )
            damping = DampingStabilizer(
                pid=pid,
                max_oscillation=float(dcfg.get("max_oscillation", 0.15)),
                cooldown_seconds=int(dcfg.get("cooldown_seconds", 60)),
            )

        # Circuit breaker
        circuit_breaker = CircuitBreaker(BreakerConfig(
            failure_threshold=3,
            cooldown_seconds=120.0,
        ))

        # TSI tracker
        tsi_tracker = TSITracker(window_size=20)

        # Post-recovery verifier
        audit_cfg = res.get("audit", {})
        verify_cfg = audit_cfg.get("verify_post_recovery", {}) if isinstance(audit_cfg, dict) else {}
        verifier = PostRecoveryVerifier(
            config=VerificationConfig(
                replay_samples=int(verify_cfg.get("replay_samples", 3)),
                mvi_check=bool(verify_cfg.get("mvi_check", True)),
            ),
            targets=targets,
        )

        runtime = ResilienceRuntime(
            engine=engine,
            plans=plans,
            damping=damping,
            circuit_breaker=circuit_breaker,
            tsi_tracker=tsi_tracker,
            verifier=verifier,
            enabled=True,
        )

        return CompiledResilience(enabled=True, runtime=runtime, raw=res, errors=errors)
    except Exception as e:
        errors.append(str(e))
        return CompiledResilience(enabled=False, runtime=None, raw=res, errors=errors)
