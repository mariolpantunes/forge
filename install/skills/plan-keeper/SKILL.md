---
name: plan-keeper
description: "Write, route and compact PLAN.md files: pick the plan of a task (home folder concept router), add entries, keep a plan under 8k tokens, prune old home plans. Use at the start of every task, whenever a plan is written, and when a plan is over 8k tokens."
---

# plan-keeper

Command: `uv run ~/.agents/skills/plan-keeper/scripts/plan.py` (below: `plan.py`). Details: `references/format.md`.

## Pick the plan

1. In a project folder the plan is `./.agents/PLAN.md`.
2. In the home folder run `plan.py prune`, then `plan.py find "<task in a few English words>"`.
3. `verdict: continue`: use the printed plan.
4. `verdict: new`: run `plan.py init --desc "<one line: what the work is, with its key nouns>"` and use the printed plan path.
5. A chat that writes no files needs no plan.
6. A task that changes files in another project folder: write its entry to `<folder>/.agents/PLAN.md` (`--plan <folder>`).

## Write

1. Add an entry: `plan.py add [--plan P] <Done|Current|Next|Aborted|Key> "<text>"`.
2. The home router holds one line per concept; `find` matches the task against that line, so reword it when the work shifts (`add --desc "<new line>"`).
3. One entry: what was done, output paths, the rerun command, the decision, the next step.
4. Text over 3 lines goes to `notes/` by itself; the entry keeps a link.
5. A subagent never runs `add`; the parent records its result.
6. Before retrying an approach, grep the plan and `.agents/notes/` (`notes/tried.md` too) for it.
7. At the end of the task run `plan.py check [--plan P]`.
8. If any output says OVER CAP, compact (below) before continuing.

## Compact (plan over 8k tokens)

1. `plan.py archive --plan P`: a verbatim copy in `plan-archive/`; note the printed hash.
2. Read the plan and write a draft to `/tmp/<project>/plan-draft.md`.
3. Draft rules: sections Done, Current, Next, Aborted, Key knowledge; at most 3 lines per entry; target 4k tokens.
4. Keep every output path and rerun command that is still live; keep open Next items and the Current state verbatim.
5. Put each tested idea as one line in `### Tried` under Key knowledge: idea, result, evidence path (at most 40; older ones go to `notes/tried.md`).
6. Move run lists, result tables and long findings to `notes/<topic>.md` and link them.
7. `plan.py verify --plan P --new <draft>`: restore each missing path or command, or drop it on purpose.
8. `plan.py replace --plan P --new <draft> --expect <hash>`.
9. If replace says the plan changed, run `archive` again and merge the new entries into the draft.
10. Compacting the home router: only rows of closed or broken concepts go; `plan.py prune` does it.

## Home plans

- `plan.py prune` adopts old dated folders, merges concepts whose descriptions overlap, archives concepts idle for 14 days without Next items, and deletes archive items after 30 days.
- It runs without asking; merged and archived folders stay in `~/.agents/plans/.archive/` for 30 days.
- Plans of other projects are linked from the router, never moved.

Notes:
- The first `add` in a git project also writes `.agents/` to its `.gitignore`: say so in the final report.
- Plans, descriptions and notes are English even when the chat is not: translate the task before `find` and `init`.
- Write nothing to `~/.agents/PLAN.md`; the home plan is `~/.agents/plans/PLAN.md`.
