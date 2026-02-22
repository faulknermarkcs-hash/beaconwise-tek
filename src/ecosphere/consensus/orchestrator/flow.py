# src/ecosphere/consensus/orchestrator/flow.py
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from pydantic import ValidationError

from ecosphere.consensus.adapters.factory import build_adapter
from ecosphere.consensus.config import ConsensusConfig, ARU, ModelSpec, DebateConfig, DEFAULT_PROMPTS
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

    # Repair loop
    last_text = raw_text
    for attempt in range(1, max_attempts + 1):
        repaired = await stage_rewrite_once(
            adapter=adapter,
            prompt=_render_prompt(
                repair_template,
                {
                    "RUN_ID": rid,
                    "EPACK": epack,
                    "ARU": aru,
                    "BAD_OUTPUT": last_text,
                },
            ),
            temperature=0.0,
            timeout_s=30,
        )
        last_text = repaired.text
        data = adapter.try_parse_json(last_text)
        if data is not None:
            try:
                return target_model.model_validate(data)
            except ValidationError:
                continue

    raise ValidationError.from_exception_data("parse_failed", [])


async def _generate_primary(
    *,
    rid: str,
    epack: str,
    aru: str,
    adapter,
    prompt: str,
    temperature: float,
    timeout_s: int,
    repair_template: str,
    max_repair_attempts: int,
) -> tuple[PrimaryOutput, str, Dict[str, Any]]:
    raw_text, meta = await adapter.generate_text(
        prompt=prompt,
        temperature=temperature,
        timeout_s=timeout_s,
    )
    parsed = await _parse_with_repair(
        rid=rid,
        epack=epack,
        adapter=adapter,
        target_model=PrimaryOutput,
        raw_text=raw_text,
        repair_template=repair_template,
        max_attempts=max_repair_attempts,
        aru=aru,
    )
    return parsed, raw_text, meta


async def _generate_synth(
    *,
    rid: str,
    epack: str,
    aru: str,
    adapter,
    prompt: str,
    timeout_s: int,
    repair_template: str,
    max_repair_attempts: int,
) -> tuple[SynthesizerOutput, str, Dict[str, Any]]:
    raw_text, meta = await adapter.generate_text(
        prompt=prompt,
        temperature=0.0,
        timeout_s=timeout_s,
    )
    parsed = await _parse_with_repair(
        rid=rid,
        epack=epack,
        adapter=adapter,
        target_model=SynthesizerOutput,
        raw_text=raw_text,
        repair_template=repair_template,
        max_attempts=max_repair_attempts,
        aru=aru,
    )
    return parsed, raw_text, meta


def run_consensus(
    *,
    user_query: str,
    aru: str = ARU.ANSWER.value,
    high_stakes: bool = False,
    epack: str,
    config: ConsensusConfig,
    verification: Optional[VerificationContext] = None,
    run_id: Optional[str] = None,
) -> ConsensusResult:
    """Run TEK consensus.

    Brick 6.1+ behavior:
      - If config.enable_debate and config.debate are set:
          Primary (defender) + Challenger (critic) run in parallel, then Arbiter (synthesizer)
      - Else:
          Single-stage primary run

    Returns a ConsensusResult with PrimaryOutput or SynthesizerOutput.
    """
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
            "enable_debate": bool(config.enable_debate and config.debate),
        },
    )

    # ----------------------------
    # Debate (Primary/Challenger/Arbiter)
    # ----------------------------
    if config.enable_debate and config.debate is not None:
        debate = config.debate

        defender_adapter = build_adapter(debate.defender_model)
        critic_adapter = build_adapter(debate.critic_model)
        synth_adapter = build_adapter(debate.synthesizer_model)

        # Independent prompts (no cross-contamination)
        defender_prompt = _render_prompt(
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

        critic_prompt = _render_prompt(
            config.prompts.primary_template,
            {
                "RUN_ID": rid,
                "EPACK": epack,
                "ARU": aru,
                "USER_QUERY": (
                    "You are the Challenger. Produce an independent answer, then list weaknesses/risks "
                    "in typical answers and propose safer alternatives.\n\nUSER_QUERY:\n" + user_query
                ),
                "VERIFIED": str(verification.verified).lower(),
                "ROLE": verification.role,
                "ROLE_LEVEL": str(verification.role_level),
                "SCOPE": verification.scope or "none",
            },
        )

        async def _run_debate() -> ConsensusResult:
            t1 = time.time()
            # Parallel primary/challenger
            defender_task = asyncio.create_task(
                _generate_primary(
                    rid=rid,
                    epack=epack,
                    aru=aru,
                    adapter=defender_adapter,
                    prompt=defender_prompt,
                    temperature=config.primary_temperature,
                    timeout_s=config.primary_timeout_s,
                    repair_template=config.prompts.repair_template,
                    max_repair_attempts=config.max_repair_attempts,
                )
            )
            critic_task = asyncio.create_task(
                _generate_primary(
                    rid=rid,
                    epack=epack,
                    aru=aru,
                    adapter=critic_adapter,
                    prompt=critic_prompt,
                    temperature=0.0,
                    timeout_s=debate.critic_model.timeout_s or config.primary_timeout_s,
                    repair_template=config.prompts.repair_template,
                    max_repair_attempts=config.max_repair_attempts,
                )
            )

            try:
                defender_parsed, defender_raw, defender_meta, = await defender_task
                critic_parsed, critic_raw, critic_meta, = await critic_task
            except Exception as e:
                return ConsensusResult(
                    status="FAIL",
                    run_id=rid,
                    epack=epack,
                    aru=aru,
                    error=f"debate_generation_failed: {type(e).__name__}: {e}",
                    timings={"total_ms": (time.time() - t0) * 1000.0},
                )

            timings["primary_parallel_ms"] = (time.time() - t1) * 1000.0

            # Arbiter synthesis
            t2 = time.time()
            synth_prompt = (
                "You are the Arbiter. You MUST output valid JSON matching SynthesizerOutput.\n"
                "Choose the best answer given safety, policy, and evidence quality.\n\n"
                f"RUN_ID: {rid}\nEPACK: {epack}\nARU: {aru}\n\n"
                f"USER_QUERY:\n{user_query}\n\n"
                f"PRIMARY (Defender) JSON:\n{defender_raw}\n\n"
                f"CHALLENGER (Critic) JSON:\n{critic_raw}\n\n"
                "Synthesize a final answer. Keep reasoning_trace concise and policy-aware."
            )

            try:
                synth_parsed, synth_raw, synth_meta = await _generate_synth(
                    rid=rid,
                    epack=epack,
                    aru=aru,
                    adapter=synth_adapter,
                    prompt=synth_prompt,
                    timeout_s=debate.synthesizer_model.timeout_s or config.primary_timeout_s,
                    repair_template=config.prompts.repair_template,
                    max_repair_attempts=config.max_repair_attempts,
                )
            except Exception as e:
                return ConsensusResult(
                    status="FAIL",
                    run_id=rid,
                    epack=epack,
                    aru=aru,
                    error=f"synth_parse_failed: {type(e).__name__}: {e}",
                    timings={"total_ms": (time.time() - t0) * 1000.0},
                    debate_outputs={
                        "defender_raw": defender_raw,
                        "critic_raw": critic_raw,
                    },
                )

            timings["arbiter_ms"] = (time.time() - t2) * 1000.0

            # Scope gate on final answer
            gate_cfg = ScopeGateConfig(high_stakes=high_stakes)
            gate = scope_gate_v1(
                answer_text=synth_parsed.answer,
                config=gate_cfg,
            )
            if not gate.get("ok", True):
                return ConsensusResult(
                    status="GATED",
                    run_id=rid,
                    epack=epack,
                    aru=aru,
                    output=synth_parsed,
                    gate=gate,
                    timings={"total_ms": (time.time() - t0) * 1000.0, **timings},
                    debate_outputs={
                        "defender": defender_parsed.model_dump(),
                        "critic": critic_parsed.model_dump(),
                        "arbiter_raw": synth_raw,
                        "defender_meta": defender_meta,
                        "critic_meta": critic_meta,
                        "arbiter_meta": synth_meta,
                    },
                )

            return ConsensusResult(
                status="PASS",
                run_id=rid,
                epack=epack,
                aru=aru,
                output=synth_parsed,
                timings={"total_ms": (time.time() - t0) * 1000.0, **timings},
                debate_outputs={
                    "defender": defender_parsed.model_dump(),
                    "critic": critic_parsed.model_dump(),
                    "arbiter_raw": synth_raw,
                    "defender_meta": defender_meta,
                    "critic_meta": critic_meta,
                    "arbiter_meta": synth_meta,
                },
            )

        result = asyncio.run(_run_debate())

        emit_stage_event(
            epack=epack,
            run_id=rid,
            stage="tecl.end",
            payload={
                "status": result.status,
                "timings": result.timings or {},
                "debate": True,
            },
        )
        return result

    # ----------------------------
    # Single-stage primary (legacy)
    # ----------------------------
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

    async def _run_primary() -> ConsensusResult:
        t1 = time.time()
        raw_text, meta = await adapter.generate_text(
            prompt=prompt,
            temperature=config.primary_temperature,
            timeout_s=config.primary_timeout_s,
        )
        timings["primary_ms"] = (time.time() - t1) * 1000.0

        try:
            parsed = await _parse_with_repair(
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
                status="FAIL",
                run_id=rid,
                epack=epack,
                aru=aru,
                error=f"primary_parse_failed: {type(e).__name__}: {e}",
                timings={"total_ms": (time.time() - t0) * 1000.0, **timings},
            )

        # Scope gate
        gate_cfg = ScopeGateConfig(high_stakes=high_stakes)
        gate = scope_gate_v1(answer_text=parsed.answer, config=gate_cfg)
        if not gate.get("ok", True):
            return ConsensusResult(
                status="GATED",
                run_id=rid,
                epack=epack,
                aru=aru,
                output=parsed,
                gate=gate,
                timings={"total_ms": (time.time() - t0) * 1000.0, **timings},
            )

        return ConsensusResult(
            status="PASS",
            run_id=rid,
            epack=epack,
            aru=aru,
            output=parsed,
            timings={"total_ms": (time.time() - t0) * 1000.0, **timings},
        )

    result = asyncio.run(_run_primary())

    emit_stage_event(
        epack=epack,
        run_id=rid,
        stage="tecl.end",
        payload={
            "status": result.status,
            "timings": result.timings or {},
            "debate": False,
        },
    )
    return result


# ---------------------------------------------------------------------------
# run_two_stage_consensus — convenience wrapper for api/main.py
# ---------------------------------------------------------------------------

def _model_str_to_spec(model_str: str, timeout_s: int = 90) -> ModelSpec:
    """
    Parse a model identifier into a ModelSpec.

    Accepts two formats:
      - "provider:model-name"   e.g. "openai:gpt-4o"
      - "model-name"            e.g. "gpt-4o" (provider auto-detected)
    """
    if ":" in model_str:
        provider, model = model_str.split(":", 1)
        return ModelSpec(provider=provider.strip(), model=model.strip(), timeout_s=timeout_s)

    m = model_str.lower()
    if "claude" in m:
        provider = "anthropic"
    elif "gpt" in m or m.startswith("o1") or m.startswith("o3") or m.startswith("o4"):
        provider = "openai"
    elif "llama" in m or "mixtral" in m or "gemma" in m or "qwen" in m:
        provider = "groq"
    elif "deepseek" in m:
        provider = "deepseek"
    elif "gemini" in m:
        provider = "google"
    else:
        provider = "openai"

    return ModelSpec(provider=provider, model=model_str, timeout_s=timeout_s)


def run_two_stage_consensus(
    user_text: str,
    *,
    primary_model: str = "gpt-4o",
    challenger_model: str = "claude-sonnet-4-20250514",
    arbiter_model: str = "llama-3.3-70b-versatile",
    epack: Optional[str] = None,
    run_id: Optional[str] = None,
    high_stakes: bool = False,
) -> dict:
    """
    Parallel 3-stage debate pipeline, callable from api/main.py.

    Stage 1 — Primary + Challenger run in parallel (asyncio)
    Stage 2 — Arbiter synthesises with full context

    Model strings accept 'provider:model' or bare model names (provider
    is auto-detected from common prefixes).

    Returns a plain dict with keys:
        final, answer, status, run_id, epack, timings, debate_outputs, error, gate
    """
    import uuid as _uuid

    rid = run_id or _uuid.uuid4().hex
    ep  = epack  or _uuid.uuid4().hex[:16]

    primary_spec    = _model_str_to_spec(primary_model,    timeout_s=90)
    challenger_spec = _model_str_to_spec(challenger_model, timeout_s=90)
    arbiter_spec    = _model_str_to_spec(arbiter_model,    timeout_s=90)

    debate = DebateConfig(
        defender_model=primary_spec,
        critic_model=challenger_spec,
        synthesizer_model=arbiter_spec,
    )

    config = ConsensusConfig(
        profile_name="TWO_STAGE",
        primary=primary_spec,
        prompts=DEFAULT_PROMPTS,
        primary_temperature=0.0,
        primary_timeout_s=90,
        max_repair_attempts=1,
        enable_debate=True,
        debate=debate,
    )

    result = run_consensus(
        user_query=user_text,
        epack=ep,
        config=config,
        run_id=rid,
        high_stakes=high_stakes,
    )

    # Extract a human-readable final answer
    final_answer: Optional[str] = None
    if result.output is not None:
        if hasattr(result.output, "answer"):
            final_answer = result.output.answer
        else:
            try:
                dumped = result.output.model_dump()
                final_answer = (
                    dumped.get("answer")
                    or dumped.get("synthesis")
                    or str(dumped)
                )
            except Exception:
                final_answer = str(result.output)

    return {
        "final":         final_answer,
        "answer":        final_answer,
        "status":        result.status,
        "run_id":        result.run_id,
        "epack":         result.epack,
        "timings":       result.timings,
        "debate_outputs": result.debate_outputs,
        "error":         result.error,
        "gate":          result.gate,
    }

