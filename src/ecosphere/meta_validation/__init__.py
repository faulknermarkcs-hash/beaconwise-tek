"""Meta-validation and resilience control plane (V9).

Components:
  - recovery_engine:         Deterministic plan selection
  - damping_stabilizer:      PID-inspired rollout damping
  - circuit_breaker:         Per-plan failure tracking
  - tsi_tracker:             Sliding-window Trust Stability Index
  - post_recovery_verifier:  Closed-loop verification
  - mvi:                     Meta-Validation Index
  - recovery_events:         EPACK audit event emitters
  - policy_compiler:         DSL → runtime compilation
  - resilience_runtime:      Orchestration wiring
"""
