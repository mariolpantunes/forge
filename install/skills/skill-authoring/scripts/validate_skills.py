#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Validate the skills folder against the Agent Skills format and our conventions.

Usage: validate_skills.py [--run] [SKILLS_DIR]     default: ~/.agents/skills. --run also executes each script with --help (slow, catches broken scripts).

Checks per skill: SKILL.md frontmatter (name equals folder, description present),
body size, paths mentioned in SKILL.md exist, scripts are executable, Python scripts
declare a PEP 723 block and import nothing from outside the skill, Rust skills have
a Cargo.toml, bash scripts use strict mode, no secrets, no stale ~/.agent paths.
Exit 1 if any error. Warnings do not change the exit code.
"""
import re
import subprocess
import sys
from pathlib import Path

from lib.common import run

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SECRET_RE = re.compile(r"(api[_-]?key|token|secret|password)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}", re.I)
PATH_RE = re.compile(r"~/\.agents/skills/([a-z0-9-]+)/((?:scripts|references)/[\w./-]+)")
RUN = "--run" in sys.argv
if RUN:
    sys.argv.remove("--run")
STDLIB = set(sys.stdlib_module_names)
ALIASES = {"sklearn": "scikit_learn", "PIL": "pillow", "cv2": "opencv_python", "yaml": "pyyaml", "bs4": "beautifulsoup4", "dateutil": "python_dateutil"}


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            v = v.strip()
            if v[:1] not in "\"'" and (": " in v or " #" in v):
                fm.setdefault("_yaml_error", k.strip())
            fm[k.strip()] = v[1:-1] if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'" else v
    return fm, text[m.end():]


def check_python(f, skill, err, warn):
    src = f.read_text()
    if not src.startswith("#!/usr/bin/env -S uv run --script"):
        err(f"{f.name}: shebang must be '#!/usr/bin/env -S uv run --script'")
    if "# /// script" not in src:
        err(f"{f.name}: missing PEP 723 '# /// script' block")
    local = {p.stem for p in (skill / "scripts").iterdir()} | {"lib"}
    declared = re.search(r"# dependencies = \[(.*?)\]", src, re.S)
    deps = {d.strip(" \"'").split(">")[0].split("=")[0].lower().replace("-", "_") for d in declared.group(1).split(",")} if declared else set()
    for mod in re.findall(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", src, re.M):
        mod = ALIASES.get(mod, mod)
        if mod not in STDLIB and mod not in local and mod.lower() not in deps and mod != "pillow":
            err(f"{f.name}: imports '{mod}' but it is not declared in the script block")
        if mod == "pillow" and "pillow" not in deps:
            err(f"{f.name}: imports PIL but 'pillow' is not declared")
    if re.search(r"sys\.path\.insert\(.*\.\.", src) or re.search(r"\.agents/skills/(?!%s)" % skill.name, src):
        err(f"{f.name}: reaches outside its skill folder")


def check_skill(skill, ok_names):
    errs, warns = [], []
    err, warn = errs.append, warns.append
    md = skill / "SKILL.md"
    if not md.exists():
        return ["SKILL.md missing"], warns
    text = md.read_text()
    fm, body = frontmatter(text)
    if fm is None:
        return ["SKILL.md has no frontmatter"], warns
    name, desc = fm.get("name", ""), fm.get("description", "")
    if "_yaml_error" in fm:
        err(f"frontmatter '{fm['_yaml_error']}' has ': ' or ' #' unquoted: strict YAML parsers (goose) skip the skill; wrap it in double quotes")
    if name != skill.name:
        err(f"name '{name}' must equal folder '{skill.name}'")
    if not NAME_RE.match(skill.name):
        err("folder name must be lowercase words joined by hyphens")
    if not desc:
        err("description is empty")
    else:
        if len(desc) > 300:
            warn(f"description is {len(desc)} chars; keep it under 300 (small models)")
        if not re.search(r"\bUse\b", desc):
            warn('description should say when to use the skill ("Use when ...")')
        if re.search(r"\b(I|you|your|my)\b", desc):
            warn("description should be third person (no I/you/my)")
    if len(body.splitlines()) > 60:
        warn(f"body is {len(body.splitlines())} lines; keep it under 60, move detail to references/")
    if re.search(r"^(\d+\.|Notes:) TODO", text, re.M):
        err("SKILL.md still has TODO placeholders")
    for s, rel in PATH_RE.findall(text):
        if s not in ok_names or not (skill.parent / s / rel.rstrip(".,)`")).exists():
            err(f"mentioned path does not exist: {s}/{rel}")
    for f in sorted(skill.rglob("*")):
        if not f.is_file() or (skill.name == "skill-authoring" and f.name == "validate_skills.py") or "__pycache__" in f.parts or "target" in f.parts:
            continue
        rel = f.relative_to(skill)
        if f.suffix in {".py", ".sh", ".md", ".yaml", ".yml", ".toml", ".rs"}:
            t = f.read_text(errors="ignore")
            if SECRET_RE.search(t):
                err(f"{rel}: looks like a secret")
            if re.search(r"~/\.agent(?!s)\b|/\.agent/", t):
                err(f"{rel}: stale ~/.agent path (use ~/.agents)")
        if rel.parts[0] == "scripts" and len(rel.parts) == 2 and f.suffix in {".py", ".sh"}:
            if not f.stat().st_mode & 0o111:
                err(f"{rel}: not executable")
            if f.suffix == ".py":
                check_python(f, skill, err, warn)
            else:
                if "set -euo pipefail" not in f.read_text():
                    err(f"{rel}: bash script needs 'set -euo pipefail'")
    sc = skill / "scripts"
    if (sc / "lib").exists() and not any("lib." in p.read_text(errors="ignore") or "from lib" in p.read_text(errors="ignore")
                                         for p in sc.glob("*.py")):
        warn("scripts/lib is not imported by any script: delete it")
    if RUN:
        for p in sorted(sc.glob("*.py")) if sc.exists() else []:
            r = subprocess.run(["uv", "run", str(p), "--help"], capture_output=True, text=True, timeout=300)
            out = (r.stderr or "") + (r.stdout or "")
            if "Traceback" in out or "ModuleNotFoundError" in out or r.returncode in (126, 127):
                err(f"scripts/{p.name} --help fails: {out.strip()[-200:]}")
    if list(skill.rglob("*.rs")) and not list(skill.rglob("Cargo.toml")):
        err("Rust sources without Cargo.toml (use cargo)")
    return errs, warns


def main(log):
    if "--help" in sys.argv:
        print(__doc__)
        return 0
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "~/.agents/skills").expanduser()
    skills = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    # a folder without SKILL.md that holds skills in subfolders (claude's account-synced skills) is a container, not a broken skill
    for c in [p for p in skills if not (p / "SKILL.md").exists() and any(p.rglob("SKILL.md"))]:
        print(f"skip {c.name} (no SKILL.md of its own, holds skills in subfolders)")
        skills.remove(c)
    names = {p.name for p in skills}
    bad = 0
    for s in skills:
        errs, warns = check_skill(s, names)
        print(f"{'FAIL' if errs else 'ok  '} {s.name}")
        for e in errs:
            print(f"     error: {e}")
        for w in warns:
            print(f"     warn:  {w}")
        bad += bool(errs)
    print(f"{len(skills)} skills, {bad} with errors")
    return 1 if bad else 0


if __name__ == "__main__":
    run(main)
