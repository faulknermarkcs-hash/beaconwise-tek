from __future__ import annotations

import asyncio
import time
from typing import Dict, Any

from ecosphere.providers.factory import make_llm_provider
from ecosphere.providers.base import GenerationConfig


# -------------------------
# Parallel Model Execution
# -------------------------

async def _run_model(provider, prompt, cfg):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: provider.generate(prompt, cfg)
    )


async def run_two_stage_consensus(
    user_query: str,
    primary_model: str,
    challenger_model: str,
    arbiter_model: str,
) -> Dict[str, Any]:
    """
    True two-stage deliberation:

    1. Primary + Challenger run independently (parallel)
    2. Arbiter synthesizes final decision
    """

    start = time.time()

    primary_provider = make_llm_provider(primary_model)
    challenger_provider = make_llm_provider(challenger_model)
    arbiter_provider = make_llm_provider(arbiter_model)

    cfg = GenerationConfig(temperature=0.0, max_tokens=900)

    primary_prompt = f"Primary analysis:\n{user_query}"
    challenger_prompt = f"Critique and alternative view:\n{user_query}"

    # -------- Parallel Stage --------
    primary_task = asyncio.create_task(_run_model(primary_provider, primary_prompt, cfg))
    challenger_task = asyncio.create_task(_run_model(challenger_provider, challenger_prompt, cfg))

    primary_result, challenger_result = await asyncio.gather(
        primary_task,
        challenger_task
    )

    # -------- Arbiter Stage --------
    arbiter_prompt = f"""
User query:
{user_query}

Primary answer:
{primary_result.text}

Challenger critique:
{challenger_result.text}

Synthesize final answer with reasoning.
"""

    arbiter_result = await _run_model(arbiter_provider, arbiter_prompt, cfg)

    latency_ms = int((time.time() - start) * 1000)

    return {
        "primary": primary_result.text,
        "challenger": challenger_result.text,
        "final": arbiter_result.text,
        "latency_ms": latency_ms,
    }
