---
name: bp-research
description: "Reproducibility standards for research papers with code: scripted numbers, seeds, read-only data, code and paper in sync. Use when working on a paper with code, data and results."
---

# bp-research

Draft defaults: edit to match your conventions.

1. Produce every number, table and figure in the paper with a script in the repo; never copy results by hand.
2. Fix random seeds, and record the environment and library versions for each result.
3. Keep raw data read-only; derived data lives elsewhere and is reproducible from scripts.
4. When code or results change, update the paper section and the figures in the same commit.
5. Log decisions and dead ends in `./.agents/PLAN.md` and memory (`#decision`, `#notes`).

Notes:
- LaTeX sources: also load `bp-latex`.
- Python code: also load `bp-python`; commits and hooks: `bp-git`.
