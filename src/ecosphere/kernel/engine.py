# --- PATCHED ENGINE: Brick 3/4/5 EPACK integration ---

def _execute_v9_runtime(sess: SessionState, user_text: str, iv: InputVector) -> Tuple[str, Dict[str, Any]]:
    """
    V9 consensus execution WITH EPACK sealing.
    This was missing → caused 0-block replay failure.
    """

    from ecosphere.consensus.policy_loader import consensus_config_from_policy
    from ecosphere.consensus.orchestrator.flow import run_consensus
    from ecosphere.governance.dsl_loader import load_policy

    rt = _v9_runtime()

    policy_path = os.getenv("BW_POLICY_PATH") or "policies/enterprise_v9.yaml"
    if not os.path.exists(policy_path):
        policy_path = "policies/default.yaml"

    policy = load_policy(policy_path)
    consensus_config = consensus_config_from_policy(policy)

    import uuid
    run_id = uuid.uuid4().hex
    epack_id = f"v9-{run_id[:12]}"

    result = asyncio.run(
        run_consensus(
            user_query=user_text,
            epack=epack_id,
            config=consensus_config,
            run_id=run_id,
        )
    )

    status = getattr(result, "status", "UNKNOWN")

    rt.record_outcome(
        status=status,
        validator_agreement=0.5,
        latency_ms=int((getattr(result, "timings", {}) or {}).get("total_ms", 0)),
        challenger_fired=False,
    )

    signal = rt.current_signal()

    snapshot = TrustSnapshot(
        tsi_current=signal.tsi_current,
        tsi_forecast_15m=signal.tsi_forecast_15m,
        der_density=0.0,
        dep_concentration_index=0.0,
        degraded=(status != "PASS"),
    )

    decision = rt.maybe_recover(snapshot)

    output = getattr(result, "output", None)
    if output and hasattr(output, "answer"):
        assistant_text = output.answer
    elif output:
        assistant_text = str(output)
    else:
        assistant_text = getattr(result, "text", str(result))

    # -------------------------------------------------
    # 🔥 CRITICAL: EPACK COMMITMENT (Brick 3/4/5)
    # -------------------------------------------------

    payload = {
        "consensus_status": status,
        "policy_id": policy.get("policy_id"),
        "policy_version": policy.get("policy_version"),
        "tsi_current": signal.tsi_current,
        "tsi_forecast": signal.tsi_forecast_15m,
        "recovery": decision.to_dict() if decision else None,
    }

    from ecosphere.decision.object import build_decision_object

    decision_obj, decision_hash = build_decision_object(
        session_id=sess.session_id,
        profile=sess.current_profile,
        payload=payload,
        assistant_text=assistant_text,
        build_manifest=current_manifest(),
    )

    payload["decision_hash"] = decision_hash
    payload["decision_object"] = decision_obj

    ep = new_epack(
        sess.epack_seq + 1,
        sess.epack_prev_hash,
        payload,
        payload_hash_override=decision_hash,
    )

    sess.epack_seq = ep.seq
    sess.epack_prev_hash = ep.hash

    sess.epacks.append(
        {
            "seq": ep.seq,
            "ts": ep.ts,
            "prev_hash": ep.prev_hash,
            "payload_hash": ep.payload_hash,
            "hash": ep.hash,
            "payload": ep.payload,
        }
    )

    # -------------------------------------------------

    meta = {
        "v9": True,
        "consensus_status": status,
        "tsi": signal.tsi_current,
    }

    return assistant_text, meta
