---
name: bp-latex
description: "LaTeX standards: latexmk build without warnings, one sentence per line, single .bib, scripted figures. Use when writing or editing LaTeX papers, slides or guides."
---

# bp-latex

Draft defaults: edit to match your conventions.

1. Build with `latexmk -pdf`.
2. The build ends without errors, overfull boxes or undefined references.
3. Write one sentence per line in `.tex` sources (clean diffs).
4. Keep the bibliography in a single `.bib` file with stable cite keys; never format references by hand.
5. Generate figures with scripts as vector PDF; never edit them by hand; keep script and output in the repo.
6. Gitignore aux files (`.aux .log .bbl .out .toc .fls .fdb_latexmk`); commit sources only.

Notes:
- Papers: also load `bp-research`.
