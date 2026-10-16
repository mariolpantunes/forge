#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Create a new skill folder that already passes the validator.

Usage: new_skill.py NAME "DESCRIPTION" [--script NAME.py] [--ref NAME.md] [--root DIR]

NAME: lowercase words joined by hyphens. DESCRIPTION: what it does, then "Use when ..."
(under 300 chars). --root defaults to ~/.agents/skills. Never overwrites an existing skill.
Takes the same per-skill lock as skill.py and appears atomically (built aside, then renamed),
so parallel agents never see a half-built skill and only one creator of a name wins.
"""
import argparse
import os
import re
import shutil
import stat
from pathlib import Path

from lib.common import run
from skill import locked

SKILL = """---
name: {name}
description: {desc}
---

# {name}

1. TODO exact command or action.
2. TODO next step.

Notes: TODO only what the model would get wrong.
"""

PY = '''#!/usr/bin/env -S uv run --script
# @@ script
# requires-python = ">=3.10"
# dependencies = []
# @@
"""TODO one line: what it does. Usage: {file} <args>"""
import sys

from lib.common import run


def main(log):
    log.info("TODO")


if __name__ == "__main__":
    run(main)
'''


def build(d, a):
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(SKILL.format(name=a.name, desc=a.description))
    for s in a.script:
        (d / "scripts").mkdir(exist_ok=True)
        p = d / "scripts" / s
        body = PY.format(file=s).replace("@@", "///")
        lib = d / "scripts" / "lib"
        if not lib.exists():
            lib.mkdir()
            (lib / "__init__.py").write_text("")
            src = Path(__file__).parent / "lib" / "common.py"
            (lib / "common.py").write_text(src.read_text())
        p.write_text(body)
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    for r in a.ref:
        (d / "references").mkdir(exist_ok=True)
        (d / "references" / r).write_text("Read when: TODO\n\n")


def main(log):
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("description")
    ap.add_argument("--script", action="append", default=[])
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--root", default="~/.agents/skills")
    a = ap.parse_args()
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", a.name):
        raise SystemExit("name must be lowercase words joined by hyphens")
    if len(a.description) > 300 or not re.search(r"\bUse\b", a.description):
        raise SystemExit('description: under 300 chars and must contain "Use when ..."')
    root = Path(a.root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    d = root / a.name
    with locked(root, a.name):
        if d.exists():
            raise SystemExit(f"{d} exists: improve it instead of creating a new skill")
        tmp = root / f".new-{a.name}-{os.getpid()}"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            build(tmp, a)
            os.rename(tmp, d)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    log.info("created %s; fill the TODOs, then run validate_skills.py", d)
    print(d)


if __name__ == "__main__":
    run(main)
