from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import streamlit as st


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


def _has_env(*keys: str) -> bool:
    for k in keys:
        v = os.getenv(k, "")
        if isinstance(v, str) and v.strip():
            return True
    return False


def _is_writable_path(path: str) -> Tuple[bool, str]:
    try:
        p = (path or "").strip()
        if not p:
            return False, "No EPACK store path set."
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "a", encoding="utf-8"):
            pass
        return True, f"Writable: {p}"
    except Exception as e:
        return False, f"Not writable: {path} ({type(e).__name__})"


def _provider_key_health(provider: str) -> ReadinessItem:
    p = (provider or "mock").lower().strip()
    provider_key_map: Dict[str, Tuple[str, ...]] = {
        "openai": ("OPENAI_API_KEY",),
        "groq": ("GROQ_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY",),
        "deepseek": ("DEEPSEEK_API_KEY",),
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
    items: List[ReadinessItem] = []

    items.append(
        ReadinessItem(
            id="tool_safe_calc",
            label="Tool: safe_calc",
            status="OK",
            detail="Deterministic AST calculator available.",
        )
    )

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

    items.append(_provider_key_health(p))

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

    rm = (redact_mode or "off").lower().strip()
    if rm in ("hash", "on"):
        items.append(ReadinessItem("redaction", "Redaction", "OK", f"Mode: {rm}"))
    elif rm == "off":
        items.append(ReadinessItem("redaction", "Redaction", "WARN", "Redaction is OFF (not recommended for real data)."))
    else:
        items.append(ReadinessItem("redaction", "Redaction", "WARN", f"Unknown redaction mode '{rm}'."))

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

    items.extend(_tools_health())

    items.append(
        ReadinessItem(
            id="tecl",
            label="Consensus layer (TE-CL)",
            status="OK" if tecl_available else "WARN",
            detail="Consensus module available." if tecl_available else "Consensus module not loaded (demo disabled).",
        )
    )

    warm = _warmup_health()
    if warm:
        items.append(warm)

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


_READINESS_CSS = """
<style>
/* context bar (sticky, thin) */
.bw-contextbar {
  position: sticky;
  top: 0;
  z-index: 999;
  padding: 6px 10px;
  margin: -0.75rem 0 0.75rem 0;
  border-radius: 12px;
  border: 1px solid rgba(0,0,0,0.10);
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(6px);
}
.bw-contextrow { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
.bw-left { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.bw-right { display:flex; align-items:center; gap:8px; flex-wrap:wrap; opacity: 0.9;}
.bw-tag {
  display:inline-flex; align-items:center; gap:6px;
  padding: 3px 8px; border-radius: 999px;
  border: 1px solid rgba(0,0,0,0.10);
  font-size: 12px; line-height: 1;
  background: rgba(0,0,0,0.02);
}
.bw-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
.bw-ok { background:#22c55e; }     /* green */
.bw-warn { background:#f59e0b; }   /* amber */
.bw-fail { background:#ef4444; }   /* red */
.bw-title { font-weight: 700; letter-spacing: 0.2px; font-size: 12px; }
.bw-mini { font-size: 12px; opacity: 0.9; }
.bw-linklike { font-size: 12px; text-decoration: underline; cursor: pointer; }
</style>
"""

def _dot_class(status: str) -> str:
    if status == "OK":
        return "bw-ok"
    if status == "FAIL":
        return "bw-fail"
    return "bw-warn"


def _overall_to_status(overall: str) -> str:
    if overall == "READY":
        return "OK"
    if overall == "NOT READY":
        return "FAIL"
    return "WARN"


def _get_item(report: ReadinessReport, item_id: str) -> Optional[ReadinessItem]:
    for it in report.items:
        if it.id == item_id:
            return it
    return None


def render_governance_context_bar(
    report: ReadinessReport,
    *,
    session_id: str,
    profile: str,
    pending_gate: str,
    audit_on: bool,
    human_finalize_on: bool,
    where: str = "main",
) -> None:
    """
    Thin, always-on header strip. Uses the same readiness report.
    Mirrors the 'governance state obvious at all times' goal.
    """
    host = st.sidebar if where == "sidebar" else st
    host.markdown(_READINESS_CSS, unsafe_allow_html=True)

    status = _overall_to_status(report.overall)

    provider = _get_item(report, "provider_declared")
    model = _get_item(report, "model_declared")
    redaction = _get_item(report, "redaction")
    epack = _get_item(report, "epack_persist")

    def tag(label: str, status_s: str) -> str:
        return f'<span class="bw-tag"><span class="bw-dot {_dot_class(status_s)}"></span><span class="bw-mini">{label}</span></span>'

    left_bits = [
        f'<span class="bw-tag"><span class="bw-dot {_dot_class(status)}"></span><span class="bw-title">READINESS: {report.overall}</span></span>',
        tag(f"Session: {session_id}", "OK"),
        tag(f"Profile: {profile or 'default'}", "OK"),
        tag(f"Gate: {pending_gate or 'none'}", "OK" if (pending_gate or "").lower() == "none" else "WARN"),
    ]

    right_bits = []
    if provider:
        right_bits.append(tag(provider.detail.replace("Provider: ", "Prov: "), provider.status))
    if model:
        right_bits.append(tag(model.detail.replace("Model: ", "Model: "), model.status))
    if redaction:
        right_bits.append(tag(f"Redaction: {redaction.detail.replace('Mode: ','')}", redaction.status))
    if epack:
        # keep it short
        ep = "EPACK: on" if epack.status == "OK" else ("EPACK: off" if "disabled" in epack.detail.lower() else "EPACK: issue")
        right_bits.append(tag(ep, epack.status))

    right_bits.append(tag(f"Audit: {'on' if audit_on else 'off'}", "OK" if audit_on else "WARN"))
    right_bits.append(tag(f"Finalize: {'human' if human_finalize_on else 'auto'}", "OK" if human_finalize_on else "WARN"))

    html = f"""
    <div class="bw-contextbar">
      <div class="bw-contextrow">
        <div class="bw-left">{''.join(left_bits)}</div>
        <div class="bw-right">{''.join(right_bits)}</div>
      </div>
    </div>
    """
    host.markdown(html, unsafe_allow_html=True)


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

    # compact pill row (non-sticky) + expander
    host.markdown(
        """
<style>
.bw-readiness-row { display:flex; gap:8px; align-items:center; flex-wrap:wrap;
  padding: 8px 10px; border-radius: 12px; border:1px solid rgba(0,0,0,0.10); background: rgba(0,0,0,0.02);}
.bw-pill { display:inline-flex; align-items:center; gap:8px; padding:5px 9px; border-radius: 999px;
  border:1px solid rgba(0,0,0,0.12); font-size:12px; background: rgba(255,255,255,0.65); }
.bw-pill .bw-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
</style>
        """,
        unsafe_allow_html=True,
    )

    overall_status = _overall_to_status(report.overall)
    pills = [
        f'<span class="bw-pill"><span class="bw-dot {_dot_class(overall_status)}"></span><b>SYSTEM READINESS:</b> {report.overall}</span>',
    ]

    # Inline, high-signal items only
    for item_id in ("provider_auth", "epack_persist", "redaction", "citation_verify"):
        it = _get_item(report, item_id)
        if not it:
            continue
        pills.append(
            f'<span class="bw-pill" title="{it.detail}"><span class="bw-dot {_dot_class(it.status)}"></span>{it.label}</span>'
        )

    host.markdown(f'<div class="bw-readiness-row">{"".join(pills)}</div>', unsafe_allow_html=True)

    with host.expander("System readiness details (audit-style)", expanded=False):
        host.write(report.summary)
        host.caption(time.strftime("Generated: %Y-%m-%d %H:%M:%S", time.localtime(report.generated_ts)))
        for it in report.items:
            icon = "✅" if it.status == "OK" else ("⚠️" if it.status == "WARN" else "⛔")
            host.markdown(f"**{icon} {it.label}**  \n{it.detail}")

    return report
