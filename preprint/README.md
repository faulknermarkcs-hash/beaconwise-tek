[README.md](https://github.com/user-attachments/files/25276627/README.md)
# BeaconWise Academic Preprint — v1.9.0

**Title:** Deterministic Governance Kernels for Auditable AI Systems  
**Author:** Mark Randall Havens, Transparency Ecosphere Project  
**Status:** Preprint — arXiv submission candidate, not peer reviewed  
**Date:** February 2026

## Files

| File | Description |
|------|-------------|
| `beaconwise_preprint_v1.9.0.pdf` | Publication-ready PDF (US Letter, 12pt Times, academic format) |
| `beaconwise_preprint_v1.9.0.docx` | Editable Word document (same content, heading styles, tables) |
| `pdf_generator.py` | ReportLab Platypus generator — requires `reportlab` |
| `docx_generator.js` | docx-js generator — requires `npm install docx` |

## Regenerating

```bash
# PDF
pip install reportlab --break-system-packages
python3 pdf_generator.py

# DOCX
npm install -g docx
node docx_generator.js
```

## Paper Sections

1. Introduction — governance kernel vs. policy filter distinction
2. Background & Related Work — regulatory context, existing approaches
3. Governance Kernel Architecture — 8 invariants, EPACK, DRP, validator governance
4. Governance Threat Model — hallucination propagation, hidden persuasion, silent drift, capture
5. Comparison to Existing Approaches — audit independence, enforcement vs. evaluation
6. Implementation: BeaconWise v1.9.0 — component table, verification properties, **V9 Resilience Control Plane**
7. Discussion — kernel as infrastructure, determinism scope, limitations, regulatory mapping
8. Conclusion — 355 tests, 9 normative specs, Apache 2.0

## Key Figures / Tables

- **Figure 1:** Architecture diagram — kernel stack, routing engine, EPACK chain
- **Table 1:** Comparison to Constitutional AI, Guardrails, HELM, Observability
- **Table 2:** Component status (v1.9.0)
- **Table 3:** Threat model — 5 threat classes
- **Table 4:** Regulatory infrastructure mapping (EU AI Act, NIST AI RMF, ISO/IEC 42001)
- **Table 5:** V9 Resilience Control Plane — 9 components (NEW in this version)
- **Figure 2:** Package structure (src/ecosphere/)

## Citation

```
Havens, M. R. (2026). Deterministic governance kernels for auditable AI systems.
Preprint. Transparency Ecosphere Project. 
https://github.com/beaconwise-tek/beaconwise
```
