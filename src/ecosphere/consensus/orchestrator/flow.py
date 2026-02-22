# src/ecosphere/consensus/orchestrator/flow.py
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from pydantic import ValidationError

from ecosphere.consensus.adapters.factory import build_adapter
from ecosphere.consensus.config import ConsensusConfig, ARU
from ecosphere.consensus.ledger.hooks import emit_stage_event
from ecosphere.consensus.schemas import PrimaryOutput, SynthesizerOutput
from ecosphere.consensus.verification.types import VerificationContext, PUBLIC_CONTEXT
from ecosphere.consensus.gates.scope_gate import ScopeGateConfig, scope_gate_v1
from ecosphere.consensus.orchestrator.stage_rewrite import stage_rewrite_once


@dataclass
class ConsensusResult:
    status: str
    run_id: str
    epack: str
    aru: str
    output: Optional[Union[PrimaryOutput, SynthesizerOutput]] = None
    gate: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timings: Optional[Dict[str, float]] = None
    debate_outputs: Optional[Dict[str, Any]] = None


def _render_prompt(template: str, vars: Dict[str, str]) -> str:
    # Simple str.format rendering (templates are controlled by repo)
    return template.format(**vars)


async def _parse_with_repair(
    *,
    rid: str,
    epack: str,
    adapter,
    target_model,
    raw_text: str,
    repair_template: str,
    max_attempts: int,
    aru: str,
) -> Any:
    # Try parse JSON directly
    data = adapter.try_parse_json(raw_text)
    if data is not None:
        try:
            return target_model.model_validate(data)
        except ValidationError:
            pass

    bad = raw_text
    for attempt in range(max_attempts):
        repair_prompt = _render_prompt(
            repair_template,
            {"RUN_ID": rid, "EPACK": epack, "ARU": aru, "BAD_TEXT": bad[:4000]},
        )
        fixed_text, _ = await adapter.generate_text(prompt=repair_prompt, temperature=0.0, timeout_s=30)
        data = adapter.try_parse_json(fixed_text)
        if data is None:
            bad = fixed_text
            continue
        try:
            return target_model.model_validate(data)
        except ValidationError:
            bad = fixed_text
            continue
    raise ValueError("Failed to parse output as valid JSON after repair attempts")


async def run_consensus(
    *,
    user_query: str,
    aru: str = ARU.ANSWER.value,
    high_stakes: bool = False,
    epack: str,
    config: ConsensusConfig,
    verification: Optional[VerificationContext] = None,
    run_id: Optional[str] = None,
) -> ConsensusResult:
    rid = run_id or uuid.uuid4().hex
    verification = verification or PUBLIC_CONTEXT

    t0 = time.time()
    timings: Dict[str, float] = {}

    emit_stage_event(
        epack=epack,
        run_id=rid,
        stage="tecl.start",
        payload={
            "aru": aru,
            "high_stakes": high_stakes,
            "verification": {"verified": verification.verified, "role": verification.role, "role_level": verification.role_level},
            "primary_model": f"{config.primary.provider}:{config.primary.model}",
        },
    )


# ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    # Brick 6.1: 2-pass debate (optional)
    # If enabled, run two independent answers (defender/critic) in parallel,
    # then synthesize once. This reduces latency vs multi-round debate.
    # ──────────────────────────────────────────────────────────────────

    if bool(config.enable_debate and config.debate):
        debate = config.debate

        defender_adapter = build_adapter(debate.defender_model)
        critic_adapter   = build_adapter(debate.critic_model)

        # Render two independent prompts using the same PrimaryOutput schema.
        defender_prompt = _render_prompt(
            config.prompts.primary_template,
            {
                "RUN_ID": rid,
                "EPACK": epack,
                "ARU": aru,
                "USER_QUERY": user_query + "\n\n(ROLE: DEFENDER — provide the best direct answer.)",
                "VERIFIED": str(verification.verified).lower(),
                "ROLE": verification.role,
                "ROLE_LEVEL": str(verification.role_level),
                "SCOPE": verification.scope or "none",
            },
        )
        critic_prompt = _render_prompt(
            config.prompts.primary_template,
            {
                "RUN_ID": rid,
                "EPACK": epack,
                "ARU": aru,
                "USER_QUERY": user_query + "\n\n(ROLE: CRITIC — challenge assumptions, note uncertainties, propose alternatives.)",
                "VERIFIED": str(verification.verified).lower(),
                "ROLE": verification.role,
                "ROLE_LEVEL": str(verification.role_level),
                "SCOPE": verification.scope or "none",
            },
        )

        t1 = time.time()
        raw_def, meta_def, raw_cri, meta_cri = await asyncio.gather(
            defender_adapter.generate_text(prompt=defender_prompt, temperature=config.primary_temperature, timeout_s=config.primary_timeout_s),
            critic_adapter.generate_text(prompt=critic_prompt, temperature=config.primary_temperature, timeout_s=config.primary_timeout_s),
        )
        # asyncio.gather returns tuples; normalize
        # (raw_text, meta)
        raw_text_def, meta_def = raw_def
        raw_text_cri, meta_cri = raw_cri
        timings["debate_primary_s"] = time.time() - t1

        emit_stage_event(epack=epack, run_id=rid, stage="tecl.debate.defender.raw",
                         payload={"meta": meta_def, "raw_preview": raw_text_def[:200]})
        emit_stage_event(epack=epack, run_id=rid, stage="tecl.debate.critic.raw",
                         payload={"meta": meta_cri, "raw_preview": raw_text_cri[:200]})

        try:
            defender_out = await _parse_with_repair(
                rid=rid, epack=epack, adapter=defender_adapter, target_model=PrimaryOutput,
                raw_text=raw_text_def, repair_template=config.prompts.repair_template,
                max_attempts=config.max_repair_attempts, aru=aru,
            )
            critic_out = await _parse_with_repair(
                rid=rid, epack=epack, adapter=critic_adapter, target_model=PrimaryOutput,
                raw_text=raw_text_cri, repair_template=config.prompts.repair_template,
                max_attempts=config.max_repair_attempts, aru=aru,
            )
        except Exception as e:
            return ConsensusResult(
                status="REFUSE",
                run_id=rid,
                epack=epack,
                aru=aru,
                output=None,
                gate={"parse_error": repr(e)},
                error="Failed to parse debate outputs",
                timings={"total_s": time.time() - t0, **timings},
            )

        # Synthesizer (arbiter) — single pass
        synth_adapter = build_adapter(debate.synthesizer_model)
        synth_prompt = (
            "You are the Transparency Ecosphere Consensus Layer synthesizer (arbiter).\n"
            "Return ONLY valid JSON for SynthesizerOutput with fields: run_id, epack, aru, answer, reasoning_trace, overall_confidence.\n"
            "Use the user query + the two independent model outputs below.\n"
            "Prefer evidence-backed claims, highlight uncertainty, and resolve conflicts.\n"
            f"RUN_ID={rid} EPACK={epack} ARU={aru}.\n\n"
            f"USER_QUERY:\n{user_query}\n\n"
            "DEFENDER_OUTPUT (PrimaryOutput JSON):\n"
            f"{defender_out.model_dump_json()}\n\n"
            "CRITIC_OUTPUT (PrimaryOutput JSON):\n"
            f"{critic_out.model_dump_json()}\n"
        )

        t2 = time.time()
        raw_text, meta = await synth_adapter.generate_text(prompt=synth_prompt, temperature=0.0, timeout_s=config.primary_timeout_s)
        timings["synthesizer_s"] = time.time() - t2

        emit_stage_event(
            epack=epack,
            run_id=rid,
            stage="tecl.synthesizer.raw",
            payload={"meta": meta, "raw_preview": raw_text[:200]},
        )

        try:
            primary = await _parse_with_repair(
                rid=rid,
                epack=epack,
                adapter=synth_adapter,
                target_model=SynthesizerOutput,
                raw_text=raw_text,
                repair_template=config.prompts.repair_template,
                max_attempts=config.max_repair_attempts,
                aru=aru,
            )
        except Exception as e:
            return ConsensusResult(
                status="REFUSE",
                run_id=rid,
                epack=epack,
                aru=aru,
                output=None,
                gate={"parse_error": repr(e)},
                error="Failed to parse synthesizer output",
                timings={"total_s": time.time() - t0, **timings},
            )

        gate_debate: Dict[str, Any] = {
            "debate_models": {
                "defender": f"{debate.defender_model.provider}:{debate.defender_model.model}",
                "critic": f"{debate.critic_model.provider}:{debate.critic_model.model}",
                "synthesizer": f"{debate.synthesizer_model.provider}:{debate.synthesizer_model.model}",
            }
        }

    else:
        adapter = build_adapter(config.primary)

        prompt = _render_prompt(
            config.prompts.primary_template,
            {
                "RUN_ID": rid,
                "EPACK": epack,
                "ARU": aru,
                "USER_QUERY": user_query,
                "VERIFIED": str(verification.verified).lower(),
                "ROLE": verification.role,
                "ROLE_LEVEL": str(verification.role_level),
                "SCOPE": verification.scope or "none",
            },
        )

        t1 = time.time()
        raw_text, meta = await adapter.generate_text(
            prompt=prompt,
            temperature=config.primary_temperature,
            timeout_s=config.primary_timeout_s,
        )
        timings["primary_s"] = time.time() - t1

        emit_stage_event(
            epack=epack,
            run_id=rid,
            stage="tecl.primary.raw",
            payload={"meta": meta, "raw_preview": raw_text[:200]},
        )

        try:
            primary = await _parse_with_repair(
                rid=rid,
                epack=epack,
                adapter=adapter,
                target_model=PrimaryOutput,
                raw_text=raw_text,
                repair_template=config.prompts.repair_template,
                max_attempts=config.max_repair_attempts,
                aru=aru,
            )
        except Exception as e:
            return ConsensusResult(
                status="REFUSE",
                run_id=rid,
                epack=epack,
                aru=aru,
                output=None,
                gate={"parse_error": repr(e)},
                error="Failed to parse model output",
                timings={"total_s": time.time() - t0, **timings},
            )

        gate_debate = {}
    # Anchor checks
    if primary.run_id != rid or primary.epack != epack:
        return ConsensusResult(
            status="REFUSE",
            run_id=rid,
            epack=epack,
            aru=aru,
            output=None,
            gate={"anchor_mismatch": {"expected": {"run_id": rid, "epack": epack}, "got": {"run_id": primary.run_id, "epack": primary.epack}}},
            error="Anchor mismatch",
            timings={"total_s": time.time() - t0, **timings},
        )

    # Scope gate enforcement (PR-C behavior)
    scope_cfg = ScopeGateConfig(domain="general")
    scope_result = scope_gate_v1(output=primary, verification=verification, config=scope_cfg, epack=epack, run_id=rid)
    gate: Dict[str, Any] = {"scope": scope_result, **(gate_debate or {})}

    if scope_result["decision"] == "PASS":
        return ConsensusResult(
            status="PASS",
            run_id=rid,
            epack=epack,
            aru=aru,
            output=primary,
            gate=gate,
            timings={"total_s": time.time() - t0, **timings},
        )

    if scope_result["decision"] == "REWRITE":
        try:
            rewritten = await stage_rewrite_once(
                rid=rid,
                epack=epack,
                original_output=primary,
                rewrite_prompt=scope_result["details"]["suggested_rewrite_prompt"],
                config=config,
                verification=verification,
            )
            recheck = scope_gate_v1(output=rewritten, verification=verification, config=scope_cfg, epack=epack, run_id=rid)
            gate["rewrite_attempted"] = True
            gate["scope_after_rewrite"] = recheck
            if recheck["decision"] == "PASS":
                return ConsensusResult(
                    status="PASS",
                    run_id=rid,
                    epack=epack,
                    aru=aru,
                    output=rewritten,
                    gate=gate,
                    timings={"total_s": time.time() - t0, **timings},
                )
        except Exception as e:
            gate["rewrite_error"] = repr(e)

    # REFUSE fallback
    return ConsensusResult(
        status="REFUSE",
        run_id=rid,
        epack=epack,
        aru=aru,
        output=primary,
        gate=gate,
        error="Scope gate refused output",
        timings={"total_s": time.time() - t0, **timings},
    )
