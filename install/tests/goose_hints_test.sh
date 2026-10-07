#!/usr/bin/env bash
# Smoke test for ~/.config/goose/.goosehints and ~/.agents/skills.
# Usage: goose_hints_test.sh   (static checks only: hints version, .goosehints link, skills listing, scripts run, skills validate)
set -uo pipefail
SK=~/.agents/skills
pass=0; fail=0
ok()  { echo "  PASS $*"; pass=$((pass+1)); }
bad() { echo "  FAIL $*"; fail=$((fail+1)); }

echo "== static checks"
[ -f ~/.agents/VERSION ] && ok "forge hints $(cat ~/.agents/VERSION)" || bad "~/.agents/VERSION missing (run setup.sh)"
cmp -s ~/.agents/AGENTS.md ~/.config/goose/.goosehints && ok ".goosehints matches ~/.agents/AGENTS.md" || bad ".goosehints differs from ~/.agents/AGENTS.md (re-run setup.sh)"
for s in bp-git bp-latex bp-research skill-authoring; do
  goose skills list 2>/dev/null | grep -q "^$s " && ok "skill listed: $s" || bad "skill missing: $s"
done
for s in bp-python bp-rust bp-bash; do
  [ -d "$SK/$s" ] && { goose skills list 2>/dev/null | grep -q "^$s " && ok "skill listed: $s" || bad "skill missing: $s"; }
done
for f in "$SK"/*/scripts/*.py; do
  uv run "$f" --help >/dev/null 2>&1 && ok "runs: ${f#$SK/}" || bad "does not run: ${f#$SK/}"
done
uv run "$SK/skill-authoring/scripts/validate_skills.py" >/dev/null && ok "skills validate" || bad "validate_skills.py reports errors"
grep -rq --exclude=validate_skills.py '\.agent\b' ~/.config/goose/.goosehints "$SK" && bad "stale ~/.agent reference" || ok "no stale ~/.agent reference"
echo "== $pass passed, $fail failed"
[ "$fail" -eq 0 ]
