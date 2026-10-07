---
name: skill-authoring
description: Create, change or validate agent skills in the Agent Skills format (SKILL.md, scripts, references). Use whenever a reusable action should become a skill.
---

# skill-authoring

Skills live in `~/.agents/skills/<name>/`. Improve an existing skill before creating a new one.

## Steps

1. Scaffold: `uv run ~/.agents/skills/skill-authoring/scripts/new_skill.py <name> "<what it does. Use when ...>" [--script x.py] [--ref y.md]`. It refuses an existing name. Template and headers: `references/template.md`.
2. Write `SKILL.md`: frontmatter `name` (same as the folder, lowercase, hyphens) and `description` (what it does, when to use it). Body: numbered steps with exact commands, one action per step or bullet (split a line that holds several; simpler models follow single-action lines), under 60 lines. Long detail goes to `references/`, with a line saying when to read it.
3. Add helpers only if a command sequence is fragile. Put them in `scripts/`, executable.
4. Validate: `uv run ~/.agents/skills/skill-authoring/scripts/validate_skills.py --run` (also runs every script with `--help`). Fix every error; read the warnings (description needs "Use when", third person, under 300 chars; body under 60 lines).
5. Confirm discovery: `goose skills list` shows it; agy reads `~/.agents/skills` through `~/.gemini/config/skills.json`; claude does not list it, so name the skill in the task or in the hints ("read its SKILL.md").
6. Test it: run the skill's own command on a small real input and read the output before you call the skill done; delete files the skill does not use (`scripts/lib` if no script imports it).
7. Trigger check: write 3 prompts that must use it and 3 near-misses that must not; the description must separate them.

## Language rules

- Python: run with `uv run`. Declare dependencies in the script's PEP 723 block. Never `pip install` globally.
- Rust: a Cargo project inside the skill, built and run with `cargo`.
- Bash: use only commands already installed. If a needed command is missing, stop and ask the user. Do not install it.
- Each skill is self-contained: no imports from another skill or from outside its folder.
- Refer to files by full path, e.g. `~/.agents/skills/<name>/scripts/x.py`.
- Never put secrets in a skill. Use env vars.
