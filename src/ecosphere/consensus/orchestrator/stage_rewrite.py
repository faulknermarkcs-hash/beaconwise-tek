# src/ecosphere/consensus/orchestrator/stage_rewrite.py
from __future__ import annotations

from typing import Any, Dict

from ecosphere.consensus.adapters.factory import build_adapter
from ecosphere.consensus.config import ConsensusConfig
from ecosphere.consensus.ledger.hooks import emit_stage_event
from ecosphere.consensus.schemas import PrimaryOutput, SynthesizerOutput
from ecosphere.consensus.verification.types import VerificationContext


async def stage_rewrite_once(
    *,
    rid: str,
    epack: str,
    original_output: PrimaryOutput | SynthesizerOutput,
    rewrite_prompt: str,
    config: ConsensusConfig,
    verification: VerificationContext,
) -> PrimaryOutput | SynthesizerOutput:
    adapter = build_adapter(config.primary)

    emit_stage_event(
        epack=epack,
        run_id=rid,
        stage="tecl.rewrite.request",
        payload={"role_level": verification.role_level},
    )

    raw_text, meta = await adapter.generate_text(prompt=rewrite_prompt, temperature=0.0, timeout_s=config.primary_timeout_s)

    emit_stage_event(
        epack=epack,
        run_id=rid,
        stage="tecl.rewrite.raw",
        payload={"meta": meta, "raw_preview": raw_text[:200]},
    )

    # Keep rewrite stage simple: return same schema by parsing JSON using adapter helper
    data = adapter.try_parse_json(raw_text)
    if not data:
        raise ValueError("Rewrite did not produce JSON")
    target = type(original_output)
    parsed = target.model_validate(data)
    if parsed.run_id != rid or parsed.epack != epack:
        raise ValueError("Rewritten output run_id/epack mismatch")
    return parsed
