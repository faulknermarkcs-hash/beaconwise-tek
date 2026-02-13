# Regulator-Readiness Lint Report

This report checks documentation for issues that commonly reduce regulator/enterprise confidence: broken internal links, duplicated files, contradictory claims, and missing required sections.

## Summary
- Markdown files scanned: **18**
- Broken internal links: **0**
- Exact duplicate markdown files: **0**
- Potential contradictory compliance claims: **0**
- Key docs missing a 'Non-Goals' section: **0** ✓

## Broken Internal Links
- None found.

## Exact Duplicate Markdown Files
- None found.

## Potential Contradictory Compliance Claims
- None found.

## Missing 'Non-Goals' Section (Key Docs)
- None. All key documents carry explicit scope boundaries.

## Previously Open Items (Now Resolved)

| Issue | Severity | Resolution |
|-------|----------|------------|
| `FAQ.md` missing Non-Goals section | LOW | Non-Goals section added |
| Missing `docs/INDEX.md` reading order | RECOMMENDED | `docs/INDEX.md` created |
| `enterprise/PILOT_PACKAGE` was a stub | MODERATE | Full deployment guide written |
| `REGULATOR_BRIEFING.md` stale test count | LOW | Updated to 355 passing / 36 files |

## Notes
- `docs/CONSTITUTION` (no extension) is a machine-readable schema file distinct from `CONSTITUTION.md`. Recommend noting this distinction in INDEX.md if it causes confusion during third-party audit. (Optional.)
- All compliance claims are scoped as infrastructure capabilities, not compliance certifications. Deployer responsibility language is consistent across all documents.
