#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Find, write, check and merge skills safely when several agents work at once.

Usage: skill.py [--root DIR] find "<what the skill does>"
       skill.py [--root DIR] show NAME                     (prints tree-sha for --base)
       skill.py [--root DIR] put NAME RELPATH [--from FILE] [--base SHA]   (content from stdin if no --from)
       skill.py [--root DIR] check NAME
       skill.py [--root DIR] merge KEEP DROP [--apply]

find: verdict extend NAME (a skill already covers it) or new.
put: locked, atomic, refuses a stale --base, refuses content that is not generic or breaks the format.
check: format and generic/reusable findings (personal paths, mail, IPs, user name, secrets) as errors.
merge: dry run by default; --apply folds DROP into KEEP and moves DROP to <root>/../skill-archive.
--root defaults to ~/.agents/skills.
"""
import argparse
import fcntl
import hashlib
import os
import re
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from lib.common import run
from validate_skills import check_skill, frontmatter, generic_findings

STOP = set("a an and the of to for in on with from by or use when it its is are as at be this that into skill skills".split())


def words(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def skill_dirs(root):
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".") and (p / "SKILL.md").exists())


@contextmanager
def locked(root, name):
    d = root / ".locks"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / f"{name}.lock", "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def tree_sha(skill):
    h = hashlib.sha256()
    for f in sorted(skill.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            h.update(str(f.relative_to(skill)).encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def safe_target(skill, rel):
    t = (skill / rel).resolve()
    if rel.startswith("/") or not t.is_relative_to(skill.resolve()) or t == skill.resolve():
        raise SystemExit(f"error: {rel} is not a path inside {skill.name}")
    return t


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    if path.exists():
        tmp.chmod(path.stat().st_mode)
    os.replace(tmp, path)


def problems(skill, root):
    errs, _ = check_skill(skill, {p.name for p in skill_dirs(root)})
    return errs + [f"not generic: {g}" for g in generic_findings(skill)]


def cmd_find(a, root):
    mine = words(" ".join(a.task))
    scored = []
    for s in skill_dirs(root):
        fm, _ = frontmatter((s / "SKILL.md").read_text())
        theirs = words(s.name.replace("-", " ") + " " + (fm or {}).get("description", ""))
        scored.append((len(mine & theirs) / max(1, min(len(mine), len(theirs))), s.name, sorted(mine & theirs)))
    scored.sort(reverse=True)
    for sc, n, common in scored[:3]:
        print(f"candidate: {n} score {sc:.2f} shared {','.join(common)}")
    best = scored[0] if scored else (0, "", [])
    if best[0] >= 0.4 and len(best[2]) >= 2:
        print(f"verdict: extend {best[1]}\nnext: improve it with `skill.py put {best[1]} <relpath>`")
    else:
        print("verdict: new\nnext: scaffold with `new_skill.py <name> \"<what it does. Use when ...>\"`")
    return 0


def cmd_show(a, root):
    s = root / a.name
    if not (s / "SKILL.md").exists():
        raise SystemExit(f"error: no skill {a.name} in {root}")
    print(f"tree-sha: {tree_sha(s)}")
    for f in sorted(s.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            print(f"  {f.relative_to(s)} {f.stat().st_size}")
    return 0


def cmd_check(a, root):
    s = root / a.name
    errs = problems(s, root) if s.is_dir() else [f"no skill {a.name} in {root}"]
    for e in errs:
        print(f"error: {e}")
    print(f"{'FAIL' if errs else 'ok'} {a.name}")
    return 1 if errs else 0


def cmd_put(a, root):
    s = root / a.name
    if not (s / "SKILL.md").exists():
        raise SystemExit(f"error: no skill {a.name}: scaffold it first with new_skill.py")
    target = safe_target(s, a.relpath)
    data = Path(a.src).read_bytes() if a.src else sys.stdin.buffer.read()
    with locked(root, a.name):
        if a.base and a.base != tree_sha(s):
            print(f"conflict: {a.name} changed since tree-sha {a.base} (now {tree_sha(s)}).\n"
                  f"Run `skill.py show {a.name}`, read the new files, merge your change into them, put again with the new --base.")
            return 3
        before = set(problems(s, root))
        old = target.read_bytes() if target.exists() else None
        atomic_write(target, data)
        new = set(problems(s, root)) - before
        if new:
            if old is None:
                target.unlink()
            else:
                atomic_write(target, old)
            print("refused, previous content restored:")
            for e in sorted(new):
                print(f"  error: {e}")
            return 2
        print(f"wrote {a.name}/{a.relpath}\ntree-sha: {tree_sha(s)}")
    return 0


def rewrite_refs(text, drop, keep):
    return text.replace(f"skills/{drop}/", f"skills/{keep}/")


def merged_bytes(f, drop, keep):
    if f.suffix in {".py", ".sh", ".md", ".yml", ".yaml", ".toml"}:
        return rewrite_refs(f.read_text(errors="surrogateescape"), drop, keep).encode(errors="surrogateescape")
    return f.read_bytes()


def cmd_merge(a, root):
    keep, drop = root / a.keep, root / a.drop
    for s in (keep, drop):
        if not (s / "SKILL.md").exists():
            raise SystemExit(f"error: no skill {s.name} in {root}")
    if keep == drop:
        raise SystemExit("error: keep and drop are the same skill")
    plan = []
    for f in sorted(drop.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts or f.relative_to(drop) == Path("SKILL.md"):
            continue
        rel = f.relative_to(drop)
        dest = keep / rel
        if not dest.exists():
            plan.append(("copy", rel, rel))
        elif dest.read_bytes() != f.read_bytes():
            plan.append(("conflict", rel, Path("references") / f"merged-from-{drop.name}" / rel))
    _, body = frontmatter((drop / "SKILL.md").read_text())
    plan.append(("body", Path("SKILL.md"), Path("references") / f"{drop.name}.md"))
    for kind, src, dst in plan:
        print(f"{kind}: {src} -> {a.keep}/{dst}")
    if not a.apply:
        print("dry run: add --apply to merge")
        return 0
    first, second = sorted([a.keep, a.drop])
    with locked(root, first), locked(root, second):
        for kind, src, dst in plan:
            data = (body.strip() + "\n").encode() if kind == "body" else merged_bytes(drop / src, a.drop, a.keep)
            atomic_write(keep / dst, data)
        arch = root.parent / "skill-archive"
        arch.mkdir(exist_ok=True)
        shutil.move(str(drop), arch / f"{drop.name}-{time.strftime('%Y%m%d-%H%M%S')}")
    errs = problems(keep, root)
    stale = [str(p) for p in root.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".sh"} and re.search(rf"\b{re.escape(a.drop)}\b", p.read_text(errors="ignore"))]
    print(f"merged {a.drop} into {a.keep}; {a.drop} archived in {arch}")
    print(f"next: fold references/{a.drop}.md into {a.keep}/SKILL.md (steps, description), then `skill.py check {a.keep}`")
    for p in stale[:10]:
        print(f"stale pointer to {a.drop}: {p}")
    for e in errs:
        print(f"error: {e}")
    return 1 if errs else 0


def main(log):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="~/.agents/skills")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("find").add_argument("task", nargs="+")
    sub.add_parser("show").add_argument("name")
    sub.add_parser("check").add_argument("name")
    p = sub.add_parser("put")
    p.add_argument("name")
    p.add_argument("relpath")
    p.add_argument("--from", dest="src")
    p.add_argument("--base")
    m = sub.add_parser("merge")
    m.add_argument("keep")
    m.add_argument("drop")
    m.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).expanduser()
    return {"find": cmd_find, "show": cmd_show, "check": cmd_check, "put": cmd_put, "merge": cmd_merge}[a.cmd](a, root)


if __name__ == "__main__":
    run(main)
