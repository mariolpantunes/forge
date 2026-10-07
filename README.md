# FORGE

Foundations for Open Research Guidance and Expansion: one hints file and a small set of skills that make claude, goose and agy follow the same working rules.

Current hints version: **h11** (`install/VERSION`).

## What is in the repo

| path | content |
|---|---|
| `install/AGENTS.md` | the hints file (role, workflow, scope, reading and writing, languages, memory); the single source for all three agents |
| `install/moim.md` | the per-turn reminder for goose (plan file, `load_skill`, act in the same turn, write long files in parts) |
| `install/skills/` | 7 skills: `bp-git`, `bp-latex`, `bp-research`, `skill-authoring` (always installed) and `bp-python`, `bp-rust`, `bp-bash` (optional, see `--langs`) |
| `install/tests/` | headless smoke tests for the hints and skills |
| `setup.sh` | installs `install/` into `~/.agents` and wires the agents that are on `PATH` |

## Install

```
./setup.sh --dry-run            # show what would change
./setup.sh                      # install, or update if already installed: copies files that are missing or older than the source, keeps newer installed ones (reported as `keep`)
./setup.sh --force              # replace every installed file with the source (`--update` is an alias of the default)
./setup.sh --langs python,rust  # pick the language skills (all | none | comma list; unknown names warn); an interactive run asks
./setup.sh --status             # what is linked, hints version, differences against install/
./setup.sh --uninstall          # remove the links, restore the saved originals
```

What it does, per agent found on `PATH`:

| agent | hints | skills | extra |
|---|---|---|---|
| claude | link `~/.claude/CLAUDE.md` | read from `~/.agents/skills` (claude does not load them itself; the hints say so) | none |
| goose | a **hard link** at `~/.config/goose/.goosehints` (goose ignores a symlink; a hard link is a regular file with the same inode, so edits in place reach it; an editor that replaces the file (`sed -i`, save-by-rename) or a different filesystem breaks it: setup falls back to a copy, `--status` reports `copy` or `STALE`, re-run setup to relink) | `load_skill` | `GOOSE_MOIM_MESSAGE_FILE` block in `~/.bashrc`, Top Of Mind extension enabled |
| agy | link `~/.gemini/GEMINI.md` | `~/.gemini/config/skills.json` with an absolute path (agy does not expand `~`) | none |

Existing files are saved as `<name>.pre-forge-<timestamp>` and restored by `--uninstall`. Skills and tests under `~/.agents` are kept on uninstall. `$HOME` is honoured, so a test run in a throwaway `HOME` touches nothing else.

## The hints in one paragraph

The plan lives in `./.agents/PLAN.md` and is the memory across restarts; skills are loaded before the first edit (goose: `load_skill`, others: read `SKILL.md`); a missing library is fixed inside the project (venv, PEP 723, cargo), never by skipping a deliverable; long jobs log to a file and are polled; a turn never ends by announcing the next step; files longer than 150 lines are written in parts; the matching `bp-<lang>` skill is loaded before writing code; agentic files go to `./.agents/` (always gitignored) and scratch to `/tmp/<project>`.

## Open items

- After every change to `install/`, re-run `./setup.sh` and `install/tests/goose_hints_test.sh` (it checks the hints version, that `.goosehints` matches, the skills listing and that every script runs).
- `install/skills` holds only `bp-git`, `bp-latex`, `bp-research`, `bp-python`, `bp-rust`, `bp-bash` and `skill-authoring`; personal skills are never shipped; they live only in `~/.agents/skills`.
- `git init`, pre-commit and CI are not set up yet.
