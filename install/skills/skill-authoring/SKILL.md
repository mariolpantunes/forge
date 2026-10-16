---
name: skill-authoring
description: Create, change, merge or validate agent skills in the Agent Skills format (SKILL.md, scripts, references). Use whenever a reusable action should become a skill or skills overlap.
---

# skill-authoring

Skills live in `~/.agents/skills/<name>/`. Command: `uv run ~/.agents/skills/skill-authoring/scripts/skill.py` (below: `skill.py`).

## Pick: extend or new

1. Run `skill.py find "<what the skill does, in a few English words>"`.
2. `verdict: extend <name>`: improve that skill with the Write steps.
3. `verdict: new`: scaffold with `uv run ~/.agents/skills/skill-authoring/scripts/new_skill.py <name> "<what it does. Use when ...>" [--script x.py] [--ref y.md]`. It refuses an existing name. Template: `references/template.md`.

## Write

1. Read the skill's state: `skill.py show <name>` prints a `tree-sha`.
2. Write each file with `skill.py put <name> <relpath> --base <tree-sha> [--from FILE]` (content on stdin without `--from`). Never write into `~/.agents/skills` by hand.
3. `put` locks the skill, writes atomically and restores the old file if the result breaks the format or is not generic.
4. `conflict:` means another agent changed the skill: run `show`, read the new files, merge your change into them, `put` again.
5. Put scripts and references before the `SKILL.md` that mentions them.
6. `SKILL.md`: frontmatter `name` (same as the folder) and `description` (what it does, when to use it, third person, under 300 chars).
7. Body: numbered steps with exact commands, one action per step, under 60 lines. Long detail goes to `references/` with a line saying when to read it.
8. Add a script only if a command sequence is fragile. Scripts go in `scripts/`, executable.

## Generic and reusable

1. A skill holds no personal path, user name, e-mail, host, IP or secret. Use `~`, relative paths and env vars.
2. A skill is self-contained: no import from another skill.
3. A skill states a method, not one project's data: move project facts to the project's `.agents/` notes.
4. Run `skill.py check <name>`; fix every error.

## Merge overlapping skills

1. `skill.py merge <keep> <drop>` is a dry run: it lists copies, conflicts and the body of `<drop>`.
2. Add `--apply`: `<drop>` moves to `~/.agents/skill-archive/`, its files join `<keep>`, conflicts go to `references/merged-from-<drop>/`.
3. Fold `references/<drop>.md` into `<keep>/SKILL.md` and widen its description.
4. Fix every `stale pointer` the merge prints.
5. Run `skill.py check <keep>`.

## Validate and test

1. `uv run ~/.agents/skills/skill-authoring/scripts/validate_skills.py --run` runs every script with `--help`; fix errors, read warnings.
2. Run the skill's own command on a small real input and read the output.
3. Write 3 prompts that must trigger it and 3 near-misses; the description must separate them.
4. goose lists it with `goose skills list`; agy reads `~/.agents/skills` through `~/.gemini/config/skills.json`.
5. claude lists only skills it knows: name the skill in the task.

## Language rules

- Python: run with `uv run`, dependencies in the PEP 723 block, never `pip install` globally.
- Rust: a Cargo project inside the skill, built with `cargo`.
- Bash: use only installed commands; if one is missing, ask the user.
- Refer to files by full path, e.g. `~/.agents/skills/<name>/scripts/x.py`.
