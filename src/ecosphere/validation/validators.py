from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ecosphere.utils.stable import stable_hash
from ecosphere.config import Settings


@dataclass(frozen=True)
class ValidationAttempt:
    attempt: int
    ok: bool
    reason: str
    score: float


ALLOWED_KEYS = {"text", "disclosure", "citations", "assumptions"}


# ---------------------------
# Citation schema (BeaconWise)
# ---------------------------

CITATION_REQUIRED_FIELDS = {
    "title",
    "authors_or_org",
    "year",
    "source_type",
    "evidence_strength",
    "verification_status",
}

CITATION_OPTIONAL_FIELDS = {"identifier", "notes"}

CITATION_SOURCE_TYPES = {
    "randomized_trial",
    "meta_analysis",
    "systematic_review",
    "clinical_guideline",
    "observational_study",
    "technical_standard",
    "institutional_report",
    "textbook_reference",
    "general_background",
}

CITATION_EVIDENCE_STRENGTH = {
    "strong_consensus",
    "moderate_evidence",
    "emerging_evidence",
    "contested",
    "contextual_reference",
}

CITATION_VERIFICATION_STATUS = {
    "verified_reference",
    "probable_reference",
    "unverified_model_recall",
    "citation_not_retrieved",
}

# Triggers for implied evidence claims. Conservative on purpose.
EVIDENCE_CLAIM_RE = re.compile(
    r"\b(studies show|research shows|evidence suggests|systematic review|meta-analys(?:is|es)|randomi[sz]ed (?:trial|controlled trial)|RCT\b|clinical guideline|guidelines (?:recommend|suggest)|according to (?:a|the) (?:study|trial|review|meta-analysis))\b",
    re.IGNORECASE,
)


def _validate_citations(obj: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates citations array structure.
    Returns (ok, reason).
    """
    if "citations" not in obj:
        return True, "no_citations_key"

    cites = obj.get("citations")
    if cites is None:
        return True, "citations_null_ok"

    if not isinstance(cites, list):
        return False, "citations_not_list"

    for i, c in enumerate(cites):
        if not isinstance(c, dict):
            return False, f"citation_{i}_not_object"

        missing = CITATION_REQUIRED_FIELDS - set(c.keys())
        if missing:
            return False, f"citation_{i}_missing:{sorted(list(missing))}"

        extra = set(c.keys()) - (CITATION_REQUIRED_FIELDS | CITATION_OPTIONAL_FIELDS)
        if extra:
            return False, f"citation_{i}_extra:{sorted(list(extra))}"

        # Required fields types
        if not isinstance(c.get("title"), str) or not c["title"].strip():
            return False, f"citation_{i}_bad_title"
        if not isinstance(c.get("authors_or_org"), str) or not c["authors_or_org"].strip():
            return False, f"citation_{i}_bad_authors_or_org"

        year = c.get("year")
        if not (isinstance(year, int) or year == "unknown"):
            return False, f"citation_{i}_bad_year"

        st = c.get("source_type")
        if st not in CITATION_SOURCE_TYPES:
            return False, f"citation_{i}_bad_source_type:{st}"

        es = c.get("evidence_strength")
        if es not in CITATION_EVIDENCE_STRENGTH:
            return False, f"citation_{i}_bad_evidence_strength:{es}"

        vs = c.get("verification_status")
        if vs not in CITATION_VERIFICATION_STATUS:
            return False, f"citation_{i}_bad_verification_status:{vs}"

        if "identifier" in c and c["identifier"] is not None and not isinstance(c["identifier"], str):
            return False, f"citation_{i}_bad_identifier"
        if "notes" in c and c["notes"] is not None and not isinstance(c["notes"], str):
            return False, f"citation_{i}_bad_notes"

    return True, "citations_ok"



def validate_json_schema(raw: str) -> Tuple[bool, Dict[str, Any], str]:
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return False, {}, "not_object"

        extra = set(obj) - ALLOWED_KEYS
        if extra:
            return False, {}, f"extra_keys:{sorted(list(extra))}"

        if "text" not in obj or not isinstance(obj["text"], str) or not obj["text"].strip():
            return False, {}, "missing_or_empty_text"

        # Optional fields basic types
        if "disclosure" in obj and obj["disclosure"] is not None and not isinstance(obj["disclosure"], str):
            return False, {}, "disclosure_not_string"

        if "assumptions" in obj:
            a = obj.get("assumptions")
            if a is not None and not isinstance(a, list):
                return False, {}, "assumptions_not_list"
            if isinstance(a, list):
                for i, item in enumerate(a):
                    if not isinstance(item, str):
                        return False, {}, f"assumptions_{i}_not_string"

        ok_c, reason_c = _validate_citations(obj)
        if not ok_c:
            return False, {}, reason_c

        return True, obj, "pass"
    except json.JSONDecodeError as e:
        return False, {}, f"json_error:{str(e)}"


def protected_regions_hash(text: str) -> str:
    """
    PR6: hash of protected regions: code fences + JSON-like blocks.
    Deterministic, conservative.
    """
    fences = re.findall(r"```[\s\S]*?```", text)
    json_blocks = re.findall(r"\{[\s\S]*?\}", text)
    combined = "\n".join(fences + json_blocks)
    return stable_hash(combined)[:16]


def validate_output(user_text: str, raw_output: str, threshold: float = 0.90) -> List[ValidationAttempt]:
    attempts: List[ValidationAttempt] = []

    # Attempt 1: strict JSON + schema (including citations schema)
    ok_schema, obj, reason = validate_json_schema(raw_output)
    attempts.append(ValidationAttempt(1, ok_schema, reason, 1.0 if ok_schema else 0.0))
    if not ok_schema:
        return attempts

    # Attempt 2: evidence-claim gating (if enabled)
    # If the text implies studies/guidelines/reviews, require citations list to be non-empty.
    if Settings.REQUIRE_EVIDENCE_CITATIONS and EVIDENCE_CLAIM_RE.search(obj.get("text", "")):
        cites = obj.get("citations") or []
        ok_ev = isinstance(cites, list) and len(cites) > 0
        attempts.append(ValidationAttempt(2, ok_ev, "evidence_claim_requires_citations", 1.0 if ok_ev else 0.0))
        if not ok_ev:
            return attempts
    else:
        attempts.append(ValidationAttempt(2, True, "evidence_claim_gate_skipped", 1.0))

    # Attempt 3: deterministic placeholder alignment score
    # (Replace with real alignment in future PR; this keeps determinism.)
    align_score = 0.92 if len(user_text) < 200 else 0.88
    ok_align = align_score >= threshold
    attempts.append(ValidationAttempt(3, ok_align, "alignment_check", float(align_score)))

    # Attempt 4: protected region integrity (if user has protected blocks)
    before_hash = protected_regions_hash(user_text)
    after_hash = protected_regions_hash(obj.get("text", ""))
    ok_regions = before_hash == after_hash
    attempts.append(ValidationAttempt(4, ok_regions, "protected_regions", 1.0 if ok_regions else 0.0))

    return attempts
