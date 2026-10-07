---
name: bp-python
description: "Best practices for Python work: project venv, pyproject, uv scripts, tests, lint, install scope. Use when writing, running or reviewing Python code."
---

# bp-python

Install scope: packages go into the project venv or a script's PEP 723 block. Never `pip install` system-wide, `--user`, or with `sudo`; if a system tool is missing, ask the user.

1. Project: `pyproject.toml` is the single source of truth (`[project]` dependencies, `[dependency-groups]` test, `[tool.*]` config). No `requirements.txt`.
2. Venv: `./venv`, gitignored. Create it with `python3 -m venv venv`, always call `venv/bin/python` explicitly, never activate it or use the PATH interpreter.
3. Sync: `venv/bin/pip install -q --upgrade . --group test` (pip >= 25.1; fallback `".[test]"`). The venv holds runtime dependencies plus coverage only.
4. Tests and coverage run with `PYTHONPATH=src` (or the package dir), so the working tree is tested, not an installed copy.
5. Scripts without a project: PEP 723 block and `uv run script.py`; declare every import (`scikit-learn` for `sklearn`, `pillow` for `PIL`).
6. Lint and types: `ruff`, `basedpyright` (pointed at the venv with `[tool.basedpyright] venvPath` and `venv`), `vulture` run from the system install; their versions must match CI.
7. CI pipeline: `.github/workflows/` runs, in this order, env sync, ruff, basedpyright, vulture, unittest, coverage (`--fail-under`); tool versions are pinned in CI and match the system install.
8. Pre-commit hooks mirror that pipeline step for step; rules for the hook file are in `bp-git`. Templates: `~/.agents/skills/bp-python/templates/precommit/python.yaml`.
9. If an editable install can mask a clean CI install, use `~/.agents/skills/bp-python/templates/precommit/python-venv-sync.yaml` (first hook makes `./venv` match a clean install).
10. Throwaway scripts and scratch outputs go to the OS temp folder (`/tmp/<project>`), agent notes to `./.agents/` (gitignored), never into the project tree.

Notes:
- `pip install .` also installs the package; `PYTHONPATH` makes the working tree shadow it.
- Pin dependency versions from the registry's latest release, not from memory.
- Seed every random generator that feeds a reported number; record the library versions.
