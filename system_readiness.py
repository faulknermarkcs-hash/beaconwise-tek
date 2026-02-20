# system_readiness.py
"""
Regulator-friendly System Readiness Indicator for Streamlit.

Goals:
- Make runtime readiness visible (no hidden background behavior).
- Explain *why* the system is READY / DEGRADED / NOT READY.
- Surface high-signal controls: provider config, keys present, audit persistence, redaction, citations, tools.
- Optional warmup integration (if you add warmup): reads st.session_state["warmup_status"].

Usage:
    from system_readiness import render_system_readiness

    render_system_readiness(
        provider=Settings.PROVIDER,
        model=Settings.MODEL,
        epack_store_path=Settings.EPACK_STORE_PATH,
        persist_epacks=Settings.PERSIST_EPACKS,
        redact_mode=Settings.REDACT_MODE,
        citation_verify=Settings.CITATION_VERIFY,
        require_evidence_citations=Settings.REQUIRE_EVIDENCE_CITATIONS,
        tecl_available=TECL_AVAILABLE,
    )
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import streamlit as st


# -----------------------------
# Types
# -----------------------------
@dataclass(frozen=True)
class ReadinessItem:
    id: str
    label: str
    status: str  # "OK" | "WARN" | "FAIL"
    detail: str


@dataclass(frozen=True)
class ReadinessReport:
    overall: str  # "READY" | "DEGRADED" | "NOT READY"
    summary: str
    items: List[ReadinessItem]
    generated_ts: float


# -----------------------------
# Helpers (checks)
# -----------------------------
def _has_env(*keys: str) -> bool:
    for k in keys:
        v = os.getenv(k, "")
        if isinstance(v, str) and v.strip():
            return True
    return False


def _is_writable_path(path: str) -> Tuple[bool, str]:
    # Lightweight, regulator-friendly "can we persist audit artifacts?"
    try:
        p = (path or "").strip()
        if not p:
            return False, "No EPACK store path set."
        # Attempt an append-only open (does not write data unless you do)
        with open(p, "a", encoding="utf-8"):
            pass
        return True, f"Writable: {p}"
    except Exception as e:
        return False, f"Not writable: {path} ({type(e).__name__})"


def _provider_key_health(provider: str) -> ReadinessItem:
    p = (provider or "mock").lower().strip()

    # You can extend this mapping as your provider adapters expand.
    # We intentionally check *presence only* (not value) to avoid leaking secrets.
    provider_key_map: Dict[str, Tuple[str, ...]] = {
        "openai": ("OPENAI_API_KEY",),
        "groq": ("GROQ_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY",),
        "deepseek": ("DEEPSEEK_API_KEY",),
        # fallback/compat:
        "mock": tuple(),
    }

    if p == "mock":
        return ReadinessItem(
            id="provider_auth",
            label="Provider authentication",
            status="WARN",
            detail="Provider is set to 'mock' (non-production).",
        )

    keys = provider_key_map.get(p, tuple())
    if not keys:
        # Unknown provider: don't fail hard; warn with explicit need.
        return ReadinessItem(
            id="provider_auth",
            label="Provider authentication",
            status="WARN",
            detail=f"Unknown provider '{p}'. Add env key check mapping for it.",
        )

    if _has_env(*keys):
        return ReadinessItem(
            id="provider_auth",
            label="Provider authentication",
            status="OK",
            detail=f"Key present for provider '{p}' (value not displayed).",
        )

    return ReadinessItem(
        id="provider_auth",
        label="Provider authentication",
        status="FAIL",
        detail=f"Missing required env var(s) for '{p}': {', '.join(keys)}",
    )


def _tools_health() -> List[ReadinessItem]:
    """
    TEK tools are allowlisted; here we check whether optional external tools
    are ready without implying they'll be used.
    """
    items: List[ReadinessItem] = []

    # Safe calc is always available (in-kernel sandbox)
    items.append(
        ReadinessItem(
            id="tool_safe_calc",
            label="Tool: safe_calc",
            status="OK",
            detail="Deterministic AST calculator available.",
        )
    )

    # Optional web search tools: keys determine readiness
    brave_ok = _has_env("BRAVE_API_KEY")
    items.append(
        ReadinessItem(
            id="tool_brave",
            label="Tool: Brave Search",
            status="OK" if brave_ok else "WARN",
            detail="BRAVE_API_KEY present." if brave_ok else "BRAVE_API_KEY not set (web_search_brave disabled).",
        )
    )

    serper_ok = _has_env("SERPER_API_KEY")
    items.append(
        ReadinessItem(
            id="tool_serper",
            label="Tool: Serper Search",
            status="OK" if serper_ok else "WARN",
            detail="SERPER_API_KEY present." if serper_ok else "SERPER_API_KEY not set (web_search_serper disabled).",
        )
    )

    return items


def _warmup_health() -> Optional[ReadinessItem]:
    """
    Optional: if you add warmup, store results in st.session_state["warmup_status"] like:
      {
        "overall": "OK|WARN|FAIL",
        "detail": "...",
        "providers": {"openai": {"ok": True, "ms": 123}, ...}
      }
    """
    ws = st.session_state.get("warmup_status")
    if not isinstance(ws, dict):
        return None

    overall = str(ws.get("overall", "WARN")).upper()
    if overall not in ("OK", "WARN", "FAIL"):
        overall = "WARN"

    detail = str(ws.get("detail", "Warmup status recorded."))
    return ReadinessItem(
        id="warmup",
        label="Readiness: network/model warmup",
        status=overall,
        detail=detail,
    )


def build_readiness_report(
    *,
    provider: str,
    model: str,
    epack_store_path: str,
    persist_epacks: bool,
    redact_mode: str,
    citation_verify: bool,
    require_evidence_citations: bool,
    tecl_available: bool,
) -> ReadinessReport:
    items: List[ReadinessItem] = []

    # Provider/model declared
    p = (provider or "").strip()
    m = (model or "").strip()

    if not p:
        items.append(ReadinessItem("provider_declared", "Provider configured", "FAIL", "ECOSPHERE_PROVIDER is empty."))
    elif p.lower() == "mock":
        items.append(ReadinessItem("provider_declared", "Provider configured", "WARN", "Provider is 'mock' (dev mode)."))
    else:
        items.append(ReadinessItem("provider_declared", "Provider configured", "OK", f"Provider: {p}"))

    if not m:
        items.append(ReadinessItem("model_declared", "Model configured", "FAIL", "ECOSPHERE_MODEL is empty."))
    elif "mock" in m.lower():
        items.append(ReadinessItem("model_declared", "Model configured", "WARN", f"Model is '{m}' (dev mode)."))
    else:
        items.append(ReadinessItem("model_declared", "Model configured", "OK", f"Model: {m}"))

    # Provider auth key presence
    items.append(_provider_key_health(p))

    # Audit/persistence readiness
    if persist_epacks:
        ok, detail = _is_writable_path(epack_store_path)
        items.append(
            ReadinessItem(
                id="epack_persist",
                label="Audit artifacts (EPACK) persistence",
                status="OK" if ok else "FAIL",
                detail=detail,
            )
        )
    else:
        items.append(
            ReadinessItem(
                id="epack_persist",
                label="Audit artifacts (EPACK) persistence",
                status="WARN",
                detail="EPACK persistence disabled (ECOSPHERE_PERSIST_EPACKS=0).",
            )
        )

    # Redaction mode (regulator-friendly default is hash)
    rm = (redact_mode or "off").lower().strip()
    if rm in ("hash", "on"):
        items.append(ReadinessItem("redaction", "Redaction", "OK", f"Mode: {rm}"))
    elif rm == "off":
        items.append(ReadinessItem("redaction", "Redaction", "WARN", "Redaction is OFF (not recommended for real data)."))
    else:
        items.append(ReadinessItem("redaction", "Redaction", "WARN", f"Unknown redaction mode '{rm}'."))

    # Citation governance posture
    if require_evidence_citations:
        items.append(ReadinessItem("citations_required", "Evidence citation requirement", "OK", "Evidence citations required."))
    else:
        items.append(ReadinessItem("citations_required", "Evidence citation requirement", "WARN", "Evidence citations not required."))

    items.append(
        ReadinessItem(
            "citation_verify",
            "Citation verification",
            "OK" if citation_verify else "WARN",
            "Verification enabled (tool-backed) where configured." if citation_verify else "Verification disabled (model recall may be unverified).",
        )
    )

    # Tools
    items.extend(_tools_health())

    # TE-CL module presence
    items.append(
        ReadinessItem(
            id="tecl",
            label="Consensus layer (TE-CL)",
            status="OK" if tecl_available else "WARN",
            detail="Consensus module available." if tecl_available else "Consensus module not loaded (demo disabled).",
        )
    )

    # Optional warmup
    warm = _warmup_health()
    if warm:
        items.append(warm)

    # Compute overall
    has_fail = any(i.status == "FAIL" for i in items)
    has_warn = any(i.status == "WARN" for i in items)

    if has_fail:
        overall = "NOT READY"
        summary = "One or more blocking requirements failed. System should not be used for regulated workflows."
    elif has_warn:
        overall = "DEGRADED"
        summary = "System is operational but not fully configured for regulated workflows."
    else:
        overall = "READY"
        summary = "All readiness checks passed. System configuration supports regulated workflows."

    return ReadinessReport(overall=overall, summary=summary, items=items, generated_ts=time.time())


# -----------------------------
# Rendering (Streamlit)
# -----------------------------
_READINESS_CSS = """
<style>
.bw-readiness-bar {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  padding: 10px 12px; border-radius: 14px;
  border: 1px solid rgba(0,0,0,0.10);
  background: rgba(0,0,0,0.02);
}
.bw-pill {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: 999px;
  border: 1px solid rgba(0,0,0,0.12);
  font-size: 12px; line-height: 1;
  background: rgba(255,255,255,0.6);
}
.bw-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.bw-ok { background: #22c55e; }     /* green */
.bw-warn { background: #f59e0b; }   /* amber */
.bw-fail { background: #ef4444; }   /* red */
.bw-title { font-weight: 700; letter-spacing: 0.2px; }
.bw-sub { opacity: 0.8; font-size: 12px; }
</style>
"""

def _dot_class(status: str) -> str:
    if status == "OK":
        return "bw-ok"
    if status == "FAIL":
        return "bw-fail"
    return "bw-warn"


def render_system_readiness(
    *,
    provider: str,
    model: str,
    epack_store_path: str,
    persist_epacks: bool,
    redact_mode: str,
    citation_verify: bool,
    require_evidence_citations: bool,
    tecl_available: bool,
    where: str = "main",  # "main" | "sidebar"
) -> ReadinessReport:
    """
    Renders a regulator-friendly readiness bar and an expandable audit-style details panel.
    Returns the ReadinessReport (useful for logging into EPACK/system events if desired).
    """
    report = build_readiness_report(
        provider=provider,
        model=model,
        epack_store_path=epack_store_path,
        persist_epacks=persist_epacks,
        redact_mode=redact_mode,
        citation_verify=citation_verify,
        require_evidence_citations=require_evidence_citations,
        tecl_available=tecl_available,
    )

    host = st.sidebar if where == "sidebar" else st

    host.markdown(_READINESS_CSS, unsafe_allow_html=True)

    # Overall status pill
    overall_status = "OK" if report.overall == "READY" else ("FAIL" if report.overall == "NOT READY" else "WARN")
    overall_label = f"SYSTEM READINESS: {report.overall}"

    # Key high-signal pills (keep it sparse for regulators)
    # Pick a few items to show inline; everything else goes into the expander.
    def pick(item_id: str) -> Optional[ReadinessItem]:
        for i in report.items:
            if i.id == item_id:
                return i
        return None

    inline = [
        pick("provider_declared"),
        pick("provider_auth"),
        pick("epack_persist"),
        pick("redaction"),
        pick("citation_verify"),
    ]
    inline = [i for i in inline if i is not None]

    pills_html = []
    pills_html.append(
        f"""
        <div class="bw-pill">
          <span class="bw-dot {_dot_class(overall_status)}"></span>
          <span class="bw-title">{overall_label}</span>
        </div>
        """
    )

    for it in inline:
        pills_html.append(
            f"""
            <div class="bw-pill" title="{it.detail}">
              <span class="bw-dot {_dot_class(it.status)}"></span>
              <span>{it.label}</span>
            </div>
            """
        )

    host.markdown(f"""<div class="bw-readiness-bar">{''.join(pills_html)}</div>""", unsafe_allow_html=True)

    with host.expander("System readiness details (audit-style)", expanded=False):
        host.write(report.summary)
        host.caption(time.strftime("Generated: %Y-%m-%d %H:%M:%S", time.localtime(report.generated_ts)))

        # Render as an audit-style list rather than a marketing dashboard
        for it in report.items:
            icon = "✅" if it.status == "OK" else ("⚠️" if it.status == "WARN" else "⛔")
            host.markdown(f"**{icon} {it.label}**  \n{it.detail}")

    return report
