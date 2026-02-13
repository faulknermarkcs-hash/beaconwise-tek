# Repository File Tree

Generated from beaconwise v1.9.0 (final release).

```
beaconwise-v1.9.0/
├── .github
│   └── workflows
│       └── ci.yml
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── Makefile
├── NOTICE
├── PATCH_NOTES.md
├── PATCH_NOTES_RELEASE_HYGIENE.md
├── README.md
├── SECURITY.md
├── SMOKE_TEST.md
├── TEST_RESULTS_TEMPLATE.md
├── TEST_SUITE_OVERVIEW.md
├── api
│   ├── main.py
│   └── resilience.py
├── app.py
├── docker
│   └── Dockerfile
├── docs
│   ├── ADOPTION_GUIDE.md
│   ├── ARCHITECTURE.md
│   ├── COMPLIANCE_MAPPING.md
│   ├── CONFORMANCE_REPORT.md
│   ├── CONSTITUTION
│   ├── CONSTITUTION.md
│   ├── EVIDENCE_LIFECYCLE.md
│   ├── FAQ.md
│   ├── FILETREE.md
│   ├── GOVERNANCE_USE_CASES.md
│   ├── INDEX.md
│   ├── PUBLIC_TRANSPARENCY_GUIDE.md
│   ├── REGULATOR_BRIEFING.md
│   ├── REGULATOR_LINT_REPORT.md
│   ├── REPLAY_PROTOCOL.md
│   ├── SCHEMA_SPECIFICATION.md
│   ├── SECURITY_MODEL.md
│   ├── THREAT_MODEL.md
│   ├── VALIDATOR_GOVERNANCE.md
│   └── architecture.svg
├── enterprise
│   ├── PILOT_PACKAGE
│   └── PILOT_PACKAGE.md
├── examples
│   ├── minimal_demo.py
│   └── run_demo.py
├── governance_schema.json
├── mock_credentials.json.sample
├── policies
│   ├── default.yaml
│   ├── enterprise_v9.yaml
│   └── healthcare.yaml
├── preprint
│   ├── README.md
│   ├── beaconwise_preprint_v1.9.0.docx
│   ├── beaconwise_preprint_v1.9.0.pdf
│   ├── docx_generator.js
│   └── pdf_generator.py
├── pyproject.toml
├── render.yaml
├── requirements.txt
├── runtime.txt
├── src
│   └── ecosphere
│       ├── __init__.py
│       ├── challenger
│       │   ├── __init__.py
│       │   ├── config.py
│       │   └── engine.py
│       ├── config.py
│       ├── consensus
│       │   ├── __init__.py
│       │   ├── adapters
│       │   │   ├── __init__.py
│       │   │   ├── anthropic_adapter.py
│       │   │   ├── base.py
│       │   │   ├── factory.py
│       │   │   ├── grok_adapter.py
│       │   │   ├── groq_adapter.py
│       │   │   ├── mock_adapter.py
│       │   │   ├── openai_adapter.py
│       │   │   ├── retrieval_adapter.py
│       │   │   └── symbolic_adapter.py
│       │   ├── config.py
│       │   ├── gates
│       │   │   ├── __init__.py
│       │   │   └── scope_gate.py
│       │   ├── ledger
│       │   │   ├── __init__.py
│       │   │   ├── hooks.py
│       │   │   └── reader.py
│       │   ├── orchestrator
│       │   │   ├── __init__.py
│       │   │   ├── flow.py
│       │   │   └── stage_rewrite.py
│       │   ├── policy_loader.py
│       │   ├── schemas.py
│       │   └── verification
│       │       ├── __init__.py
│       │       ├── types.py
│       │       └── verifier_stub.py
│       ├── embeddings
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── factory.py
│       │   └── local.py
│       ├── epack
│       │   ├── __init__.py
│       │   ├── chain.py
│       │   └── postgres_store.py
│       ├── governance
│       │   ├── __init__.py
│       │   ├── adversarial.py
│       │   ├── constitution.py
│       │   ├── dsl_loader.py
│       │   ├── failure.py
│       │   ├── metrics.py
│       │   ├── proof.py
│       │   └── schema.py
│       ├── kernel
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── gates.py
│       │   ├── provenance.py
│       │   ├── revisions.py
│       │   ├── router.py
│       │   ├── session.py
│       │   ├── session_secret.py
│       │   ├── tools.py
│       │   └── types.py
│       ├── meta_validation
│       │   ├── __init__.py
│       │   ├── circuit_breaker.py
│       │   ├── damping_stabilizer.py
│       │   ├── mvi.py
│       │   ├── policy_compiler.py
│       │   ├── post_recovery_verifier.py
│       │   ├── recovery_engine.py
│       │   ├── recovery_events.py
│       │   ├── resilience_runtime.py
│       │   └── tsi_tracker.py
│       ├── providers
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── factory.py
│       │   └── mock.py
│       ├── replay
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   └── package.py
│       ├── safety
│       │   ├── __init__.py
│       │   ├── embedding_stage2.py
│       │   └── stage1.py
│       ├── security
│       │   ├── __init__.py
│       │   └── redaction.py
│       ├── storage
│       │   ├── __init__.py
│       │   └── store.py
│       ├── tools
│       │   ├── __init__.py
│       │   ├── brave.py
│       │   ├── citations.py
│       │   └── serper.py
│       ├── tsv
│       │   ├── __init__.py
│       │   └── state.py
│       ├── utils
│       │   ├── __init__.py
│       │   └── stable.py
│       └── validation
│           ├── __init__.py
│           └── validators.py
├── testdata
│   ├── drift_epack_chain.jsonl
│   ├── golden_epack_chain.jsonl
│   └── tampered_epack_chain.jsonl
└── tests
    ├── conftest
    ├── conftest.py
    ├── test_consensus_config.py
    ├── test_consensus_orchestrator.py
    ├── test_engine.py
    ├── test_epack_chain_integrity.py
    ├── test_epack_reader.py
    ├── test_epack_reader_hooks.py
    ├── test_epack_reader_integration.py
    ├── test_gates_full.py
    ├── test_hash_agility.py
    ├── test_integration_scenario.py
    ├── test_kernel_replay_roundtrip.py
    ├── test_pr510_tool_sandbox.py
    ├── test_pr54_token_length.py
    ├── test_pr6_hardening.py
    ├── test_profile_escalation.py
    ├── test_recovery_lifecycle.py
    ├── test_redaction_epack_provenance.py
    ├── test_replay_engine.py
    ├── test_replay_package.py
    ├── test_router.py
    ├── test_safe_calc_hardened.py
    ├── test_scope_gate.py
    ├── test_tsv_state.py
    ├── test_v7_governance.py
    ├── test_v8_challenger.py
    ├── test_v9_circuit_breaker.py
    ├── test_v9_policy_loader.py
    ├── test_v9_post_recovery.py
    ├── test_v9_recovery_events.py
    ├── test_v9_resilience.py
    ├── test_v9_resilience_recovery_engine.py
    ├── test_v9_runtime_integration.py
    ├── test_v9_tsi_tracker.py
    └── test_verifier_stub.py
```
