# FORGE

Foundations for Open Research Guidance and Expansion: one hints file and a small set of skills that make claude, goose and agy follow the same working rules.

Current hints version: **h14** (`install/VERSION`).

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
| claude | link `~/.claude/CLAUDE.md` | `~/.claude/skills` becomes a symlink to `~/.agents/skills` so claude lists the skills itself; skills already in `~/.claude/skills` are merged into `~/.agents/skills` first (an existing name there wins) and the old folder is saved as `skills.pre-forge-<timestamp>` | none |
| goose | a **hard link** at `~/.config/goose/.goosehints` (goose ignores a symlink; a hard link is a regular file with the same inode, so edits in place reach it; an editor that replaces the file (`sed -i`, save-by-rename) or a different filesystem breaks it: setup falls back to a copy, `--status` reports `copy` or `STALE`, re-run setup to relink) | `load_skill` | `GOOSE_MOIM_MESSAGE_FILE: ~/.agents/moim.md` (absolute path) in goose's `config.yaml`, so the desktop app gets it too, Top Of Mind extension enabled; a forge block that an older setup appended to `~/.zshrc` or `~/.bashrc` is removed (backup saved); without a `config.yaml` the rc export is the fallback |
| agy | link `~/.gemini/GEMINI.md` | `~/.gemini/config/skills.json` with an absolute path (agy does not expand `~`) | none |

## macOS and the goose desktop app

- `setup.sh` runs on the stock bash 3.2 and BSD tools (no `cp -u`, `sed -i` or stdin `paste`).
- goose counts as installed when `goose` is on `PATH` or the desktop app is in `/Applications` (its CLI is `Goose.app/Contents/Resources/bin/goose`, also used by the test).
- The desktop app starts a chat in the home folder unless a project folder is picked, so the hints send that plan to `~/.agents/plans/<date>-<topic>/PLAN.md` instead of `~/.agents/PLAN.md`.
- With an ACP provider (`claude-acp`), goose forwards only the latest user message and `type: mcp` extensions: `.goosehints`, the Top Of Mind reminder and platform extensions (`load_skill`, developer, todo) never reach the agent. Claude still gets the hints through `~/.claude/CLAUDE.md`, because the adapter loads the user settings, and reads the skills from `~/.agents/skills` as the hints say.

The Claude app's account-synced skills (`~/.claude/skills/synced/`) land in `~/.agents/skills/synced/` on purpose: goose finds them there (checked: 13 skills listed), so every agent can use them. `validate_skills.py` and `--status` treat `synced/` as a container, not an error. agy scans one level only, so it probably does not list them (not tested).

Existing files and folders are saved as `<name>.pre-forge-<timestamp>` and restored by `--uninstall` (which also removes the `~/.claude/skills` link). Skills and tests under `~/.agents` are kept on uninstall. `$HOME` is honoured, so a test run in a throwaway `HOME` touches nothing else.

## The hints in one paragraph

The plan lives in `./.agents/PLAN.md` and is the memory across restarts; skills are loaded before the first edit (goose: `load_skill`, others: read `SKILL.md`); a missing library is fixed inside the project (venv, PEP 723, cargo), never by skipping a deliverable; long jobs log to a file and are polled; a turn never ends by announcing the next step; files longer than 150 lines are written in parts; the matching `bp-<lang>` skill is loaded before writing code; agentic files go to `./.agents/` (always gitignored) and scratch to `/tmp/<project>`.

## Open items

- After every change to `install/`, re-run `./setup.sh` and `install/tests/goose_hints_test.sh` (it checks the hints version, that `.goosehints` matches, the skills listing and that every script runs).
- `install/skills` holds only `bp-git`, `bp-latex`, `bp-research`, `bp-python`, `bp-rust`, `bp-bash` and `skill-authoring`; personal skills are never shipped; they live only in `~/.agents/skills`.
- Pre-commit and CI are not set up yet.
