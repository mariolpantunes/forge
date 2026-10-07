---
name: bp-git
description: "Git and pre-commit standards: commits, .gitignore, hooks that mirror CI, coverage floor. Use when working in a git repo or creating .pre-commit-config.yaml."
---

# bp-git

Outside a git repo, skip this skill.

1. Commit once per relevant implementation step or milestone.
2. Write an imperative summary line; the body explains why.
3. Before the first commit, check `.gitignore`: venv, build artefacts, `.env`, LaTeX aux files, `.agents/`.
4. Never bypass hooks with `--no-verify`.
5. Do not push or rewrite published history unless asked.
6. Keep a CI workflow (`.github/workflows/`) that matches the repo's language; its checks are defined by the language skill (`bp-python`, `bp-rust`, `bp-bash`), not here.
7. Pre-commit runs the same checks as CI: read `~/.agents/skills/bp-git/references/precommit.md` before creating or changing `.pre-commit-config.yaml`.
8. Start the hook file from the template in the language skill (`~/.agents/skills/bp-python/templates/precommit/`, `~/.agents/skills/bp-rust/templates/precommit/`).

Notes:
- If CI changes, the hooks change in the same commit.
- No language skill installed for the repo's language: follow the repo's conventions and propose a `bp-<lang>` skill with its CI checks and a hook template.
