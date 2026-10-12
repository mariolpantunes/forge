#!/usr/bin/env bash
# Smoke test for ~/.config/goose/.goosehints and ~/.agents/skills.
# Usage: goose_hints_test.sh   (static checks only: hints version, .goosehints link, skills listing, scripts run, skills validate)
set -uo pipefail
SK=~/.agents/skills
# the goose desktop app on macOS ships its CLI inside the bundle; use it when goose is not on PATH
GOOSE=$(command -v goose || echo /Applications/Goose.app/Contents/Resources/bin/goose)
# list once: grep -q on a live pipe stops early, goose gets SIGPIPE and pipefail reports a listed skill as missing
LISTED=$("$GOOSE" skills list 2>/dev/null)
pass=0; fail=0
ok()  { echo "  PASS $*"; pass=$((pass+1)); }
bad() { echo "  FAIL $*"; fail=$((fail+1)); }

echo "== static checks"
[ -f ~/.agents/VERSION ] && ok "forge hints $(cat ~/.agents/VERSION)" || bad "~/.agents/VERSION missing (run setup.sh)"
cmp -s ~/.agents/AGENTS.md ~/.config/goose/.goosehints && ok ".goosehints matches ~/.agents/AGENTS.md" || bad ".goosehints differs from ~/.agents/AGENTS.md (re-run setup.sh)"
for s in bp-git bp-latex bp-research skill-authoring; do
  printf '%s\n' "$LISTED" | grep -q "^$s " && ok "skill listed: $s" || bad "skill missing: $s"
done
for s in bp-python bp-rust bp-bash; do
  [ -d "$SK/$s" ] && { printf '%s\n' "$LISTED" | grep -q "^$s " && ok "skill listed: $s" || bad "skill missing: $s"; }
done
for f in "$SK"/*/scripts/*.py; do
  uv run "$f" --help >/dev/null 2>&1 && ok "runs: ${f#$SK/}" || bad "does not run: ${f#$SK/}"
done
uv run "$SK/skill-authoring/scripts/validate_skills.py" >/dev/null && ok "skills validate" || bad "validate_skills.py reports errors"
# every skill the hints or the reminder name must be installed (issue #3: moim.md once named a skill that is not shipped)
missing=""
for n in $(grep -ohE 'load_skill [a-z][a-z0-9-]+|\bbp-[a-z]+\b' ~/.agents/AGENTS.md ~/.agents/moim.md 2>/dev/null | sed 's/^load_skill //' | grep -vx tool | sort -u); do
  [ -d "$SK/$n" ] || missing="$missing $n"
done
[ -z "$missing" ] && ok "hints and reminder name only installed skills" || bad "hints or reminder name skills that are not installed:$missing"
grep -rq --exclude=validate_skills.py '\.agent\b' ~/.config/goose/.goosehints "$SK" && bad "stale ~/.agent reference" || ok "no stale ~/.agent reference"
echo "== $pass passed, $fail failed"
[ "$fail" -eq 0 ]
