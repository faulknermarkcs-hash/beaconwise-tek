from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from ecosphere.storage.store import read_jsonl
from ecosphere.utils.stable import stable_hash


# Public APIs used:
# - Crossref Works API (https://api.crossref.org/)
# - NCBI E-utilities (PubMed) (https://eutils.ncbi.nlm.nih.gov/)
#
# This module is intentionally deterministic-ish:
# - fixed timeouts
# - stable ranking rules
# - no randomness
#
# Note: Upstream databases can change over time. Callers should record
# verification timestamps + selected identifiers in the audit trail.

CROSSREF_WORKS = "https://api.crossref.org/works"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)


@dataclass(frozen=True)
class VerificationEvent:
    idx: int
    status_before: str
    status_after: str
    method: str  # crossref|pubmed|identifier_only|no_match|error
    identifier: Optional[str]
    confidence: float  # 0..1
    note: str


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def _fingerprint(cite: Dict[str, Any]) -> str:
    """Stable key for caching verification results.

    We intentionally avoid including dynamic fields (like identifier, notes) so
    citations that differ only by later-resolved identifiers still map to the
    same cache entry.
    """
    key_obj = {
        "title": _norm(str(cite.get("title") or "")),
        "authors_or_org": _norm(str(cite.get("authors_or_org") or "")),
        "year": cite.get("year") if cite.get("year") is not None else "unknown",
        "source_type": _norm(str(cite.get("source_type") or "")),
    }
    return stable_hash(key_obj)


def _load_cache_from_epacks(epack_store_path: str, limit: int = 5000) -> Dict[str, Dict[str, Any]]:
    """Build a cache from persisted EPACK records.

    We read `extra.gen_meta.citation_cache_updates` (if present) and assemble
    the latest mapping per fingerprint.
    """
    cache: Dict[str, Dict[str, Any]] = {}
    try:
        rows = read_jsonl(epack_store_path, limit=limit)
    except Exception:
        return cache

    for row in rows:
        payload = (row or {}).get("payload") or {}
        extra = payload.get("extra") or {}
        gen_meta = extra.get("gen_meta") or {}
        updates = gen_meta.get("citation_cache_updates")
        if not isinstance(updates, list):
            continue
        for u in updates:
            if not isinstance(u, dict):
                continue
            k = str(u.get("fingerprint") or "")
            ident = u.get("identifier")
            if not k or not ident:
                continue
            cache[k] = dict(u)
    return cache


# Process-wide cache (deterministic selection rules; upstream DB changes are
# mitigated by caching resolved identifiers).
_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_LOADED_FROM: Optional[str] = None


def get_cache(epack_store_path: str) -> Dict[str, Dict[str, Any]]:
    global _CACHE, _CACHE_LOADED_FROM
    if _CACHE_LOADED_FROM != epack_store_path:
        _CACHE = _load_cache_from_epacks(epack_store_path)
        _CACHE_LOADED_FROM = epack_store_path
    return _CACHE


def commit_cache_updates(epack_store_path: str, updates: List[Dict[str, Any]]) -> None:
    """Update the in-process cache with newly resolved identifiers."""
    if not epack_store_path or not updates:
        return
    cache = get_cache(epack_store_path)
    for u in updates:
        if not isinstance(u, dict):
            continue
        fp = str(u.get("fingerprint") or "")
        ident = u.get("identifier")
        if fp and ident:
            cache[fp] = dict(u)


def apply_cache(
    citations: List[Dict[str, Any]],
    *,
    epack_store_path: str,
) -> Tuple[List[Dict[str, Any]], List[VerificationEvent]]:
    """Apply cached resolution results to citations.

    Returns patched citations + events (method='cache').
    """
    cache = get_cache(epack_store_path)
    patched: List[Dict[str, Any]] = []
    events: List[VerificationEvent] = []
    for idx, cite in enumerate(citations):
        c = dict(cite or {})
        status_before = str(c.get("verification_status") or "citation_not_retrieved")
        if status_before == "verified_reference":
            patched.append(c)
            continue

        fp = _fingerprint(c)
        hit = cache.get(fp)
        if hit and hit.get("identifier"):
            c["identifier"] = hit.get("identifier")
            c["verification_status"] = "verified_reference"
            events.append(
                VerificationEvent(idx, status_before, "verified_reference", "cache", str(hit.get("identifier")), 1.0, "Resolved from EPACK cache")
            )
        patched.append(c)
    return patched, events


def _title_similarity(a: str, b: str) -> float:
    # Simple token overlap similarity (deterministic, cheap).
    ta = set(re.findall(r"[a-z0-9]+", _norm(a)))
    tb = set(re.findall(r"[a-z0-9]+", _norm(b)))
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _extract_doi(cite: Dict[str, Any]) -> Optional[str]:
    for k in ("identifier", "notes", "title"):
        v = str(cite.get(k) or "")
        m = DOI_RE.search(v)
        if m:
            return m.group(0)
    return None


def _crossref_query(title: str, authors_or_org: str, year: Any, timeout_s: int = 8) -> List[Dict[str, Any]]:
    params = {
        "query.bibliographic": title,
        "rows": 5,
    }
    # Lightly include author/org as additional signal
    if authors_or_org:
        params["query.author"] = authors_or_org
    # Crossref also supports filters; but year matching can be messy, so we post-filter.
    r = requests.get(CROSSREF_WORKS, params=params, timeout=timeout_s, headers={"User-Agent": "BeaconWise/1.0 (citation verification)"})
    r.raise_for_status()
    data = r.json()
    items = (data.get("message") or {}).get("items") or []
    return items


def _best_crossref_match(items: List[Dict[str, Any]], title: str, year: Any) -> Tuple[Optional[Dict[str, Any]], float]:
    best = None
    best_score = 0.0
    y = None
    try:
        y = int(year) if year not in (None, "", "unknown") else None
    except Exception:
        y = None

    for it in items:
        it_title = ""
        if isinstance(it.get("title"), list) and it["title"]:
            it_title = it["title"][0]
        else:
            it_title = str(it.get("title") or "")
        sim = _title_similarity(title, it_title)

        # Year preference: slight boost if year matches
        it_year = None
        issued = (it.get("issued") or {}).get("date-parts")
        if isinstance(issued, list) and issued and isinstance(issued[0], list) and issued[0]:
            try:
                it_year = int(issued[0][0])
            except Exception:
                it_year = None

        if y and it_year:
            if it_year == y:
                sim += 0.15
            elif abs(it_year - y) <= 1:
                sim += 0.05

        # Clamp
        sim = max(0.0, min(1.0, sim))

        if sim > best_score:
            best_score = sim
            best = it

    return best, best_score


def _pubmed_search(title: str, timeout_s: int = 8) -> Optional[str]:
    # Search by title phrase. PubMed query syntax: "title"[Title]
    term = f"\"{title}\"[Title]"
    params = {"db": "pubmed", "term": term, "retmode": "json", "retmax": "1"}
    r = requests.get(PUBMED_ESEARCH, params=params, timeout=timeout_s, headers={"User-Agent": "BeaconWise/1.0 (citation verification)"})
    r.raise_for_status()
    data = r.json()
    ids = ((data.get("esearchresult") or {}).get("idlist")) or []
    return ids[0] if ids else None


def _pubmed_summary(pmid: str, timeout_s: int = 8) -> Dict[str, Any]:
    params = {"db": "pubmed", "id": pmid, "retmode": "json"}
    r = requests.get(PUBMED_ESUMMARY, params=params, timeout=timeout_s, headers={"User-Agent": "BeaconWise/1.0 (citation verification)"})
    r.raise_for_status()
    data = r.json()
    return (data.get("result") or {}).get(pmid) or {}


def verify_citations(
    citations: List[Dict[str, Any]],
    *,
    epack_store_path: Optional[str] = None,
    max_to_verify: int = 5,
    timeout_s: int = 8,
) -> Tuple[List[Dict[str, Any]], List[VerificationEvent], List[Dict[str, Any]]]:
    """
    Attempts to turn unverified citations into verified_reference by resolving DOI (Crossref)
    and/or PMID (PubMed). Returns patched citations + events.

    Deterministic selection rules:
    - If DOI present in fields: mark verified_reference (identifier_only).
    - Else try Crossref: accept if similarity >= 0.60.
    - Else try PubMed: accept if PMID found and title similarity >= 0.60.
    """
    patched: List[Dict[str, Any]] = []
    events: List[VerificationEvent] = []
    cache_updates: List[Dict[str, Any]] = []

    # First, apply cache hits (no network). This also ensures that we don't
    # waste verification budget on already-resolved items.
    if epack_store_path:
        cached_citations, cache_events = apply_cache(citations, epack_store_path=epack_store_path)
        citations = cached_citations
        events.extend(cache_events)

    for idx, cite in enumerate(citations):
        c = dict(cite or {})
        status_before = str(c.get("verification_status") or "citation_not_retrieved")
        status_after = status_before

        # Only attempt on unverified-ish statuses
        if status_before in ("verified_reference",):
            patched.append(c)
            continue

        if idx >= max_to_verify:
            patched.append(c)
            continue

        title = str(c.get("title") or "")
        authors = str(c.get("authors_or_org") or "")
        year = c.get("year")

        try:
            doi = _extract_doi(c)
            if doi:
                c["identifier"] = doi
                status_after = "verified_reference"
                c["verification_status"] = status_after
                events.append(
                    VerificationEvent(idx, status_before, status_after, "identifier_only", doi, 0.95, "DOI detected in citation fields")
                )
                cache_updates.append(
                    {
                        "fingerprint": _fingerprint(c),
                        "identifier": doi,
                        "verification_status": "verified_reference",
                        "method": "identifier_only",
                        "resolved_ts": int(time.time()),
                        "meta_hash": stable_hash({"title": c.get("title"), "authors_or_org": c.get("authors_or_org"), "year": c.get("year")}),
                    }
                )
                patched.append(c)
                continue

            # Crossref resolution
            if title:
                items = _crossref_query(title=title, authors_or_org=authors, year=year, timeout_s=timeout_s)
                best, score = _best_crossref_match(items, title=title, year=year)
                if best and score >= 0.60:
                    doi2 = best.get("DOI")
                    if doi2:
                        c["identifier"] = doi2
                        status_after = "verified_reference"
                        c["verification_status"] = status_after
                        events.append(
                            VerificationEvent(idx, status_before, status_after, "crossref", doi2, float(min(1.0, score)), "Matched via Crossref")
                        )
                        cache_updates.append(
                            {
                                "fingerprint": _fingerprint(c),
                                "identifier": doi2,
                                "verification_status": "verified_reference",
                                "method": "crossref",
                                "resolved_ts": int(time.time()),
                                "meta_hash": stable_hash({"title": c.get("title"), "authors_or_org": c.get("authors_or_org"), "year": c.get("year")}),
                            }
                        )
                        patched.append(c)
                        continue

            # PubMed fallback
            if title:
                pmid = _pubmed_search(title=title, timeout_s=timeout_s)
                if pmid:
                    summ = _pubmed_summary(pmid, timeout_s=timeout_s)
                    pm_title = str(summ.get("title") or "")
                    score = _title_similarity(title, pm_title)
                    if score >= 0.60:
                        ident = f"PMID:{pmid}"
                        c["identifier"] = ident
                        status_after = "verified_reference"
                        c["verification_status"] = status_after
                        events.append(
                            VerificationEvent(idx, status_before, status_after, "pubmed", ident, float(min(1.0, score)), "Matched via PubMed")
                        )
                        cache_updates.append(
                            {
                                "fingerprint": _fingerprint(c),
                                "identifier": ident,
                                "verification_status": "verified_reference",
                                "method": "pubmed",
                                "resolved_ts": int(time.time()),
                                "meta_hash": stable_hash({"title": c.get("title"), "authors_or_org": c.get("authors_or_org"), "year": c.get("year")}),
                            }
                        )
                        patched.append(c)
                        continue

            # No match
            status_after = status_before if status_before != "citation_not_retrieved" else "citation_not_retrieved"
            c["verification_status"] = status_after
            events.append(VerificationEvent(idx, status_before, status_after, "no_match", None, 0.0, "No DOI/PMID match found"))
            patched.append(c)

        except Exception as e:
            # Keep original but record failure
            c["verification_status"] = status_before
            events.append(VerificationEvent(idx, status_before, status_before, "error", None, 0.0, f"Verification error: {type(e).__name__}"))
            patched.append(c)

        # tiny sleep to be polite, still deterministic
        time.sleep(0.05)

    # Update in-process cache so subsequent turns don't re-query network.
    if epack_store_path:
        commit_cache_updates(epack_store_path, cache_updates)

    return patched, events, cache_updates

