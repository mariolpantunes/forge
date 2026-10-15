---
name: bp-bash
description: "Best practices for Bash scripts: strict mode, quoting, temp files, installed commands only. Use when writing or reviewing shell scripts."
---

# bp-bash

Install scope: use only commands that are already installed (`command -v tool`). If one is missing, stop and ask the user; never `sudo`, `apt` or `pip` from a script.

1. Header: `#!/usr/bin/env bash` and `set -euo pipefail`.
2. Quote every expansion (`"$var"`, `"${arr[@]}"`), use arrays for argument lists and `[[ ... ]]` for tests.
3. Temp files: `tmp=$(mktemp -d "${TMPDIR:-/tmp}/<project>.XXXXXX")` and `trap 'rm -rf "$tmp"' EXIT`. Never write scratch files into the project tree.
4. Guard destructive commands: `rm -rf "${dir:?}/"`, absolute paths, no `cd` without `|| exit 1`.
5. File lists: `find ... -print0 | xargs -0` or a `while IFS= read -r` loop; never parse `ls`.
6. Check: `bash -n script.sh`, and `shellcheck script.sh` when it is installed.
7. Format: `shfmt -d -i 2 -ci script.sh` when it is installed (`-d` only prints the diff; fix with `shfmt -w` in a commit of its own).
8. Arguments and help: a usage line in the header comment, `-h` prints it, unknown flags exit 2.
9. Secrets come from environment variables or `.env`; never echo or log them.

Notes:
- More than about 50 lines of logic, or JSON and dates: write it in Python (`uv run`) instead.
- Make the script idempotent and support a `--dry-run` that prints the commands.
