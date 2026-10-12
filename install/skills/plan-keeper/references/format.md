# plan-keeper formats

Read when a router row, a notes file or a limit is unclear.

## Layout

- Project: `.agents/PLAN.md` (hot, target 4k tokens, cap 8k), `.agents/notes/` (cold, kept), `.agents/plan-archive/` (verbatim copies, deleted after 30 days).
- Home: `~/.agents/plans/PLAN.md` (router), `~/.agents/plans/<id>/PLAN.md` (same layout as a project), `~/.agents/plans/.archive/` (merged and idle concepts, deleted after 30 days).
- Folder names are random 8-hex ids: the name carries no meaning, the description in the router does.

## Router row

`- description | plan path | touched: YYYY-MM-DD`

- One line (at most 200 characters) saying what the work is, with its key nouns; it is the only thing `find` and `prune` read.
- Current holds open concepts; Done holds archived ones (`archived: date`) and broken links (`link broken: date`).
- The path is `~/.agents/plans/<id>/PLAN.md` or the plan of a project (`~/git/<repo>/.agents/PLAN.md`; the project folder name also counts as description words).
- `find` counts the words shared by the task and the description: 3 shared words, or 2 when the task has at most 4 words, continue that concept; less is a new one.
- `prune` merges two concepts when their descriptions share at least 3 words and 60 percent of the shorter one (or 2 words and 90 percent).

## Limits

| item | value |
|---|---|
| cap (compact above) | 8000 tokens, 3.3 bytes per token |
| target after compaction | 4000 tokens |
| entry | 3 lines, 400 bytes; the rest goes to `notes/<date>-<hash>.md` |
| Tried ledger | 40 entries in the plan, older ones in `notes/tried.md` |
| idle concept | 14 days without activity and no Next items |
| expiry | 30 days (plan-archive copies, `.archive` folders) |

## Exit codes

- `replace`: 0 done, 1 refused (missing section or over the cap), 3 the plan changed since `archive`.
- `verify`: 1 on a missing section or over the cap; missing paths only warn.
