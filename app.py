from __future__ import annotations

import os
import sys
import importlib
import json
import uuid
import asyncio
import time

import streamlit as st
from dotenv import load_dotenv

# ----------------------------
# Force local src/ package
# ----------------------------
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(REPO_ROOT, "src")

# Ensure local src/ wins over any pip-installed "ecosphere"
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# If something already imported a different ecosphere, purge it
if "ecosphere" in sys.modules:
    mod = sys.modules["ecosphere"]
    mod_file = getattr(mod, "__file__", "") or ""
    if SRC_PATH not in mod_file:
        for k in list(sys.modules.keys()):
            if k == "ecosphere" or k.startswith("ecosphere."):
                sys.modules.pop(k, None)
        importlib.invalidate_caches()

# ----------------------------
# Core app imports (now safe)
# ----------------------------
from ecosphere.config import Settings
from ecosphere.kernel.engine import handle_turn
from ecosphere.kernel.session import SessionState
from ecosphere.storage.store import read_jsonl

# ----------------------------
# Optional TE-CL consensus imports
#   (do NOT crash UI if missing)
# ----------------------------
TECL_AVAILABLE = True
TECL_IMPORT_ERROR = ""
try:
    from ecosphere.consensus.orchestrator.flow import run_consensus
    from ecosphere.consensus.config import ConsensusConfig
    from ecosphere.consensus.verification.types import PUBLIC_CONTEXT
    from ecosphere.consensus.verification.verifier_stub import verify_from_file
    from ecosphere.consensus.ledger.reader import get_recent_events
except Exception as e:
    TECL_AVAILABLE = False
    TECL_IMPORT_ERROR = repr(e)

load_dotenv()

st.set_page_config(page_title="BeaconWise v1.9.0", layout="wide")
st.title("BeaconWise Transparency Ecosphere Kernel (TEK) — v9.0")


def _display_text(raw: str) -> str:
    """
    PR6-style: engine may return strict JSON (keys: text, disclosure, citations, assumptions).
    In the UI, render the main text and (if provided) a human-readable Evidence References list.
    """
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and "text" in obj:
            out = str(obj["text"])
            cites = obj.get("citations")
            if isinstance(cites, list) and cites:
                lines = ["", "Evidence References:"]
                for c in cites[:10]:
                    if not isinstance(c, dict):
                        continue
                    authors = (c.get("authors_or_org") or "").strip()
                    year = c.get("year")
                    year_s = str(year) if year is not None else "unknown"
                    title = (c.get("title") or "").strip()
                    src_type = (c.get("source_type") or "").strip()
                    ver = (c.get("verification_status") or "").strip()
                    parts = [p for p in [authors, year_s] if p]
                    head = ", ".join(parts) if parts else "(unknown)"
                    tail = " — ".join([p for p in [title, src_type, ver] if p])
                    lines.append(f"- {head}: {tail}")
            if isinstance(cites, list) and cites:
                out += "\n".join(lines)
            return out
    except Exception:
        pass
    return raw


# --- Session init ---
if "sess" not in st.session_state:
    st.session_state.sess = SessionState(session_id=f"sess_{uuid.uuid4().hex[:10]}")
if "chat" not in st.session_state:
    st.session_state.chat = []
if "restored" not in st.session_state:
    st.session_state.restored = False

sess: SessionState = st.session_state.sess

# Optional: show restored EPACKs if persistence enabled
if not st.session_state.restored and Settings.PERSIST_EPACKS:
    restored = read_jsonl(Settings.EPACK_STORE_PATH, limit=200)
    if restored:
        with st.sidebar:
            st.subheader("Restored EPACKs (redacted)")
            st.write(f"Loaded {len(restored)} records from {Settings.EPACK_STORE_PATH}")
            with st.expander("Show last restored"):
                st.json(restored[-1])
    st.session_state.restored = True

# --- Sidebar ---
with st.sidebar:
    st.subheader("Runtime")
    st.write("Provider:", os.getenv("ECOSPHERE_PROVIDER", "mock"))
    st.write("Model:", os.getenv("ECOSPHERE_MODEL", "mock-llm"))
    st.write("Embeddings:", os.getenv("ECOSPHERE_EMBEDDINGS", "local"))
    st.write("Embeddings model:", os.getenv("ECOSPHERE_EMBEDDINGS_MODEL", "local-mini"))
    st.write("Profile:", sess.current_profile)
    st.write("Pending gate:", sess.pending_gate.gate)
    st.write("Token:", sess.pending_gate.confirm_token)
    st.write("EPACK store:", Settings.EPACK_STORE_PATH)
    st.write("Redaction mode:", Settings.REDACT_MODE)

    st.divider()
    st.subheader("TE-CL Demo (Credential Tiering)")

    if not TECL_AVAILABLE:
        st.warning("TE-CL demo disabled (consensus module import failed).")
        with st.expander("Import error"):
            st.code(TECL_IMPORT_ERROR)
        use_tecl = False
    else:
        use_tecl = st.checkbox(
            "Enable TE-CL demo",
            value=False,
            help="Runs the Consensus Layer with credential-aware tiering (dev-only).",
        )

    if TECL_AVAILABLE and use_tecl:
        if "tecl_epack_id" not in st.session_state:
            st.session_state["tecl_epack_id"] = f"tecl-{uuid.uuid4().hex[:12]}"
        if "tecl_run_id" not in st.session_state:
            st.session_state["tecl_run_id"] = f"run-{uuid.uuid4().hex[:12]}"

        epack_id = st.text_input("EPACK ID", value=st.session_state.get("tecl_epack_id"))
        st.session_state["tecl_epack_id"] = epack_id.strip() or st.session_state["tecl_epack_id"]
        run_id = st.text_input("Run ID", value=st.session_state.get("tecl_run_id"))
        st.session_state["tecl_run_id"] = run_id.strip() or st.session_state["tecl_run_id"]
        user_id = st.text_input(
            "Mock User ID",
            value=st.session_state.get("tecl_user_id", "public@example.com"),
            help="Lookup key in mock_credentials.json (dev-only).",
        )
        st.session_state["tecl_user_id"] = user_id
        cred_file = st.text_input("Credential file", value=st.session_state.get("tecl_cred_file", "mock_credentials.json"))
        st.session_state["tecl_cred_file"] = cred_file

        verification = PUBLIC_CONTEXT
        if user_id.strip():
            verification = verify_from_file(
                user_id=user_id.strip(),
                credential_file=cred_file.strip() or "mock_credentials.json",
                epack=st.session_state["tecl_epack_id"],
                run_id=st.session_state["tecl_run_id"],
            )

        if verification == PUBLIC_CONTEXT:
            st.info("Tier: Public / unverified")
        else:
            st.success(f"Tier: {verification.role} (level {verification.role_level})")
            if verification.scope:
                st.caption(f"Scope: {verification.scope}")
            if verification.expires_ts:
                st.caption(f"Expires: {time.strftime('%Y-%m-%d', time.localtime(verification.expires_ts))}")

        tecl_query = st.text_area(
            "TE-CL Query",
            value=st.session_state.get("tecl_query", "What are statin side effects?"),
            height=90,
        )
        st.session_state["tecl_query"] = tecl_query

        if st.button("Run TE-CL"):
            cfg = ConsensusConfig.preset_for_verification_default(verification)
            result = asyncio.run(
                run_consensus(
                    user_query=tecl_query,
                    aru="ANSWER",
                    high_stakes=(getattr(verification, "role_level", 0) >= 2),
                    epack=st.session_state["tecl_epack_id"],
                    config=cfg,
                    verification=verification,
                    run_id=st.session_state["tecl_run_id"],
                )
            )
            st.session_state["tecl_last_result"] = {
                "status": result.status,
                "answer": getattr(result.output, "answer", None) if result.output else None,
                "gate": result.gate,
            }

        last = st.session_state.get("tecl_last_result")
        if last:
            st.write("**Last TE-CL Result**:", last.get("status"))
            if last.get("answer"):
                st.write(last["answer"])
            with st.expander("Gate details"):
                st.json(last.get("gate", {}))

        with st.expander("Recent Verification Events (EPACK)"):
            events = get_recent_events(epack_id, stage_prefix="tecl.verification.", limit=10)
            if not events:
                st.caption("No verification events yet.")
            for evt in events:
                ts = evt.get("ts_ms", 0) / 1000.0
                st.markdown(f"**{evt.get('stage','')}** @ {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))}")
                st.json(evt.get("payload", {}))
                h = evt.get("event_hash", "")
                if h:
                    st.caption(f"hash: {h[:12]}…")
                st.markdown("---")

    if st.button("Reset Session"):
        st.session_state.sess = SessionState(session_id=f"sess_{uuid.uuid4().hex[:10]}")
        st.session_state.chat = []
        st.session_state.restored = False
        st.rerun()

st.divider()

# --- Render chat history ---
for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.write(m["content"])
        if m.get("epack"):
            with st.expander("EPACK (last)"):
                st.json(m["epack"])

# --- Input / turn execution ---
user_text = st.chat_input("Type a message... (try `calc: (2+2)*10`)")
if user_text:
    st.session_state.chat.append({"role": "user", "content": user_text})

    out = handle_turn(sess, user_text)

    st.session_state.chat.append(
        {
            "role": "assistant",
            "content": _display_text(out["assistant_text"]),
            "epack": out.get("epack"),
        }
    )
    st.rerun()
