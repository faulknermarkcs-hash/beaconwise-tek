from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, asdict
from typing import Any, Dict

from ecosphere.utils.stable import stable_hash


@dataclass(frozen=True)
class BuildManifest:
    kernel_version: str
    product_name: str
    python: str
    platform: str

    # V5-V6 feature flags
    pr5_4_tokenlen: bool
    pr5_5_structured_revision_render: bool
    pr5_6_workflow_queue: bool
    pr5_7_session_binding: bool
    pr5_8_persistence: bool
    pr5_9_redaction: bool
    pr5_10_tool_sandbox: bool
    pr5_11_manifest: bool

    pr6_stage2_frozen_exemplars: bool
    pr6_schema_retry_loop: bool
    pr6_protected_region_integrity: bool
    pr6_profile_escalation: bool

    # V7 capabilities
    v7_governance_proof_protocol: bool
    v7_universal_adapter_layer: bool
    v7_anti_capture_safeguards: bool
    v7_interop_schema_standard: bool
    v7_adversarial_defense: bool
    v7_governance_constitution: bool
    v7_zero_trust_default: bool
    v7_governance_metrics: bool
    v7_failure_disclosure: bool
    v7_educational_mode: bool

    # V8 capabilities
    v8_challenger_architecture: bool
    v8_three_role_consensus: bool
    v8_fastapi_backend: bool
    v8_replay_engine: bool
    v8_governance_dsl: bool
    v8_grok_adapter: bool
    v8_groq_adapter: bool
    v8_cost_aware_triggers: bool
    v8_arbitration_engine: bool
    v8_enterprise_deployment: bool

    # V9 capabilities
    v9_resilience_policy: bool
    v9_recovery_engine: bool
    v9_damping_stabilizer: bool
    v9_adaptive_tuning: bool

    def seal_hash(self) -> str:
        return stable_hash(asdict(self))


def current_manifest() -> Dict[str, Any]:
    m = BuildManifest(
        kernel_version="v1.9.0",
        product_name="BeaconWise Transparency Ecosphere Kernel (TEK)",
        python=sys.version.split()[0],
        platform=f"{platform.system()}-{platform.release()}",

        # V5-V6
        pr5_4_tokenlen=True,
        pr5_5_structured_revision_render=True,
        pr5_6_workflow_queue=True,
        pr5_7_session_binding=True,
        pr5_8_persistence=True,
        pr5_9_redaction=True,
        pr5_10_tool_sandbox=True,
        pr5_11_manifest=True,
        pr6_stage2_frozen_exemplars=True,
        pr6_schema_retry_loop=True,
        pr6_protected_region_integrity=True,
        pr6_profile_escalation=True,

        # V7
        v7_governance_proof_protocol=True,
        v7_universal_adapter_layer=True,
        v7_anti_capture_safeguards=True,
        v7_interop_schema_standard=True,
        v7_adversarial_defense=True,
        v7_governance_constitution=True,
        v7_zero_trust_default=True,
        v7_governance_metrics=True,
        v7_failure_disclosure=True,
        v7_educational_mode=True,

        # V8
        v8_challenger_architecture=True,
        v8_three_role_consensus=True,
        v8_fastapi_backend=True,
        v8_replay_engine=True,
        v8_governance_dsl=True,
        v8_grok_adapter=True,
        v8_groq_adapter=True,
        v8_cost_aware_triggers=True,
        v8_arbitration_engine=True,
        v8_enterprise_deployment=True,

        # V9
        v9_resilience_policy=True,
        v9_recovery_engine=True,
        v9_damping_stabilizer=True,
        v9_adaptive_tuning=True,
    )
    d = asdict(m)
    d["manifest_hash"] = m.seal_hash()
    return d
