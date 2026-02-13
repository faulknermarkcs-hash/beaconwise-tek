"""
BeaconWise Academic Preprint Paper
Deterministic Governance Kernels for Auditable AI Systems
Generated with ReportLab Platypus — two-column academic layout
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
pt = 1.0  # 1 point = 1 PDF unit
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, HRFlowable, PageBreak,
    Flowable
)
from reportlab.platypus.flowables import NullDraw
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfgen import canvas as pdfcanvas
import datetime

# ── Color palette ──────────────────────────────────────────────
NAVY      = HexColor("#1B2C5E")
ACCENT    = HexColor("#2563EB")
MID_GRAY  = HexColor("#6B7280")
DARK_GRAY = HexColor("#374151")
LIGHT_BG  = HexColor("#F3F4F6")
RULE_CLR  = HexColor("#D1D5DB")
CREAM     = HexColor("#FAFAF9")

PAGE_W, PAGE_H = letter
MARGIN = 0.85 * inch
COL_GAP = 0.22 * inch
COL_W = (PAGE_W - 2 * MARGIN - COL_GAP) / 2
BODY_W = PAGE_W - 2 * MARGIN  # single-column usable width

# ── Styles ─────────────────────────────────────────────────────
def make_styles():
    s = {}

    s['title'] = ParagraphStyle('PaperTitle',
        fontName='Times-Bold', fontSize=17, leading=21,
        textColor=NAVY, alignment=TA_CENTER,
        spaceAfter=6)

    s['authors'] = ParagraphStyle('Authors',
        fontName='Times-Roman', fontSize=10.5, leading=14,
        textColor=DARK_GRAY, alignment=TA_CENTER, spaceAfter=4)

    s['affil'] = ParagraphStyle('Affil',
        fontName='Times-Italic', fontSize=9, leading=12,
        textColor=MID_GRAY, alignment=TA_CENTER, spaceAfter=4)

    s['date'] = ParagraphStyle('DateLine',
        fontName='Times-Roman', fontSize=9, leading=12,
        textColor=MID_GRAY, alignment=TA_CENTER, spaceAfter=14)

    s['abstract_heading'] = ParagraphStyle('AbsHeading',
        fontName='Times-Bold', fontSize=9, leading=11,
        textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)

    s['abstract'] = ParagraphStyle('Abstract',
        fontName='Times-Roman', fontSize=9, leading=13,
        textColor=DARK_GRAY, alignment=TA_JUSTIFY,
        leftIndent=0.5*inch, rightIndent=0.5*inch, spaceAfter=12)

    s['keywords'] = ParagraphStyle('Keywords',
        fontName='Times-Italic', fontSize=9, leading=12,
        textColor=MID_GRAY, alignment=TA_CENTER,
        leftIndent=0.5*inch, rightIndent=0.5*inch, spaceAfter=14)

    s['section'] = ParagraphStyle('SectionHead',
        fontName='Times-Bold', fontSize=10.5, leading=13,
        textColor=NAVY, spaceBefore=10, spaceAfter=4)

    s['subsection'] = ParagraphStyle('SubsectionHead',
        fontName='Times-BoldItalic', fontSize=9.5, leading=12,
        textColor=DARK_GRAY, spaceBefore=7, spaceAfter=3)

    s['body'] = ParagraphStyle('Body',
        fontName='Times-Roman', fontSize=9.5, leading=13.5,
        textColor=DARK_GRAY, alignment=TA_JUSTIFY,
        spaceAfter=6, firstLineIndent=14)

    s['body_noindent'] = ParagraphStyle('BodyNI',
        fontName='Times-Roman', fontSize=9.5, leading=13.5,
        textColor=DARK_GRAY, alignment=TA_JUSTIFY,
        spaceAfter=6)

    s['caption'] = ParagraphStyle('Caption',
        fontName='Times-Italic', fontSize=8.5, leading=11,
        textColor=MID_GRAY, alignment=TA_CENTER, spaceAfter=8)

    s['table_head'] = ParagraphStyle('TH',
        fontName='Helvetica-Bold', fontSize=8, leading=10,
        textColor=white, alignment=TA_LEFT)

    s['table_body'] = ParagraphStyle('TB',
        fontName='Helvetica', fontSize=8, leading=10,
        textColor=DARK_GRAY, alignment=TA_LEFT)

    s['table_body_it'] = ParagraphStyle('TBI',
        fontName='Helvetica-Oblique', fontSize=8, leading=10,
        textColor=MID_GRAY, alignment=TA_LEFT)

    s['ref'] = ParagraphStyle('Ref',
        fontName='Times-Roman', fontSize=8.5, leading=12,
        textColor=DARK_GRAY, alignment=TA_LEFT,
        leftIndent=14, firstLineIndent=-14, spaceAfter=3)

    s['box_body'] = ParagraphStyle('BoxBody',
        fontName='Helvetica', fontSize=8.5, leading=12,
        textColor=DARK_GRAY, alignment=TA_JUSTIFY, spaceAfter=4)

    s['box_head'] = ParagraphStyle('BoxHead',
        fontName='Helvetica-Bold', fontSize=9, leading=12,
        textColor=NAVY, spaceAfter=4)

    s['code'] = ParagraphStyle('Code',
        fontName='Courier', fontSize=7.5, leading=11,
        textColor=DARK_GRAY, alignment=TA_LEFT,
        leftIndent=6, spaceAfter=3)

    s['footnote'] = ParagraphStyle('Footnote',
        fontName='Times-Roman', fontSize=8, leading=11,
        textColor=MID_GRAY, spaceAfter=2)

    return s


S = make_styles()

# ── Helpers ────────────────────────────────────────────────────
def B(text): return f'<b>{text}</b>'
def I(text): return f'<i>{text}</i>'
def sup(text): return f'<super>{text}</super>'

def bp(text, style='body'): return Paragraph(text, S[style])
def sp(pts=6): return Spacer(1, pts * pt)
def hr(w=None, t=0.5, c=RULE_CLR): return HRFlowable(width=w or '100%', thickness=t, color=c, spaceAfter=4*pt, spaceBefore=4*pt)

def section_head(n, text):
    return Paragraph(f'{n}. {text.upper()}', S['section'])

def subsection_head(n, text):
    return Paragraph(f'{n} {text}', S['subsection'])

def make_table(headers, rows, col_widths, shade_rows=True):
    """Build a styled academic table."""
    data = [[Paragraph(h, S['table_head']) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), S['table_body']) for c in row])

    t = Table(data, colWidths=col_widths)
    style = [
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, LIGHT_BG]),
        ('BOX', (0,0), (-1,-1), 0.5, RULE_CLR),
        ('INNERGRID', (0,0), (-1,-1), 0.3, RULE_CLR),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]
    t.setStyle(TableStyle(style))
    return t


def box(title, body_paragraphs, bg=LIGHT_BG, border=ACCENT):
    """Create a shaded callout box."""
    content = []
    if title:
        content.append(Paragraph(title, S['box_head']))
    for p in body_paragraphs:
        if isinstance(p, str):
            content.append(Paragraph(p, S['box_body']))
        else:
            content.append(p)
    t = Table([[content]], colWidths=[BODY_W - 0.08*inch])
    t.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.0, border),
        ('BACKGROUND', (0,0), (-1,-1), bg),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    return t

def wide_box(title, body_paragraphs, bg=LIGHT_BG, border=ACCENT, width=None):
    """Full-width callout box for single-column sections."""
    w = width or (PAGE_W - 2*MARGIN)
    content = []
    if title:
        content.append(Paragraph(title, S['box_head']))
    for p in body_paragraphs:
        if isinstance(p, str):
            content.append(Paragraph(p, S['box_body']))
        else:
            content.append(p)
    t = Table([[content]], colWidths=[w - 0.08*inch])
    t.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.0, border),
        ('BACKGROUND', (0,0), (-1,-1), bg),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    return t


# ── Header / Footer ────────────────────────────────────────────
class PageLayout:
    def __init__(self):
        self.title_short = "Deterministic Governance Kernels for Auditable AI Systems"

    def onFirstPage(self, canv, doc):
        pass  # cover handled by content

    def onLaterPages(self, canv, doc):
        canv.saveState()
        canv.setFont('Times-Italic', 8)
        canv.setFillColor(MID_GRAY)
        # Header
        canv.drawString(MARGIN, PAGE_H - MARGIN*0.55, self.title_short)
        canv.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN*0.55,
            f"Preprint — February 2026")
        canv.setStrokeColor(RULE_CLR)
        canv.setLineWidth(0.5)
        canv.line(MARGIN, PAGE_H - MARGIN*0.6, PAGE_W - MARGIN, PAGE_H - MARGIN*0.6)
        # Footer
        canv.line(MARGIN, MARGIN*0.7, PAGE_W - MARGIN, MARGIN*0.7)
        canv.drawString(MARGIN, MARGIN*0.45,
            "BeaconWise Transparency Ecosphere Kernel — Apache 2.0")
        canv.drawRightString(PAGE_W - MARGIN, MARGIN*0.45,
            f"Page {doc.page}")
        canv.restoreState()


# ══════════════════════════════════════════════════════════════
#  CONTENT ASSEMBLY
# ══════════════════════════════════════════════════════════════

def two_cols(left_elems, right_elems):
    """Wrap two lists of flowables into a side-by-side two-column Table."""
    from reportlab.platypus import KeepInFrame
    lf = KeepInFrame(COL_W, 99999, left_elems, mode='shrink')
    rf = KeepInFrame(COL_W, 99999, right_elems, mode='shrink')
    t = Table([[lf, rf]], colWidths=[COL_W, COL_W])
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('INNERGRID', (0,0), (-1,-1), 0, white),
        ('BOX', (0,0), (-1,-1), 0, white),
    ]))
    return t


def build_cover():
    """Title block, authors, abstract — full width before columns."""
    elems = []

    # Logo / badge row
    elems.append(sp(4))
    badge = Table([[
        Paragraph('PREPRINT  ·  arXiv SUBMISSION CANDIDATE  ·  NOT PEER REVIEWED',
            ParagraphStyle('badge', fontName='Helvetica', fontSize=7.5,
                textColor=ACCENT, alignment=TA_CENTER))
    ]], colWidths=[PAGE_W - 2*MARGIN])
    badge.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, ACCENT),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    elems.append(badge)
    elems.append(sp(10))

    # Title
    elems.append(Paragraph(
        "Deterministic Governance Kernels for Auditable AI Systems",
        S['title']))
    elems.append(sp(4))

    # Authors
    elems.append(Paragraph(
        "Mark Randall Havens<super>*</super>",
        S['authors']))
    elems.append(Paragraph(
        "<i>Transparency Ecosphere Project — Independent Research</i>",
        S['affil']))
    elems.append(Paragraph(
        "Correspondence: beaconwise-tek [at] transparencyecosphere.org &nbsp;&nbsp;|&nbsp;&nbsp; February 2026",
        S['date']))

    elems.append(hr(t=1.0, c=NAVY))
    elems.append(sp(6))

    # Abstract
    elems.append(Paragraph("ABSTRACT", S['abstract_heading']))
    elems.append(Paragraph(
        "Contemporary AI systems present a fundamental governance problem: their outputs are probabilistic, "
        "their internal decision processes are opaque, and the governance mechanisms deployed over them are "
        "predominantly shallow policy filters rather than structural enforcement infrastructure. This paper "
        "introduces the <i>deterministic governance kernel</i> as an architectural pattern for auditable AI "
        "systems. A governance kernel is a layer positioned above AI models and automated decision pipelines "
        "that enforces deterministic routing rules, maintains cryptographically tamper-evident audit chains, "
        "and enables independent deterministic replay of every governed interaction. We describe the "
        "architecture, formal invariants, and threat model of BeaconWise — a reference implementation of "
        "this pattern currently at v1.9.0 with 355 passing tests and a published open-source specification "
        "suite. We argue that the distinction between <i>governance wrappers</i> (policy filters applied "
        "post-hoc) and <i>governance kernels</i> (structural enforcement with verifiable audit continuity) "
        "is practically important for regulatory compliance, epistemic integrity, and long-term AI "
        "accountability. We describe the kernel's invariants, its threat model against hallucination "
        "propagation, hidden persuasion, silent model drift, and governance capture, and situate it "
        "relative to existing governance approaches.",
        S['abstract']))

    elems.append(Paragraph(
        "<i>Keywords:</i> AI governance, auditable AI, deterministic systems, cryptographic audit, "
        "AI transparency, regulatory compliance, governance infrastructure",
        S['keywords']))

    elems.append(hr(t=1.0, c=NAVY))
    elems.append(sp(8))

    return elems


def build_body():
    """Two-column body content."""

    # ── Left column ───────────────────────────────────────────
    left = []

    # § 1 INTRODUCTION
    left.append(section_head("1", "Introduction"))
    left.append(bp(
        "The governance of AI systems has become a primary concern for regulators, enterprises, and "
        "civil society. The EU AI Act, NIST AI RMF, and ISO/IEC 42001 each establish frameworks for "
        "managing AI risk, requiring traceability, transparency, and human oversight. Yet a structural "
        "gap persists between what these frameworks require and what most deployed governance "
        "mechanisms actually provide."))
    left.append(bp(
        "Most AI governance today consists of policy filters — post-hoc rules applied to model "
        "outputs to screen for prohibited content, enforce tone constraints, or add disclaimers. "
        "These mechanisms share a common failure mode: they govern <i>what the model says</i> "
        "without governing <i>how the decision was made</i>, <i>whether the audit trail is "
        "complete</i>, or <i>whether the governance process itself can be independently verified</i>."))
    left.append(bp(
        "This paper presents an alternative architectural approach: the <b>deterministic governance "
        "kernel</b>. A governance kernel is not a content filter. It is infrastructure — a layer "
        "that enforces deterministic routing, maintains cryptographic evidence continuity, and "
        "enables replay-based audit of every governed interaction. The distinction matters because "
        "a filter can be bypassed, reconfigured, or silently degraded. A kernel enforces invariants "
        "that cannot be overridden by configuration, and its enforcement history is preserved in a "
        "tamper-evident chain available for independent verification."))
    left.append(bp(
        "We describe the architecture of BeaconWise, a reference implementation of this pattern. "
        "BeaconWise is open-source (Apache 2.0), currently at v1.9.0, and includes a published "
        "specification suite comprising nine normative documents covering architecture, security, "
        "threat modeling, evidence lifecycle, replay protocol, and validator governance."))

    left.append(subsection_head("1.1", "Contributions"))
    left.append(bp(
        "This paper makes the following contributions. First, we articulate the "
        "governance kernel as a formal architectural pattern and define its distinguishing "
        "invariants. Second, we present a threat model specific to governance infrastructure — "
        "distinct from model robustness or data security — covering hallucination propagation, "
        "hidden persuasion, silent drift, and governance capture. Third, we describe the "
        "BeaconWise implementation as a concrete, testable instantiation of this pattern. Fourth, "
        "we compare the governance kernel approach to existing governance approaches and characterize "
        "the design space."))

    left.append(subsection_head("1.2", "Scope and Limitations"))
    left.append(bp(
        "BeaconWise governs the <i>process</i> of AI-mediated decision-making — routing, validation, "
        "and audit — not the <i>content</i> of AI outputs. It does not determine factual truth, "
        "moderate speech, or replace domain expertise. The governance guarantees described here apply "
        "to the governance layer itself; the probabilistic behavior of underlying AI models remains "
        "outside the kernel's determinism boundary. This distinction is elaborated in §3."))

    # § 2 BACKGROUND
    left.append(sp(4))
    left.append(section_head("2", "Background and Related Work"))

    left.append(subsection_head("2.1", "The AI Governance Problem"))
    left.append(bp(
        "Large language models (LLMs) and related AI systems present governance challenges that "
        "differ structurally from earlier software governance problems. Unlike traditional software, "
        "LLM outputs are probabilistic: the same input may yield different outputs across calls, "
        "making classical software testing insufficient [1]. The opacity of learned representations "
        "resists conventional audit: there is typically no machine-readable account of why a "
        "particular output was generated [2,3]."))
    left.append(bp(
        "These properties create three distinct audit failures. First, <i>post-hoc "
        "irrecoverability</i>: once an AI interaction occurs without governance recording, the "
        "decision basis is unrecoverable. Second, <i>silent drift</i>: model behavior can change "
        "across API versions, fine-tuning updates, or retrieval corpus changes without any "
        "observable governance event. Third, <i>governance theater</i>: policy filters can be "
        "satisfied in ways that technically comply with rules while violating their intent [4]."))

    left.append(subsection_head("2.2", "Existing Governance Approaches"))
    left.append(bp(
        "Contemporary AI governance mechanisms fall into several categories. "
        "<i>Constitutional AI</i> [5] and related RLHF-based approaches train governance "
        "preferences into model weights. These improve alignment but do not provide external "
        "audit continuity; the model's governance behavior is not independently verifiable "
        "from outside the model."))
    left.append(bp(
        "<i>Guardrails systems</i> such as Nvidia NeMo Guardrails [6], Llama Guard [7], "
        "and similar tools apply rule-based or classifier-based filters to model I/O. "
        "These provide policy enforcement but typically produce no audit records, operate "
        "non-deterministically, and cannot be independently replayed."))
    left.append(bp(
        "<i>Evaluation frameworks</i> such as HELM [8], MMLU [9], and safety benchmarks "
        "assess model capabilities and behaviors in test settings. These provide deployment "
        "decision support but do not govern operational interactions."))
    left.append(bp(
        "<i>Logging and observability</i> systems record model interactions for monitoring "
        "but typically without cryptographic integrity guarantees, deterministic replay "
        "capability, or governance decision traceability."))
    left.append(bp(
        "No existing system provides all of: (a) deterministic routing with verifiable "
        "invariants, (b) cryptographically tamper-evident audit chains, (c) deterministic "
        "replay with explicit divergence classification, and (d) governance independence from "
        "model providers. The governance kernel is designed to provide these properties "
        "together."))

    left.append(subsection_head("2.3", "Regulatory Context"))
    left.append(bp(
        "The EU AI Act (Regulation 2024/1689) imposes technical documentation, traceability, "
        "logging, and human oversight requirements on high-risk AI systems [10]. The NIST AI RMF "
        "organizes governance activities across Govern, Map, Measure, and Manage functions [11]. "
        "ISO/IEC 42001:2023 defines AI management system requirements including audit, "
        "traceability, and continual improvement [12]. These frameworks converge on a set of "
        "infrastructure capabilities — reproducible audit records, verifiable governance "
        "decisions, and accountable oversight chains — that policy filters do not provide. "
        "The governance kernel directly targets this infrastructure gap."))

    # ── Right column ──────────────────────────────────────────
    right = []

    # § 3 KERNEL ARCHITECTURE
    right.append(section_head("3", "Governance Kernel Architecture"))
    right.append(bp(
        "A deterministic governance kernel is a layer positioned above AI inference systems and "
        "below their consumers. It does not modify AI outputs. It enforces governance rules over "
        "the process by which outputs are validated, routed, and recorded, and it maintains a "
        "tamper-evident audit history of every governed interaction. The BeaconWise "
        "Transparency Ecosphere Kernel (TEK) is a concrete implementation of this pattern."))

    right.append(subsection_head("3.1", "Architectural Layers"))
    right.append(bp(
        "BeaconWise organizes governance across six layers:"))

    layers_table = make_table(
        ["Layer", "Function"],
        [
            ["Inference Interface", "Captures I/O; normalizes metadata; records routing decisions. Does not modify outputs."],
            ["Validation Layer", "Independent evaluation of integrity, determinism, and policy compliance."],
            ["Evidence Lifecycle", "EPACK chain formation; SHA-256 hash binding; append-only persistence."],
            ["Governance Layer", "Constitutional invariant enforcement; anti-capture controls."],
            ["Challenger Layer", "Independent escalation; replay verification authority."],
            ["Audit / Replay", "Deterministic replay; divergence detection; certificate generation."],
        ],
        [1.1*inch, BODY_W - 1.18*inch]
    )
    right.append(layers_table)
    right.append(sp(4))

    # Architecture diagram figure
    arch_diag = wide_box(
        "Figure 1: BeaconWise Governance Kernel Architecture",
        [
            Paragraph(
                '<font name="Courier" size="7.5">'
                '┌─────────────────────────────────────────────────────┐<br/>'
                '│              CONSUMER APPLICATION LAYER              │<br/>'
                '├─────────────────────────────────────────────────────┤<br/>'
                '│      GOVERNANCE KERNEL  (BeaconWise TEK v1.9.0)     │<br/>'
                '│  ┌──────────────────┐  ┌──────────────────────────┐ │<br/>'
                '│  │  Inference I/F   │→ │   Evidence Validation    │ │<br/>'
                '│  │  (capture I/O)   │  │   Gate (I2 enforced)     │ │<br/>'
                '│  └──────────────────┘  └──────────────┬───────────┘ │<br/>'
                '│  ┌──────────────────┐                 ↓             │<br/>'
                '│  │  Routing Engine  │  ┌──────────────────────────┐ │<br/>'
                '│  │  (deterministic) │  │   EPACK Chain (SHA-256)  │ │<br/>'
                '│  │  BLOCK│DEFER     │  │   append-only · tamper   │ │<br/>'
                '│  │  CONFIRM│PLAN    │  │   evident · replayable   │ │<br/>'
                '│  │  PROCEED         │  └──────────────────────────┘ │<br/>'
                '│  └──────────────────┘                               │<br/>'
                '│  ┌────────────────────────────────────────────────┐ │<br/>'
                '│  │  Validator Consensus + Challenger Layer        │ │<br/>'
                '│  │  (multi-validator · anti-capture · auditable)  │ │<br/>'
                '│  └────────────────────────────────────────────────┘ │<br/>'
                '├─────────────────────────────────────────────────────┤<br/>'
                '│     AI MODEL LAYER  (OpenAI / Anthropic / OSS)      │<br/>'
                '│     ZERO-TRUST STANCE  ←  Invariant I4              │<br/>'
                '└─────────────────────────────────────────────────────┘'
                '</font>',
                ParagraphStyle('diag', fontName='Courier', fontSize=7.2, leading=9.5,
                    textColor=DARK_GRAY, alignment=TA_LEFT)
            ),
            Paragraph(
                "The governance kernel intercepts all AI model I/O. Routing is deterministic (Invariant I1). "
                "Evidence validation gates reject unvalidated output (I2). The EPACK chain cryptographically "
                "binds every interaction record (I5). Validator consensus and the Challenger layer enforce "
                "governance independence (I6, I7). All layer boundaries are crossed only through "
                "kernel-controlled interfaces; no consumer application has direct model access.",
                S['box_body'])
        ],
        bg=HexColor("#F8FAFF"), border=ACCENT, width=BODY_W)
    right.append(arch_diag)
    right.append(sp(6))

    right.append(subsection_head("3.2", "Core Invariants"))
    right.append(bp(
        "The kernel enforces eight constitutional invariants. These are normative — they cannot "
        "be overridden by configuration or operator instruction:"))

    invs = [
        ("I1", "Deterministic Routing", "Given identical inputs and system state, routing decisions (BLOCK / DEFER / CONFIRM / PLAN / PROCEED) are identical across all invocations."),
        ("I2", "Evidence Validation Gates", "All AI outputs must pass structural validation before delivery. Failed validation produces a structured safe fallback — never unvalidated output."),
        ("I3", "Audit Replayability", "Every interaction produces a complete replay package enabling independent reconstruction of the governance decision."),
        ("I4", "Zero-Trust Model Stance", "All AI outputs are treated as untrusted until validation pipeline completion. No model provider has bypass access."),
        ("I5", "Cryptographic Traceability", "Each EPACK carries a SHA-256 hash referencing the preceding EPACK, forming an append-only tamper-evident chain."),
        ("I6", "Validator Independence", "Governance validation is performed by entities independent from AI model providers and deployment operators."),
        ("I7", "Failure Transparency", "Indeterminate or unsafe governance states produce explicit disclosure artifacts. The kernel never silently defaults to permissive behavior."),
        ("I8", "Constitutional Non-Override", "Invariants I1–I8 cannot be suspended by configuration. Amendments require documented public justification."),
    ]

    inv_table = make_table(
        ["ID", "Invariant", "Specification"],
        [[i[0], B(i[1]), i[2]] for i in invs],
        [0.28*inch, 1.0*inch, BODY_W - 1.38*inch]
    )
    right.append(inv_table)
    right.append(sp(4))

    right.append(subsection_head("3.3", "Deterministic Routing"))
    right.append(bp(
        "The routing layer classifies each governed interaction into one of five outcome "
        "classes: BLOCK (harmful input detected), DEFER (input exceeds competence threshold), "
        "CONFIRM (human confirmation required before delivery), PLAN (multi-step execution "
        "required), or PROCEED (generate and validate). Classification uses deterministic rules "
        "applied over: (a) safety screening results from the input classifier, (b) belief "
        "state across five knowledge domains maintained by Bayesian inference, (c) policy "
        "configuration, and (d) domain-specific routing tables. The routing decision is "
        "invariant: the same input and system state always yield the same classification. "
        "This property is machine-testable and constitutes the core auditability guarantee."))

    right.append(subsection_head("3.4", "Evidence Packaging (EPACK)"))
    right.append(bp(
        "Every governed interaction produces an Evidence PACKet (EPACK) — an atomic audit "
        "record with the following required fields: input payload hash, governance configuration "
        "snapshot, routing decision with rationale, validation results, validator attribution, "
        "environment fingerprint, and SHA-256 hash of the preceding EPACK. EPACKs are "
        "append-only; no modification is permitted after sealing. Any post-hoc modification "
        "breaks the hash chain and is detectable by any party with access to the replay engine, "
        "without requiring access to the original system. This property provides cryptographic "
        "tamper evidence without requiring a blockchain or external trust anchor."))

    right.append(subsection_head("3.5", "Deterministic Replay Protocol"))
    right.append(bp(
        "The Deterministic Replay Protocol (DRP) specifies how any governed run can be "
        "reconstructed from its Replay Package (RP). A replay proceeds in three steps. "
        "First, integrity verification: EPACK chain links, input hashes, and validator "
        "output hashes are verified against recorded values. Any failure terminates replay "
        "with REPLAY_RESULT = TAMPER_DETECTED. Second, environment equivalence check: "
        "the current replay environment fingerprint is compared against the recorded one; "
        "differences are classified as drift factors and the replay continues with "
        "DRIFT_RISK status rather than terminating. Third, deterministic execution: "
        "governance decisions are reproduced using the recorded routing decisions and "
        "determinism policy. The replay result is either VERIFIED (identical), DRIFT "
        "(explainable divergence), or TAMPER_DETECTED (integrity failure). Silent divergence "
        "is not a permitted outcome — the protocol enforces explicit classification."))

    right.append(subsection_head("3.6", "Validator Governance"))
    right.append(bp(
        "BeaconWise employs a multi-validator consensus architecture with a Challenger "
        "layer providing independent oversight. The Validator Governance Constitution "
        "prohibits single-entity validator control, requires auditable validator identities, "
        "and mandates independent operation of secondary validators from primary validators. "
        "The Challenger layer — a role distinct from validators — has authority to trigger "
        "replay audits, escalate disputes, and initiate additional validation independent of "
        "the primary consensus process. These structural anti-capture provisions distinguish "
        "the governance kernel from logging systems, which typically have no mechanism for "
        "detecting validator compromise."))

    right.append(subsection_head("3.7", "Kernel Boundary Specification"))
    right.append(bp(
        "Precisely defining what lies outside the governance kernel's scope is as important "
        "as defining what lies within it. The following properties are explicitly "
        "<b>outside</b> the kernel's determinism boundary: AI model output generation "
        "(probabilistic), factual accuracy determination (domain expert responsibility), "
        "content moderation policy (organizational policy), legal compliance determination "
        "(legal analysis), and user interface design (application layer)."))
    right.append(bp(
        "The following properties are explicitly <b>inside</b> the kernel's determinism "
        "boundary: routing classification given a defined system state, evidence validation "
        "gate pass/fail determination, EPACK record generation and hash chain formation, "
        "validator consensus computation, replay execution and divergence classification, "
        "and constitutional invariant enforcement. This boundary is the governance kernel's "
        "fundamental contribution: it makes the governance process deterministic and "
        "auditable even when operating over a probabilistic AI substrate."))

    # § 4 THREAT MODEL
    right.append(sp(4))
    right.append(section_head("4", "Governance Threat Model"))
    right.append(bp(
        "Governance infrastructure introduces a threat surface distinct from model "
        "robustness or infrastructure security. The relevant threats are not primarily "
        "adversarial model inputs (jailbreaks, prompt injection) but attacks on the "
        "governance layer itself — mechanisms that would allow a system to appear governed "
        "while actually being ungoverned. We identify four primary threat categories "
        "relevant to the design of governance kernels."))

    right.append(subsection_head("4.1", "Hallucination Propagation"))
    right.append(bp(
        "AI language models generate plausible-sounding outputs that may be factually "
        "incorrect, unsupported by cited sources, or internally inconsistent — a property "
        "commonly termed hallucination [13,14]. From a governance perspective, hallucination "
        "is not primarily a model accuracy problem but an audit traceability problem: when "
        "a hallucinated output is acted upon, there is typically no record of which evidence "
        "supported the output, what validation was applied, or whether the output was "
        "flagged as uncertain."))
    right.append(bp(
        "BeaconWise addresses this via the evidence validation gate (Invariant I2) combined "
        "with EPACK-recorded evidence provenance. The validation gate requires that outputs "
        "pass structural integrity and schema compliance checks before delivery; outputs that "
        "fail produce safe fallback artifacts with explicit failure codes rather than "
        "unvalidated content. EPACK records capture the evidence sources used in generation "
        "with cryptographic provenance, enabling post-hoc audit of what information supported "
        "each governed output. This does not prevent hallucination but creates an "
        "auditable record of it."))

    right.append(subsection_head("4.2", "Hidden Persuasion"))
    right.append(bp(
        "AI systems optimized for engagement or user satisfaction may exhibit behaviors "
        "that systematically bias user beliefs or decisions — sycophancy, framing effects, "
        "selective information presentation — without any observable governance event [15]. "
        "This is structurally different from content policy violations because the behavior "
        "may comply with all explicit rules while systematically undermining user epistemic "
        "autonomy."))
    right.append(bp(
        "BeaconWise addresses this through a constitutional prohibition on persuasion "
        "optimization (Transparency Over Persuasion principle) and the Transparent System "
        "Voice (TSV) framework, which reduces anthropomorphic framing that enables "
        "exploitation of human social cognition. The EPACK record preserves the governance "
        "state at delivery time, enabling retrospective audit of whether persuasive "
        "patterns emerged over interaction sequences."))

    right.append(subsection_head("4.3", "Silent Model Drift"))
    right.append(bp(
        "AI model behavior can change without observable governance events through model "
        "updates, fine-tuning, retrieval corpus changes, or context window drift [16]. "
        "From a compliance perspective, this creates a documentation gap: the system "
        "behaves differently than the documented version, but no governance record captures "
        "the change."))
    right.append(bp(
        "Deterministic replay provides structural detection of model drift. Because routing "
        "decisions are deterministic and recorded, replaying a historical interaction against "
        "current system state detects any behavioral change as an explicit divergence — "
        "classified as DRIFT with an associated drift factor record — rather than silent "
        "behavioral change. This does not prevent drift but ensures it is observable and "
        "documented."))

    right.append(subsection_head("4.4", "Governance Capture"))
    right.append(bp(
        "Governance systems are themselves subject to capture — a condition where oversight "
        "authority becomes concentrated, opaque, or aligned with the interests of the "
        "governed entity rather than independent oversight. Capture risk is well-documented "
        "in regulatory contexts [17] but rarely modeled explicitly in AI governance "
        "architecture."))
    right.append(bp(
        "BeaconWise models governance capture as an explicit threat category and implements "
        "structural mitigations: validator independence requirements, anti-capture provisions "
        "in the constitutional governance charter, the Challenger layer as an oversight body "
        "independent of the validator consensus, and prohibition on single-entity validator "
        "control. The governance constitution itself is public and versioned, making any "
        "governance degradation observable to external parties."))

    # Threat model summary table
    right.append(sp(6))
    threat_headers = ["Threat Class", "Attack Vector", "Kernel Mechanism", "Invariant"]
    threat_rows = [
        ["Hallucination\nPropagation", "Unvalidated AI output reaches consumers without evidence provenance",
            "Evidence Validation Gate + EPACK evidence provenance recording", "I2, I5"],
        ["Hidden Persuasion", "AI optimized for engagement exploits human social cognition",
            "Constitutional Transparency Over Persuasion prohibition + TSV framework", "I7 (constitutional)"],
        ["Silent Model Drift", "Model behavior changes across versions without governance event",
            "Deterministic replay detects divergence; explicit DRIFT classification — never silent",
            "I1, I3"],
        ["Non-Reproducible\nOutputs", "Governance decisions cannot be independently reconstructed",
            "Deterministic Replay Protocol produces VERIFIED / DRIFT / TAMPER_DETECTED — no silent outcome",
            "I1, I3, I5"],
        ["Governance Capture", "Validator authority concentrates or becomes provider-aligned",
            "Multi-validator consensus + Challenger layer + constitutional anti-capture provisions + public versioned charter",
            "I6, I8"],
    ]
    threat_table = make_table(
        threat_headers, threat_rows,
        [1.0*inch, 1.5*inch, 2.2*inch, BODY_W - 4.8*inch]
    )
    right.append(threat_table)
    right.append(bp("Table 3: Governance threat model — threat classes, attack vectors, and kernel mitigations.", 'caption'))

    # Assemble two-column body
    return left, right


def build_comparison():
    """§5 Comparison — full width for readability."""
    elems = []

    elems.append(section_head("5", "Comparison to Existing Governance Approaches"))
    elems.append(bp(
        "The governance kernel pattern differs from existing approaches along three key "
        "dimensions: architectural depth (wrapper vs. infrastructure), verification mode "
        "(evaluation vs. enforcement), and audit continuity (logging vs. tamper-evident "
        "chain). Table 1 summarizes these distinctions.",
        'body_noindent'))
    elems.append(sp(4))

    # Wide comparison table
    headers = ["Approach", "Architectural Depth", "Audit Continuity", "Replay Capability", "Governance Independence"]
    rows = [
        ["Constitutional AI / RLHF", "Model-internal (weights)", "None — behavior not externally auditable", "Not applicable", "Not applicable — model provider controls"],
        ["Guardrails / Policy Filters\n(NeMo, Llama Guard)", "Post-hoc wrapper", "No cryptographic guarantee; typically no audit record", "Not supported", "Often tightly coupled to inference provider"],
        ["Evaluation Frameworks\n(HELM, benchmarks)", "Pre-deployment assessment", "Deployment-time snapshot; no operational continuity", "Not applicable", "Independent of model provider"],
        ["Observability / Logging\n(LLM observability tools)", "Infrastructure layer", "Records interactions; no cryptographic integrity", "Limited; no determinism guarantee", "Variable; often provider-coupled"],
        [B("Governance Kernel (BeaconWise)"), B("Independent governance infrastructure"), B("SHA-256 EPACK chain; tamper-evident; append-only"), B("Full deterministic replay; explicit divergence classification"), B("Constitutionally enforced provider independence")],
    ]

    full_w = PAGE_W - 2*MARGIN
    col_ws = [1.3*inch, 1.4*inch, 1.8*inch, 1.5*inch, 1.55*inch]
    # Adjust last col to fill
    col_ws[-1] = full_w - sum(col_ws[:-1])

    data = [[Paragraph(h, S['table_head']) for h in headers]]
    for i, row in enumerate(rows):
        is_last = (i == len(rows) - 1)
        style = S['table_body'] if not is_last else ParagraphStyle('TBB',
            parent=S['table_body'], fontName='Helvetica-Bold', textColor=NAVY)
        data.append([Paragraph(str(c), style) for c in row])

    t = Table(data, colWidths=col_ws)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [white, LIGHT_BG]),
        ('BACKGROUND', (0, len(rows)), (-1, len(rows)), HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 0.5, RULE_CLR),
        ('INNERGRID', (0,0), (-1,-1), 0.3, RULE_CLR),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elems.append(t)
    elems.append(bp("Table 1: Comparison of AI governance approaches across key dimensions. "
        "BeaconWise row represents the governance kernel pattern.", 'caption'))
    elems.append(sp(6))

    elems.append(bp(
        "The critical distinction between wrappers and infrastructure is not merely "
        "technical sophistication but the nature of the governance guarantee. A wrapper "
        "intercepts outputs and applies rules; its operation can be monitored, but its "
        "governance behavior is not independently verifiable by external parties without "
        "access to the deployment environment. Infrastructure enforces invariants whose "
        "compliance can be verified from the audit record alone, without access to the "
        "running system. This property — sometimes called <i>audit independence</i> — "
        "is what regulatory frameworks require when they "
        "specify that AI systems be auditable by third parties.", 'body_noindent'))

    elems.append(bp(
        "The distinction between evaluation and enforcement is similarly consequential. "
        "Evaluation approaches produce evidence about model behavior under test conditions "
        "but do not govern operational behavior. A model may score well on safety benchmarks "
        "while exhibiting unsafe behavior in operational contexts, a gap documented in "
        "multiple evaluation studies [18,19]. Enforcement approaches apply governance "
        "rules to every operational interaction, not to test samples.", 'body_noindent'))

    return elems


def build_implementation():
    """§6 Implementation snapshot."""
    elems = []

    elems.append(section_head("6", "Implementation: BeaconWise v1.9.0"))
    elems.append(bp(
        "BeaconWise is a reference implementation of the governance kernel pattern, "
        "developed as open-source infrastructure under the Apache 2.0 license. As of "
        "v1.9.0 (February 2026), the implementation includes the following components:",
        'body_noindent'))
    elems.append(sp(4))

    impl_headers = ["Component", "Status", "Key Metric"]
    impl_rows = [
        ["Governance kernel\n(routing, validation)", "Production", "Deterministic routing across 5 outcome classes; 100% routing test coverage"],
        ["EPACK chain\n(evidence lifecycle)", "Production", "SHA-256 chain with 6-stage lifecycle: ingest → validate → bind → persist → challenge → archive"],
        ["Replay engine\n(DRP implementation)", "Production", "Full RP reconstruction; VERIFIED / DRIFT / TAMPER_DETECTED classification"],
        ["Validator consensus\n+ Challenger layer", "Production", "Multi-validator; constitutionally enforced independence; challenger escalation"],
        ["Safety screening\n(input classification)", "Production", "Deterministic rule-based classifier; no probabilistic classification in governance path"],
        ["LLM provider adapters", "Production", "OpenAI, Anthropic, open-source models, retrieval pipelines; vendor-neutral"],
        ["Test suite", "355 passing tests", "Governance kernel, replay, validator consensus, evidence lifecycle, V9 capabilities"],
        ["Specification suite", "9 normative docs", "Architecture, Security, Threat Model, Replay Protocol, Evidence Lifecycle, Validator Governance, Compliance Mapping, Constitution, Adoption Guide"],
    ]
    t = make_table(impl_headers, impl_rows, [1.2*inch, 1.1*inch, PAGE_W - 2*MARGIN - 2.4*inch])
    elems.append(t)
    elems.append(bp("Table 2: BeaconWise v1.9.0 component status.", 'caption'))
    elems.append(sp(6))

    elems.append(bp(
        "The architecture is organized around the <tt>src/ecosphere/</tt> package hierarchy, "
        "with submodules for the kernel, consensus, governance, replay, validation, evidence "
        "lifecycle (epack), safety screening, provider adapters, and the Transparent System "
        "Voice (TSV) framework. The governance constitution is machine-readable and normatively "
        "referenced by the kernel at runtime — constitutional invariants are not documentation "
        "but enforced constraints.", 'body_noindent'))

    elems.append(subsection_head("6.1", "Verification Properties"))
    elems.append(bp(
        "Each constitutional invariant is associated with a specific verification procedure. "
        "Invariant I1 (Deterministic Routing) can be verified by any party by replaying "
        "the same input N times against the stored EPACK records and confirming identical "
        "routing decisions in all N cases. Invariant I5 (Cryptographic Traceability) can "
        "be verified by any party with access to the EPACK chain by confirming that each "
        "record's hash correctly references its predecessor — a procedure that requires no "
        "access to the original system or private keys. Invariant I7 (Failure Transparency) "
        "can be verified by injecting ambiguous or safety-indeterminate inputs and confirming "
        "that explicit disclosure artifacts are produced rather than silent passthrough. "
        "These properties make BeaconWise governance externally auditable in the sense "
        "required by regulatory frameworks: a third party can verify governance compliance "
        "from the audit record alone."))

    elems.append(subsection_head("6.2", "Open Source Availability"))
    elems.append(bp(
        "The complete source code, specification suite, and test suite are publicly "
        "available under Apache 2.0. The governance constitution, threat model, and "
        "all normative specifications are published as versioned documentation within "
        "the repository. The specification documents use RFC 2119 normative language "
        "(MUST, SHOULD, MAY) and are designed to be machine-readable for future "
        "automated conformance verification."))

    elems.append(sp(6))

    # Module structure diagram
    pkg_diag = wide_box(
        "Figure 2: BeaconWise v1.9.0 Package Structure",
        [
            Paragraph(
                '<font name="Courier" size="7.5">'
                'src/ecosphere/<br/>'
                '├── kernel/           # Constitutional invariant enforcement<br/>'
                '│   ├── router.py     # Deterministic routing (I1)<br/>'
                '│   ├── gates.py      # Evidence validation gates (I2)<br/>'
                '│   └── constitution.py  # 13 invariants, runtime-enforced<br/>'
                '├── consensus/        # Multi-validator consensus (I6)<br/>'
                '│   ├── validators.py # Primary + secondary validators<br/>'
                '│   └── challenger.py # Independent oversight layer<br/>'
                '├── governance/       # Policy routing tables<br/>'
                '├── replay/           # DRP implementation (I3)<br/>'
                '│   ├── engine.py     # RP reconstruction + classification<br/>'
                '│   └── certificates/ # VERIFIED/DRIFT/TAMPER_DETECTED<br/>'
                '├── epack/            # Evidence lifecycle (I5)<br/>'
                '│   ├── chain.py      # SHA-256 append-only hash chain<br/>'
                '│   └── lifecycle.py  # ingest→validate→bind→persist→archive<br/>'
                '├── safety/           # Deterministic input classification<br/>'
                '├── providers/        # Vendor-neutral adapters<br/>'
                '│   ├── openai.py     # OpenAI adapter<br/>'
                '│   ├── anthropic.py  # Anthropic adapter<br/>'
                '│   └── retrieval.py  # RAG/retrieval pipelines<br/>'
                '└── tsv/              # Transparent System Voice framework<br/>'
                'docs/                 # 9 normative specification documents<br/>'
                'tests/                # 355 passing tests (full invariant coverage)'
                '</font>',
                ParagraphStyle('pkg', fontName='Courier', fontSize=7.2, leading=10,
                    textColor=DARK_GRAY, alignment=TA_LEFT)
            )
        ],
        bg=HexColor("#F8FAFF"), border=ACCENT, width=BODY_W)
    elems.append(pkg_diag)
    elems.append(bp("Package structure as of v1.9.0. All modules enforce constitutional invariants "
        "through kernel interfaces; no module has direct model provider access.", 'caption'))
    elems.append(sp(6))

    elems.append(subsection_head("6.3", "Regulatory Infrastructure Mapping"))
    elems.append(bp(
        "Table 4 maps BeaconWise implementation components to specific regulatory "
        "infrastructure requirements. This mapping is informative only; compliance "
        "requires organizational processes and legal analysis beyond governance "
        "infrastructure capabilities."))
    elems.append(sp(4))

    reg_headers = ["Regulatory Requirement", "Standard / Article", "BeaconWise Component", "Strength"]
    reg_rows = [
        ["Automatic log generation for each operation", "EU AI Act Art. 12", "EPACK mandatory audit recording", "Direct implementation"],
        ["Technical documentation of system capabilities", "EU AI Act Art. 11", "9 normative public specifications + ARCHITECTURE.md", "Substantive"],
        ["Human oversight capability", "EU AI Act Art. 14", "CONFIRM routing gate; Challenger escalation", "Infrastructure support"],
        ["Measurement of AI system behavior", "NIST AI RMF MEASURE 2.5", "Deterministic replay enables regression testing across versions", "Direct implementation"],
        ["Incident response and documentation", "NIST AI RMF MANAGE 1.3", "EPACK incident recording with permanent audit entry", "Substantive"],
        ["Internal audit capability", "ISO/IEC 42001 Cl. 9.2", "EPACK chain replay without access to production system", "Substantive"],
        ["Risk management documentation", "ISO/IEC 42001 Cl. 6.1", "Formal threat model with 5 adversary classes", "Strong"],
        ["AI policy documentation", "ISO/IEC 42001 Cl. 5.2", "Machine-readable CONSTITUTION.md with 13 normative invariants", "Strong"],
    ]
    reg_table = make_table(reg_headers, reg_rows,
        [1.9*inch, 1.4*inch, 2.1*inch, 1.3*inch])
    elems.append(reg_table)
    elems.append(bp("Table 4: BeaconWise regulatory infrastructure mapping. "
        "Deployers remain responsible for full compliance; this table maps "
        "technical capabilities to regulatory infrastructure prerequisites only.", 'caption'))

    elems.append(sp(6))
    elems.append(subsection_head("6.4", "V9 Resilience Control Plane"))
    elems.append(bp(
        "BeaconWise v1.9.0 extends the governance kernel with a Resilience Control Plane — "
        "a closed-loop feedback architecture that closes the gap between governance anomaly "
        "detection and recovery action. Where earlier versions could detect governance "
        "failures (via EPACK replay and tamper classification), v1.9.0 can also respond "
        "deterministically, verify that responses improved system health, and circuit-break "
        "persistently degraded validators — all with full EPACK audit continuity.",
        'body_noindent'))
    elems.append(bp(
        "The control plane is implemented across nine components in the "
        "<tt>meta_validation/</tt> module. The "
        "<b>TSI Tracker</b> maintains a sliding-window Trust-Signal Index aggregating "
        "interaction outcomes (PASS=0.90, WARN=0.70, REFUSE=0.45, ERROR=0.30) with "
        "exponential decay weighting and a 15-minute linear forecast — replacing the "
        "prior hardcoded 0.85/0.55 TSI thresholds with a runtime-computed signal. "
        "The <b>Recovery Engine</b> performs deterministic plan selection over a "
        "tiered recovery policy compiled from YAML, applying budget constraints "
        "(latency, cost), tier penalties, and oscillation penalties, with "
        "tie-breaking on (score, predicted_independence_gain, −tier). The "
        "<b>Damping Stabilizer</b> applies PID-inspired rollout velocity control "
        "(k<sub>p</sub>=0.5, k<sub>i</sub>=0.2, k<sub>d</sub>=0.1) to prevent "
        "governance oscillation — the yo-yo pattern where rapid recovery actions "
        "introduce more instability than the original failure.",
        'body_noindent'))
    elems.append(bp(
        "The <b>Circuit Breaker</b> tracks per-plan failure sequences through "
        "a CLOSED → OPEN → HALF_OPEN → CLOSED state machine, with auditable "
        "<tt>state_snapshot()</tt> output persisted to EPACK. The "
        "<b>Post-Recovery Verifier</b> closes the loop: after a recovery action "
        "is applied, it checks whether TSI actually improved against configured "
        "thresholds and produces a structured rollback recommendation if it did not. "
        "The <b>Meta-Validation Index (MVI)</b> operationalizes the governance kernel "
        "principle that governance must itself be governed: it computes a weighted "
        "composite score (replay stability 40%, recovery consistency 35%, TSI "
        "coherence 25%, pass threshold 0.80) as a runtime health indicator for "
        "the governance pipeline itself — not for AI output quality.",
        'body_noindent'))
    elems.append(bp(
        "All resilience events — RECOVERY_TRIGGERED, RECOVERY_DECISION, "
        "RECOVERY_APPLIED, RECOVERY_VERIFIED, RECOVERY_ROLLBACK, CIRCUIT_BREAKER — "
        "are recorded as <b>Recovery EPACK Events</b>, hash-chained via "
        "<tt>prev_hash</tt> and persisted to the standard EPACK audit store. "
        "Resilience governance is therefore auditable by the same replay "
        "infrastructure as any other governed interaction. The "
        "<b>Policy Compiler</b> compiles the <tt>resilience_policy</tt> YAML "
        "block (enterprise_v9.yaml) into a <tt>ResilienceRuntime</tt> instance "
        "at startup, with graceful degradation on parse errors. "
        "The <b>Resilience Runtime</b> provides the orchestration API: "
        "<tt>maybe_recover()</tt> → engine decide → damping → circuit breaker; "
        "<tt>verify_recovery()</tt> → post-recovery TSI check → circuit breaker "
        "feedback; <tt>record_outcome()</tt> → TSI tracker update.",
        'body_noindent'))
    elems.append(sp(4))

    # V9 component table
    v9_headers = ["Component", "Module", "Core Property"]
    v9_rows = [
        ["TSI Tracker", "meta_validation/tsi_tracker.py",
            "Sliding-window trust-signal with exponential decay; 15-min forecast; replaces hardcoded thresholds"],
        ["Recovery Engine", "meta_validation/recovery_engine.py",
            "Deterministic plan selection over tiered policy; budget + oscillation constraints; audit-logged decisions"],
        ["Damping Stabilizer", "meta_validation/damping_stabilizer.py",
            "PID-inspired rollout control (kp=0.5, ki=0.2, kd=0.1); prevents recovery oscillation; integral capping"],
        ["Circuit Breaker", "meta_validation/circuit_breaker.py",
            "Per-plan CLOSED→OPEN→HALF_OPEN state machine; state_snapshot() → EPACK; manual break-glass reset"],
        ["Post-Recovery Verifier", "meta_validation/post_recovery_verifier.py",
            "Closed-loop: did recovery improve TSI? MVI check + structured rollback recommendation"],
        ["Meta-Validation Index", "meta_validation/mvi.py",
            "Validate the validator: replay stability (40%) + recovery consistency (35%) + TSI coherence (25%)"],
        ["Recovery EPACK Events", "meta_validation/recovery_events.py",
            "6 event types; prev_hash chained; persisted to EPACK JSONL + in-memory store"],
        ["Policy Compiler", "meta_validation/policy_compiler.py",
            "Compiles resilience_policy YAML → ResilienceRuntime; V8/V9 policy shapes; graceful degradation"],
        ["Resilience Runtime", "meta_validation/resilience_runtime.py",
            "Orchestration: maybe_recover() + verify_recovery() + record_outcome() + dependency_metrics()"],
    ]
    v9_table = make_table(v9_headers, v9_rows,
        [1.5*inch, 2.1*inch, BODY_W - 3.7*inch])
    elems.append(v9_table)
    elems.append(bp("Table 5: V9 Resilience Control Plane components. All components are deterministic, "
        "independently testable, and produce EPACK-persisted audit records.", 'caption'))

    elems.append(sp(4))
    elems.append(bp(
        "The Resilience Control Plane is significant for governance credibility "
        "because it operationalizes the distinction between detection and response. "
        "A governance kernel that detects anomalies but cannot respond to them "
        "provides audit continuity without remediation capability — useful for "
        "forensic purposes but insufficient for operational governance in production "
        "environments. The V9 control plane closes this gap while preserving the "
        "core invariant: every recovery decision is deterministic, every action is "
        "auditable, and every outcome is verifiable. Resilience governance is not "
        "a parallel system; it is an extension of the same EPACK audit infrastructure "
        "that governs AI inference.",
        'body_noindent'))

    return elems


def build_discussion():
    """§7 Discussion."""
    left = []
    right = []

    left.append(section_head("7", "Discussion"))

    left.append(subsection_head("7.1", "Governance Kernels as Infrastructure"))
    left.append(bp(
        "The analogy between governance kernels and operating system kernels is instructive. "
        "An OS kernel does not constrain application logic; it enforces resource "
        "management, memory protection, and process isolation as non-negotiable structural "
        "properties of the execution environment. Applications run on top of the kernel but "
        "cannot violate its invariants through configuration. The governance kernel applies "
        "the same pattern to AI governance: AI models operate within the governance "
        "environment but cannot bypass its enforcement through output manipulation or "
        "deployment configuration."))
    left.append(bp(
        "This framing suggests that AI governance infrastructure will likely follow a "
        "layered adoption path similar to other infrastructure standards: initial adoption "
        "by early-mover regulated industries (healthcare, finance, legal), followed by "
        "expansion as regulatory requirements formalize, followed by commodity adoption "
        "as governance infrastructure becomes assumed baseline. The current moment — "
        "regulatory frameworks active but implementation requirements underspecified — "
        "is the appropriate window for establishing open governance infrastructure standards."))

    left.append(subsection_head("7.2", "Determinism Scope"))
    left.append(bp(
        "A critical clarification: the determinism guarantee in a governance kernel "
        "applies to the <i>governance decision</i>, not to the AI model output. Underlying "
        "LLMs remain stochastic; the same prompt may yield different responses. The "
        "governance kernel's determinism boundary covers the routing, validation, and "
        "audit recording processes — which are deterministic — and explicitly records "
        "which aspects of the system are non-deterministic. This is the appropriate scope "
        "for regulatory purposes: regulators need to verify that governance processes were "
        "consistently applied, not that AI outputs were identical."))

    left.append(subsection_head("7.3", "Limitations"))
    left.append(bp(
        "BeaconWise addresses the governance infrastructure problem but does not address "
        "the full scope of AI governance. Evidence validation gates check structural "
        "integrity and policy compliance, not factual accuracy. Cryptographic audit "
        "chains preserve governance history but cannot recover from catastrophic storage "
        "loss without redundancy. Validator independence provisions prevent formal capture "
        "but cannot prevent informal influence. Anti-persuasion provisions address "
        "architectural design choices but cannot prevent persuasive content from appearing "
        "in AI outputs."))
    left.append(bp(
        "More fundamentally, a governance kernel governs the <i>process</i> of AI-mediated "
        "interaction, not the <i>quality</i> of AI judgment. An AI system producing "
        "consistently wrong answers will have a well-governed audit trail of consistently "
        "wrong answers. The governance kernel is necessary but not sufficient for "
        "trustworthy AI systems."))

    right.append(subsection_head("7.4", "Relationship to Regulatory Requirements"))
    right.append(bp(
        "The governance kernel architecture maps directly to several infrastructure "
        "requirements that existing governance frameworks specify but do not provide. "
        "The EU AI Act Article 12 requires that high-risk AI systems 'automatically "
        "generate logs'; EPACK mandatory audit recording satisfies this at the "
        "infrastructure level rather than relying on application-layer logging. "
        "NIST AI RMF MEASURE 2.5 requires that AI systems be testable; deterministic "
        "replay enables regression testing of governance decisions across software "
        "versions. ISO/IEC 42001 Clause 9.2 requires internal audit capability; "
        "EPACK chain replay enables third-party audit without requiring access to "
        "the production system."))
    right.append(bp(
        "This mapping does not imply that deploying BeaconWise satisfies regulatory "
        "obligations. Compliance requires organizational processes, legal analysis, and "
        "domain-specific governance that governance infrastructure alone cannot provide. "
        "The claim is narrower: governance infrastructure that lacks the properties "
        "provided by the governance kernel — tamper-evident audit chains, deterministic "
        "replay, invariant enforcement — cannot satisfy the infrastructure prerequisites "
        "that these regulatory requirements assume."))

    right.append(subsection_head("7.5", "Future Work"))
    right.append(bp(
        "Several directions merit further development. First, formal verification of "
        "governance invariants: the current invariants are specified in natural language "
        "and tested empirically; formal specifications amenable to automated proof would "
        "strengthen the governance guarantee. Second, evaluation methodology for "
        "governance kernels: a benchmark for comparing governance infrastructure systems "
        "across auditability, determinism, and replay fidelity dimensions would support "
        "the emerging field. Third, sector-specific governance profiles: the generic "
        "kernel architecture needs instantiation in healthcare, legal, and financial "
        "contexts where domain-specific governance requirements interact with the "
        "general infrastructure properties described here. Fourth, interoperability: "
        "as governance infrastructure matures, standardization of audit record formats "
        "and replay protocols would enable cross-system governance auditing."))

    return left, right


def build_conclusion():
    elems = []
    elems.append(section_head("8", "Conclusion"))
    elems.append(bp(
        "We have presented the deterministic governance kernel as an architectural pattern "
        "for auditable AI systems, characterized its distinguishing invariants, described "
        "its threat model, and documented the BeaconWise TEK as a reference implementation. "
        "The central claim is straightforward: effective AI governance requires infrastructure "
        "— deterministic enforcement, cryptographic audit continuity, and independent replay "
        "capability — that existing governance approaches do not provide.",
        'body_noindent'))
    elems.append(bp(
        "The BeaconWise implementation demonstrates that these properties are achievable in "
        "a production-grade open-source system. The 355-test suite provides a verifiable "
        "conformance baseline. The nine normative specification documents provide a "
        "foundation for standardization. The Apache 2.0 license ensures the infrastructure "
        "remains available as a commons resource rather than a proprietary governance layer.",
        'body_noindent'))
    elems.append(bp(
        "AI governance is at an inflection point. Regulatory frameworks are active; "
        "implementation requirements are being defined; the infrastructure layer that "
        "makes compliance operationally tractable is nascent. The governance kernel "
        "pattern, and BeaconWise as a reference implementation, represents one contribution "
        "to that infrastructure foundation.",
        'body_noindent'))
    return elems


def build_references():
    refs = [
        ("[1]", "Bommasani, R. et al. (2021). On the opportunities and risks of foundation models. <i>arXiv preprint arXiv:2108.07258</i>."),
        ("[2]", "Doshi-Velez, F., & Kim, B. (2017). Towards a rigorous science of interpretable machine learning. <i>arXiv preprint arXiv:1702.08608</i>."),
        ("[3]", "Lipton, Z. C. (2018). The mythos of model interpretability. <i>Queue, 16(3)</i>, 31–57."),
        ("[4]", "Perez, E. et al. (2022). Red teaming language models with language models. <i>arXiv preprint arXiv:2202.03286</i>."),
        ("[5]", "Bai, Y. et al. (2022). Constitutional AI: Harmlessness from AI feedback. <i>arXiv preprint arXiv:2212.08073</i>."),
        ("[6]", "Rebedea, T. et al. (2023). NeMo Guardrails: A toolkit for controllable and safe LLM applications. <i>Proceedings of EMNLP 2023</i>."),
        ("[7]", "Inan, H. et al. (2023). Llama Guard: LLM-based input-output safeguard for human-AI conversations. <i>arXiv preprint arXiv:2312.06674</i>."),
        ("[8]", "Liang, P. et al. (2022). Holistic evaluation of language models. <i>arXiv preprint arXiv:2211.09110</i>."),
        ("[9]", "Hendrycks, D. et al. (2020). Measuring massive multitask language understanding. <i>arXiv preprint arXiv:2009.03300</i>."),
        ("[10]", "European Parliament (2024). Regulation 2024/1689 on artificial intelligence. <i>Official Journal of the European Union</i>."),
        ("[11]", "NIST (2023). AI Risk Management Framework (AI RMF 1.0). <i>National Institute of Standards and Technology</i>. doi:10.6028/NIST.AI.100-1."),
        ("[12]", "ISO/IEC (2023). ISO/IEC 42001:2023 Information technology — Artificial intelligence — "
            "Management system. <i>International Organization for Standardization</i>."),
        ("[13]", "Maynez, J. et al. (2020). On faithfulness and factuality in abstractive summarization. <i>Proceedings of ACL 2020</i>."),
        ("[14]", "Ji, Z. et al. (2023). Survey of hallucination in natural language generation. <i>ACM Computing Surveys, 55(12)</i>, 1–38."),
        ("[15]", "Perez, E. et al. (2023). Sycophancy to subterfuge: Investigating reward tampering in language models. <i>arXiv preprint arXiv:2306.09467</i>."),
        ("[16]", "Chen, L. et al. (2023). How is ChatGPT's behavior changing over time? <i>arXiv preprint arXiv:2307.09009</i>."),
        ("[17]", "Stigler, G. J. (1971). The theory of economic regulation. <i>The Bell Journal of Economics and Management Science, 2(1)</i>, 3–21."),
        ("[18]", "Huang, J. et al. (2023). A survey on hallucination in large language models. <i>arXiv preprint arXiv:2309.01219</i>."),
        ("[19]", "Kambhampati, S. (2024). Can LLMs really reason and plan? <i>Communications of the ACM</i>."),
    ]

    elems = []
    elems.append(hr(t=0.8, c=NAVY))
    elems.append(sp(2))
    elems.append(Paragraph("REFERENCES", S['section']))
    for num, text in refs:
        elems.append(Paragraph(f"{num} {text}", S['ref']))
    elems.append(sp(8))

    elems.append(hr(t=0.5, c=RULE_CLR))
    elems.append(Paragraph(
        f"<super>*</super> Correspondence: Transparency Ecosphere Project, Louisville, KY. "
        "Source code and specifications: https://github.com/beaconwise-tek/beaconwise &nbsp;"
        "(verify current URL) &nbsp; License: Apache 2.0 &nbsp; Submitted: February 2026",
        S['footnote']))
    return elems


# ══════════════════════════════════════════════════════════════
#  BUILD PDF
# ══════════════════════════════════════════════════════════════

def build_pdf(output_path):
    layout = PageLayout()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=MARGIN * 1.2,
        bottomMargin=MARGIN,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
    )

    story = []

    # Cover (full width)
    story.extend(build_cover())

    # §1 Intro + §2 Background in two columns
    left_body, right_body = build_body()
    story.extend(left_body)
    story.extend(right_body)

    story.append(sp(8))
    story.append(hr(t=0.5, c=RULE_CLR))

    # §5 Comparison (full width — table too wide for columns)
    story.extend(build_comparison())

    story.append(hr(t=0.5, c=RULE_CLR))

    # §6 Implementation (full width — table too wide)
    story.extend(build_implementation())

    story.append(hr(t=0.5, c=RULE_CLR))

    # §7 Discussion in two columns
    disc_left, disc_right = build_discussion()
    story.extend(disc_left)
    story.extend(disc_right)

    story.append(sp(6))
    story.append(hr(t=0.5, c=RULE_CLR))

    # §8 Conclusion (full width)
    story.extend(build_conclusion())

    # References (full width)
    story.extend(build_references())

    doc.build(story,
        onFirstPage=layout.onFirstPage,
        onLaterPages=layout.onLaterPages)

    print(f"✓ Paper written to {output_path}")


if __name__ == "__main__":
    output = "/home/claude/beaconwise_preprint.pdf"
    build_pdf(output)
