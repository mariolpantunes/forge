#!/usr/bin/env bash
# FORGE setup: copy ./install into ~/.agents, then set up only the agents found on PATH (claude, goose, agy):
# link the hints; claude: ~/.claude/skills -> ~/.agents/skills; goose: GOOSE_MOIM_MESSAGE_FILE in config.yaml + tom extension enabled; agy: skills.json.
# Runs on Linux and macOS (bash 3.2, BSD tools).
# Usage: setup.sh [--install|--update] [--uninstall] [--status] [-n|--dry-run] [-f|--force] [--langs python,rust,bash|all|none]
#   default: install; re-running it is an update: a file is copied when missing or older than the source, a newer
#   installed file is kept and reported; --force replaces every file. --langs picks the language skills (bp-python, bp-rust, bp-bash) to install (bp-git, bp-latex and bp-research are always installed); without it,
#   an interactive run asks and a non-interactive run installs all.
# $HOME is honoured, so a test run can use a throwaway HOME.
set -euo pipefail

SRC=$(cd "$(dirname "$0")" && pwd)/install
A=$HOME/.agents
HINTS=$A/AGENTS.md
OLDHINTS=$A/hints/AGENTS.md
NAMES=(claude goose agy)
LINKS=("$HOME/.claude/CLAUDE.md" "$HOME/.config/goose/.goosehints" "$HOME/.gemini/GEMINI.md")
SKJSON=$HOME/.gemini/config/skills.json
CSK=$HOME/.claude/skills
GCONF=${XDG_CONFIG_HOME:-$HOME/.config}/goose/config.yaml
case ${SHELL##*/} in zsh) RC=$HOME/.zshrc ;; *) RC=$HOME/.bashrc ;; esac
# macOS: the goose desktop app ships its own CLI inside the bundle; it counts as goose installed.
GOOSE_APP=/Applications/Goose.app/Contents/Resources/bin/goose
BEGIN='# >>> forge >>>'; END='# <<< forge <<<'
mode=install; dry=0; force=0; LANGS=""
while [ $# -gt 0 ]; do
  case $1 in
    --install|--update) mode=install ;; --uninstall) mode=uninstall ;; --status) mode=status ;;
    -n|--dry-run) dry=1 ;;
    -f|--force) force=1 ;;
    --langs) shift; LANGS=${1:-} ;;
    *) sed -n 2,6p "$0" | cut -c3-; exit 2 ;;
  esac
  shift
done

run() { echo "+ $*"; [ "$dry" -eq 1 ] || "$@"; }
have() { command -v "$1" >/dev/null 2>&1 || { [ "$1" = goose ] && [ -x "$GOOSE_APP" ]; }; }
ts() { date +%F-%H%M%S; }
# goose ignores a symlinked .goosehints (eval T0, 2026-10-03), so it gets a hard link (a regular file, same inode: edits to the hints reach it);
# if the hard link is impossible (other filesystem) it gets an identical copy. claude and agy get symlinks.
iscopy() { [ "$1" = "$HOME/.config/goose/.goosehints" ]; }
mine() { if iscopy "$1"; then [ -f "$1" ] && [ ! -L "$1" ] && [ "$1" -ef "$HINTS" ]; else [ -L "$1" ] && [ "$(readlink "$1")" = "$HINTS" ]; fi; }
samecopy() { iscopy "$1" && [ -f "$1" ] && [ ! -L "$1" ] && cmp -s "$1" "$HINTS"; }
ours() { mine "$1" || samecopy "$1"; }
# files SRC: every file under a file or folder, NUL separated, without __pycache__.
files() { find "$1" -type f ! -path '*__pycache__*' -print0; }
# cpu SRC DESTDIR: copy each file that is missing or older than the source (GNU cp -u; macOS cp has no -u).
# cp onto an existing file rewrites it in place, so the .goosehints hard link survives an update.
cpu() {
  local src=$1 dst=$2 f r
  while IFS= read -r -d '' f; do
    r=${f#"$(dirname "$src")"/}
    if [ ! -e "$dst/$r" ] || [ "$f" -nt "$dst/$r" ]; then mkdir -p "$(dirname "$dst/$r")" && cp -p "$f" "$dst/$r"; fi
  done < <(files "$src")
}
# put SRC DESTDIR: copy a file or folder into DESTDIR; update mode (missing or older only), --force replaces all.
# Installed files that differ but are newer than the source are kept and reported.
put() {
  local src=$1 dst=$2 f r
  if [ "$force" -eq 0 ]; then
    while IFS= read -r -d '' f; do
      r=${f#"$(dirname "$src")"/}
      [ -f "$dst/$r" ] && [ "$dst/$r" -nt "$f" ] && ! cmp -s "$f" "$dst/$r" && echo "keep $dst/$r (newer than source; --force replaces)"
    done < <(files "$src")
    run cpu "$src" "$dst"
  else run cp -a "$src" "$dst/"; fi
}

# claude lists skills only from ~/.claude/skills: make it a link to $A/skills. Skills already there are merged into $A/skills
# first (an existing name in $A/skills wins), then the old folder or link is saved as skills.pre-forge-<ts>; --uninstall restores it.
claude_skills() {
  local d n
  if [ -L "$CSK" ] && [ "$(readlink "$CSK")" = "$A/skills" ]; then echo "ok   $CSK"; return 0; fi
  run mkdir -p "$(dirname "$CSK")"
  if [ -e "$CSK" ] || [ -L "$CSK" ]; then
    if [ -d "$CSK" ]; then
      for d in "$CSK"/*/; do
        [ -d "$d" ] || continue
        n=$(basename "$d")
        if [ -e "$A/skills/$n" ]; then echo "keep $A/skills/$n (also in $CSK; the saved folder keeps the other copy)"
        else run cp -aL "${d%/}" "$A/skills/"; fi
      done
    fi
    run mv "$CSK" "$CSK.pre-forge-$(ts)"
  fi
  run ln -s "$A/skills" "$CSK"
}

# remove the forge block that older versions appended to the shell rc (backup first)
drop_rc_block() {
  grep -qs "^$BEGIN" "$RC" || return 0
  run cp -a "$RC" "$RC.pre-forge-$(ts)"
  echo "+ remove forge block from $RC"
  # BSD sed -i needs a suffix argument; filter through a temp file and write back in place instead
  [ "$dry" -eq 1 ] || { sed "/^$BEGIN/,/^$END/d" "$RC" >"$RC.new" && cat "$RC.new" >"$RC" && rm "$RC.new"; }
}

# the Top Of Mind reminder file is set in goose's config.yaml (goose 1.54 reads GOOSE_MOIM_MESSAGE_FILE there, tested 2026-10-12):
# the desktop app does not source the shell rc. Without a config.yaml the old rc export is the fallback.
goose_tom() {
  local cur
  if [ -f "$GCONF" ]; then
    cur=$(sed -n 's/^GOOSE_MOIM_MESSAGE_FILE:[[:space:]]*//p' "$GCONF" | tr -d "\"' " | head -1)
    cur=${cur/#\~/$HOME}
    if [ "$cur" = "$A/moim.md" ]; then echo "ok   GOOSE_MOIM_MESSAGE_FILE in $GCONF"
    elif [ -z "$cur" ]; then
      run cp -a "$GCONF" "$GCONF.pre-forge-$(ts)"
      echo "+ set GOOSE_MOIM_MESSAGE_FILE in $GCONF"
      [ "$dry" -eq 1 ] || { { cat "$GCONF"; [ -z "$(tail -c1 "$GCONF")" ] || echo; echo "GOOSE_MOIM_MESSAGE_FILE: $A/moim.md"; } >"$GCONF.new" && mv "$GCONF.new" "$GCONF"; }
    else echo "warn: $GCONF sets GOOSE_MOIM_MESSAGE_FILE to $cur; left alone"; fi
    drop_rc_block
  elif ! grep -qs 'GOOSE_MOIM_MESSAGE_FILE=' "$RC"; then
    [ -f "$RC" ] && run cp -a "$RC" "$RC.pre-forge-$(ts)"
    echo "+ append forge block to $RC (fallback: no $GCONF)"
    [ "$dry" -eq 1 ] || printf '\n%s\nexport GOOSE_MOIM_MESSAGE_FILE="$HOME/.agents/moim.md"\n%s\n' "$BEGIN" "$END" >>"$RC"
  elif grep -q 'GOOSE_MOIM_MESSAGE_FILE=.*\.agents/moim\.md' "$RC"; then echo "ok   tom variable in $RC"
  else echo "warn: $RC sets GOOSE_MOIM_MESSAGE_FILE to something else; left alone"; fi
  [ -f "$GCONF" ] || { echo "warn: $GCONF missing, run goose once, then re-run setup"; return 0; }
  if awk '/^  tom:/{f=1;next} f&&/^  [a-z_]+:/{f=0} f&&/enabled: true/{ok=1} END{exit !ok}' "$GCONF"; then echo "ok   tom extension enabled"
  elif grep -q '^  tom:' "$GCONF"; then
    run cp -a "$GCONF" "$GCONF.pre-forge-$(ts)"
    echo "+ enable tom in $GCONF"
    [ "$dry" -eq 1 ] || { awk '/^  tom:/{f=1} f&&/enabled:/{sub(/enabled:.*/,"enabled: true");f=0} {print}' "$GCONF" >"$GCONF.new" && mv "$GCONF.new" "$GCONF"; }
  else echo "warn: no tom block in $GCONF; enable Top Of Mind with 'goose configure'"; fi
}

# best-practice skills per language: ./install/skills/bp-<lang>; --langs python,rust,bash | all | none
# bp-git, bp-latex and bp-research are standards, not languages: always installed, never offered by --langs.
NONLANG=" git latex research "
is_lang() { case "$NONLANG" in *" $1 "*) false ;; *) true ;; esac; }
want_lang() { [ "$LANGS" = all ] || case ",$LANGS," in *",$1,"*) true ;; *) false ;; esac; }
choose_langs() {
  local avail l; avail=$(ls -1 "$SRC"/skills | sed -n 's/^bp-//p' | while read -r l; do is_lang "$l" && echo "$l"; done | paste -sd' ' -)
  if [ -z "$LANGS" ] && [ -t 0 ] && [ "$dry" -eq 0 ]; then
    read -r -p "Install best-practice skills for [$avail] (comma list, all, none) [all]: " LANGS || true
  fi
  LANGS=${LANGS:-all}
  for l in ${LANGS//,/ }; do
    case $l in all|none) ;; *) [ -d "$SRC/skills/bp-$l" ] || echo "warn: no best-practice skill for '$l' (available: $avail)" ;; esac
  done
}

install_all() {
  run mkdir -p "$A/skills"
  choose_langs
  for x in AGENTS.md tests VERSION; do put "$SRC/$x" "$A"; done
  for sk in "$SRC"/skills/*/; do
    n=$(basename "$sk")
    case $n in bp-*) ! is_lang "${n#bp-}" || want_lang "${n#bp-}" || { echo "skip skill $n (not selected)"; continue; } ;; esac
    put "${sk%/}" "$A/skills"
  done
  for n in "${!NAMES[@]}"; do
    c=${NAMES[$n]}; t=${LINKS[$n]}
    have "$c" || { echo "skip $c (not installed)"; continue; }
    # migration: hints used to live in $A/hints/AGENTS.md; drop links to the old file
    if { [ -L "$t" ] && [ "$(readlink "$t")" = "$OLDHINTS" ]; } || { [ -f "$t" ] && [ ! -L "$t" ] && [ "$t" -ef "$OLDHINTS" ]; }; then run rm "$t"; fi
    if mine "$t"; then echo "ok   $t"; else
      run mkdir -p "$(dirname "$t")"
      if [ -e "$t" ] || [ -L "$t" ]; then
        if samecopy "$t"; then run rm "$t"; else run mv "$t" "$t.pre-forge-$(ts)"; fi
      fi
      if iscopy "$t"; then
        echo "+ ln $HINTS $t (hard link; copy if it fails)"
        [ "$dry" -eq 1 ] || ln "$HINTS" "$t" 2>/dev/null || { echo "warn: hard link failed (other filesystem?), copied instead"; cp "$HINTS" "$t"; }
      else run ln -s "$HINTS" "$t"; fi
    fi
    case $c in
      claude) claude_skills ;;
      goose) put "$SRC/moim.md" "$A"; goose_tom ;;
      agy) run mkdir -p "$(dirname "$SKJSON")"; echo "+ write $SKJSON (absolute path: agy does not expand ~)"
         [ "$dry" -eq 1 ] || printf '{\n  "entries": [ { "path": "%s" } ]\n}\n' "$A/skills" >"$SKJSON" ;;
    esac
  done
  [ ! -d "$A/hints" ] || run rm -rf "$A/hints"
}

uninstall_all() {
  for t in "${LINKS[@]}"; do
    ours "$t" || { echo "skip $t (not a forge link)"; continue; }
    run rm "$t"
    b=$(ls -1 "$t".pre-forge-* 2>/dev/null | tail -1 || true)
    [ -z "$b" ] || run mv "$b" "$t"
  done
  if [ -L "$CSK" ] && [ "$(readlink "$CSK")" = "$A/skills" ]; then
    run rm "$CSK"
    b=""; for f in "$CSK".pre-forge-*; do if [ -e "$f" ] || [ -L "$f" ]; then b=$f; fi; done
    [ -z "$b" ] || run mv "$b" "$CSK"
  else echo "skip $CSK (not a forge link)"; fi
  drop_rc_block
  if grep -qs "^GOOSE_MOIM_MESSAGE_FILE:.*moim\.md" "$GCONF"; then
    run cp -a "$GCONF" "$GCONF.pre-forge-$(ts)"
    echo "+ remove GOOSE_MOIM_MESSAGE_FILE from $GCONF"
    [ "$dry" -eq 1 ] || { grep -v '^GOOSE_MOIM_MESSAGE_FILE:.*moim\.md' "$GCONF" >"$GCONF.new"; mv "$GCONF.new" "$GCONF"; }
  fi
  run rm -rf "$A/hints"
  run rm -f "$A/VERSION"
  run rm -f "$A/moim.md"
  ! grep -qs "\"$A/skills\"" "$SKJSON" || run rm -f "$SKJSON"
  echo "kept $A/skills (merged claude skills included) and $A/tests (your data) and the goose tom setting"
}

status_all() {
  for n in "${!NAMES[@]}"; do
    t=${LINKS[$n]}; have "${NAMES[$n]}" || echo "absent  ${NAMES[$n]} (not installed)"
    if mine "$t"; then echo "linked  $t"; elif samecopy "$t"; then echo "copy    $t (identical but not a hard link: later edits will not reach it; re-run setup.sh)"; elif iscopy "$t" && [ -f "$t" ]; then echo "STALE   $t (differs from $HINTS; re-run setup.sh)"; elif [ -e "$t" ]; then echo "OTHER   $t (not a forge link)"; else echo "missing $t"; fi
  done
  if [ -L "$CSK" ] && [ "$(readlink "$CSK")" = "$A/skills" ]; then echo "linked  $CSK"; elif [ -e "$CSK" ] || [ -L "$CSK" ]; then echo "OTHER   $CSK (not a forge link; re-run setup.sh to merge and link)"; else echo "missing $CSK"; fi
  [ -f "$HINTS" ] && echo "present $HINTS (forge hints $(cat "$A/VERSION" 2>/dev/null || echo '?'), source $(cat "$SRC/VERSION"))" || echo "missing $HINTS"
  diff -rq "$SRC/skills" "$A/skills" 2>/dev/null | grep -v __pycache__ | grep -v 'Only in .*: bp-' | grep -v 'Only in .*/skills: synced$' | head -10 || true
}

case $mode in install) install_all ;; uninstall) uninstall_all ;; status) status_all ;; esac
