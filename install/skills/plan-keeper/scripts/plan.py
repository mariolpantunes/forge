#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Manage PLAN.md files: find the plan of a task, add entries, check size, compact safely, prune.

Usage: plan.py find|init|add|check|archive|verify|replace|prune [options]  (--help per command)
Env (tests): PLAN_KEEPER_HOME = the home folder, PLAN_KEEPER_PLANS = the home plans folder.
"""
import argparse
import fcntl
import hashlib
import os
import re
import shutil
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

CAP_TOKENS = 8000  # compact above this
TARGET_TOKENS = 4000  # compact down to this
BYTES_PER_TOKEN = 3.3  # measured 3.3-3.6 on real plans
ENTRY_LINES = 3
ENTRY_BYTES = 400
LEDGER_LINES = 40
ARCHIVE_DAYS = 30  # safety copies and archived concepts expire
IDLE_DAYS = 14  # a home concept untouched this long, with no Next items, is archived
SECTIONS = ["Done", "Current", "Next", "Aborted", "Key knowledge"]
STOP = set(
    "the and for with that this from into over then than have has are was were not but you your our "
    "all any can will its use used using make made new old add fix get set run want need task "
    "para com uma uns que por dos das nos nas num mais como sobre entre isso este esta".split()
)


PT = set("de da do dos das para uma uns não nas nos pelo pela preciso sobre também são está".split())


def warn_english(text: str, what: str) -> None:
    """Plan files are English: warn when text looks Portuguese (two or more function words)."""
    if sum(1 for w in re.findall(r"[^\W\d_]+", text.lower()) if w in PT) >= 2:
        print(f"warning: {what} (plan files are English even when the chat is not)")


def home_dir() -> Path:
    return Path(os.environ.get("PLAN_KEEPER_HOME") or Path.home()).resolve()


def plans_dir() -> Path:
    env = os.environ.get("PLAN_KEEPER_PLANS")
    return Path(env).resolve() if env else home_dir() / ".agents" / "plans"


def short(p: Path) -> str:
    p = Path(p).resolve()
    try:
        return "~/" + str(p.relative_to(home_dir()))
    except ValueError:
        return str(p)


def expand(s: str) -> Path:
    return (home_dir() / s[2:]) if s.startswith("~/") else Path(s)


def tokens(nbytes: int) -> int:
    return int(nbytes / BYTES_PER_TOKEN)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


@contextmanager
def locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def norm_section(name: str) -> str | None:
    n = name.strip().lower().rstrip(":")
    for s in SECTIONS:
        if n == s.lower() or n.startswith(s.lower()) or (s == "Key knowledge" and n.startswith("key")):
            return s
    return None


def split_blocks(text: str) -> list[list]:
    """[[heading|None, [lines]], ...]; the first block is the text before any '## '."""
    blocks: list[list] = [[None, []]]
    for line in text.split("\n"):
        if line.startswith("## "):
            blocks.append([line, []])
        else:
            blocks[-1][1].append(line)
    return blocks


def join_blocks(blocks: list[list]) -> str:
    out: list[str] = []
    for head, lines in blocks:
        if head is not None:
            out.append(head)
        out.extend(lines)
    return "\n".join(out)


def section_entries(lines: list[str]) -> list[list[str]]:
    """Group a section's lines into entries: a bullet or numbered item plus its continuation lines."""
    entries: list[list[str]] = []
    for ln in lines:
        if re.match(r"^(- |\d+\. )", ln):
            entries.append([ln])
        elif ln.strip() and entries:
            entries[-1].append(ln)
    return entries


def insert_entry(text: str, section: str, entry: list[str]) -> str:
    blocks = split_blocks(text)
    for b in blocks:
        if b[0] and norm_section(b[0][3:]) == section:
            while b[1] and not b[1][-1].strip():
                b[1].pop()
            b[1].extend(entry + [""])
            return join_blocks(blocks)
    tail = text.rstrip("\n")
    return tail + f"\n\n## {section}\n" + "\n".join(entry) + "\n"


def skeleton(desc: str) -> str:
    return f"# PLAN: {desc}\nGoal: {desc}\n\n" + "\n".join(f"## {s}\n" for s in SECTIONS)


def router_skeleton() -> str:
    head = ("# PLAN (home)\nRouter: one row per work concept in Current, closed ones in Done.\n"
            "Row: `- description | plan path | touched: date`.\n\n")
    return head + "\n".join(f"## {s}\n" for s in SECTIONS)


def ensure_gitignore(project: Path) -> str | None:
    """Add '.agents/' to the project's .gitignore when the project is a git work tree."""
    if not any((d / ".git").exists() for d in [project, *project.parents]):
        return None
    gi = project / ".gitignore"
    cur = gi.read_text() if gi.exists() else ""
    if re.search(r"^/?\.agents/?\s*$", cur, re.M):
        return None
    gi.write_text(cur + ("" if cur.endswith("\n") or not cur else "\n") + ".agents/\n")
    return str(gi)


# ---- router rows -----------------------------------------------------------------------------
ROW = re.compile(r"^- (?P<desc>[^|]+?) \| (?P<path>[^|]+?) \| (?P<tail>(?:touched|archived|link broken): .*)$")


def clean_desc(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("|", "/")).strip()[:200]


def parse_rows(text: str) -> list[dict]:
    rows = []
    for head, lines in split_blocks(text):
        sec = norm_section(head[3:]) if head else None
        if sec not in ("Current", "Done"):
            continue
        for ln in lines:
            m = ROW.match(ln)
            if m:
                d = m.groupdict()
                d["section"] = sec
                d["touched"] = (re.search(r"(\d{4}-\d{2}-\d{2})", d["tail"]) or [None, ""])[1]
                rows.append(d)
    return rows


def fmt_row(r: dict) -> str:
    return f"- {r['desc']} | {r['path']} | {r['tail']}"


def write_rows(router: Path, rows: list[dict]) -> None:
    """Rewrite the Current and Done sections of the router from rows, keep everything else."""
    text = router.read_text() if router.exists() else router_skeleton()
    blocks = split_blocks(text)
    for sec in ("Current", "Done"):
        mine = [fmt_row(r) for r in rows if r["section"] == sec]
        for b in blocks:
            if b[0] and norm_section(b[0][3:]) == sec:
                kept = [ln for ln in b[1] if ln.strip() and not ROW.match(ln)]
                b[1] = kept + mine + [""]
                break
        else:
            blocks.append([f"## {sec}", mine + [""]])
    atomic_write(router, join_blocks(blocks))


def plan_goal(plan: Path) -> str | None:
    try:
        m = re.search(r"^Goal: (.+)$", plan.read_text(), re.M)
    except OSError:
        return None
    return m.group(1).strip() if m else None


def upsert_row(plan: Path, desc: str | None) -> None:
    """Record plan in the home router (touched today); create the row on first sight."""
    router = plans_dir() / "PLAN.md"
    if plan.resolve() == router.resolve():
        return
    with locked(router):
        rows = parse_rows(router.read_text()) if router.exists() else []
        path = short(plan)
        today = date.today().isoformat()
        for r in rows:
            if r["path"] == path:
                r["tail"] = f"touched: {today}"
                r["section"] = "Current"
                if desc:
                    r["desc"] = clean_desc(desc)
                break
        else:
            inside = plan.resolve().is_relative_to(plans_dir())
            fallback = plan_goal(plan) or (plan.parent.name if inside else f"project {plan.parent.parent.name}")
            rows.append({"desc": clean_desc(desc or fallback), "path": path, "tail": f"touched: {today}",
                         "section": "Current", "touched": today})
        write_rows(router, rows)
    print(f"router: {short(router)}")


def words(s: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", s.lower()):
        w = w[:-1] if w.endswith("s") and len(w) > 4 else w
        if w not in STOP and not re.fullmatch(r"\d+", w) and w not in out:
            out.append(w)
    return out


def row_words(r: dict) -> set[str]:
    w = set(words(r["desc"]))
    p = expand(r["path"])
    if not p.resolve().is_relative_to(plans_dir()):  # a project plan: its folder name counts
        w |= set(words(p.parent.parent.name))
    return w


# ---- plan resolution -------------------------------------------------------------------------
def is_home_or_support(p: Path) -> bool:
    r = p.resolve()
    return r == home_dir() or (r.is_relative_to(home_dir() / ".agents") and not r.is_relative_to(plans_dir()))


def at_home() -> bool:
    return is_home_or_support(Path.cwd())


def resolve_plan(arg: str | None) -> Path:
    if arg:
        p = expand(arg)
        if p.is_dir() or p.suffix != ".md":  # a folder, existing or not
            p = p / "PLAN.md" if p.resolve().is_relative_to(plans_dir()) else p / ".agents" / "PLAN.md"
        res = p.resolve()
        if res == (home_dir() / ".agents" / "PLAN.md").resolve():
            sys.exit("error: never write ~/.agents/PLAN.md; use ~/.agents/plans/PLAN.md via `plan.py find` or `init`")
        return res
    if at_home():
        sys.exit("error: in the home folder pass --plan (run `plan.py find \"<task>\"` first)")
    return (Path.cwd() / ".agents" / "PLAN.md").resolve()


def ensure_plan(plan: Path, desc: str | None) -> list[str]:
    notes = []
    if not plan.exists():
        label = clean_desc(desc) if desc else (plan.parent.name if plan.parent.name != ".agents" else plan.parent.parent.name)
        plan.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(plan, skeleton(label))
        notes.append(f"created {short(plan)}")
        if plan.parent.name == ".agents":
            gi = ensure_gitignore(plan.parent.parent)
            if gi:
                notes.append(f"added .agents/ to {gi} (mention it in the report)")
    return notes


def report_size(plan: Path) -> str:
    n = plan.stat().st_size
    t = tokens(n)
    if t > CAP_TOKENS:
        return (f"OVER CAP: {t} tokens (cap {CAP_TOKENS}, target {TARGET_TOKENS}). "
                f"Compact it now: follow the Compact steps of the plan-keeper skill, plan {short(plan)}")
    return f"ok: {t} tokens (cap {CAP_TOKENS})"


# ---- commands --------------------------------------------------------------------------------
def make_entry(text: str, plan: Path) -> list[str]:
    text = text.strip("\n")
    if not re.match(r"^\d{4}-\d{2}-\d{2}\b", text):
        text = f"{date.today().isoformat()} {text}"
    lines = text.split("\n")
    if len(lines) <= ENTRY_LINES and len(text.encode()) <= ENTRY_BYTES:
        return ["- " + lines[0]] + ["  " + ln.lstrip() for ln in lines[1:]]
    notes = plan.parent / "notes"
    notes.mkdir(exist_ok=True)
    name = f"{date.today().isoformat()}-{hashlib.sha256(text.encode()).hexdigest()[:6]}.md"
    (notes / name).write_text(text + "\n")
    first = lines[0][:ENTRY_BYTES // 2].rstrip()
    return [f"- {first} -> notes/{name}"]


def cmd_add(a) -> int:
    plan = resolve_plan(a.plan)
    section = norm_section(a.section)
    if not section:
        sys.exit(f"error: section must be one of {', '.join(SECTIONS)}")
    inside = plan.resolve().is_relative_to(plans_dir())
    if inside and not plan.exists():
        sys.exit('error: that home plan does not exist; create it with `plan.py init --desc "<one line>"`')
    text = sys.stdin.read() if a.text == "-" else a.text
    warn_english(text, "write the entry in English")
    warn_english(a.desc or "", "write the description in English")
    for n in ensure_plan(plan, a.desc):
        print(n)
    with locked(plan):
        atomic_write(plan, insert_entry(plan.read_text(), section, make_entry(text, plan)))
    if inside or at_home() or a.plan or a.desc or (plans_dir() / "PLAN.md").exists():
        upsert_row(plan, a.desc)
    print(f"added to {short(plan)} [{section}]")
    print(report_size(plan))
    return 0


def cmd_init(a) -> int:
    if a.plan:
        plan = resolve_plan(a.plan)
    elif at_home():
        if not a.desc:
            sys.exit('error: pass --desc "<one line: what the work is, with its key nouns>"')
        while True:
            plan = plans_dir() / uuid.uuid4().hex[:8] / "PLAN.md"
            if not plan.parent.exists():
                break
    else:
        plan = resolve_plan(None)
    warn_english(a.desc or "", "write the description in English")
    for n in ensure_plan(plan, a.desc) or [f"exists {short(plan)}"]:
        print(n)
    if plan.resolve().is_relative_to(plans_dir()) or at_home() or a.plan or a.desc or (plans_dir() / "PLAN.md").exists():
        upsert_row(plan, a.desc)
    print(f"plan: {short(plan)}")
    return 0


def expire(plan: Path) -> int:
    n = 0
    arch = plan.parent / "plan-archive"
    if arch.is_dir():
        for f in arch.iterdir():
            if f.is_file() and time.time() - f.stat().st_mtime > ARCHIVE_DAYS * 86400:
                f.unlink()
                n += 1
    return n


def cmd_check(a) -> int:
    if a.plan or not at_home():
        plans = [resolve_plan(a.plan)]
    else:
        router = plans_dir() / "PLAN.md"
        plans = [router] + [expand(r["path"]) for r in parse_rows(router.read_text())
                            if r["section"] == "Current"] if router.exists() else []
    for p in plans:
        if not p.exists():
            print(f"{short(p)}: missing")
            continue
        text = p.read_text()
        t = tokens(len(text.encode()))
        per = {}
        for head, lines in split_blocks(text):
            if head:
                per[head[3:].strip()[:24]] = tokens(len("\n".join(lines).encode()))
        long_e = sum(1 for h, ls in split_blocks(text) for e in section_entries(ls)
                     if len("\n".join(e).encode()) > ENTRY_BYTES * 2)
        verdict = "compact" if t > CAP_TOKENS else "ok"
        print(f"{short(p)}: {t} tokens, verdict {verdict}, entries over {ENTRY_BYTES * 2} bytes: {long_e}")
        print("  sections: " + ", ".join(f"{k} {v}" for k, v in per.items()))
        gone = expire(p)
        if gone:
            print(f"  expired {gone} archived copies older than {ARCHIVE_DAYS} days")
    return 0


def cmd_archive(a) -> int:
    plan = resolve_plan(a.plan)
    if not plan.exists():
        sys.exit(f"error: {short(plan)} does not exist")
    arch = plan.parent / "plan-archive"
    arch.mkdir(exist_ok=True)
    dest = arch / f"PLAN-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    shutil.copy2(plan, dest)
    print(f"archive: {short(dest)}")
    print(f"hash: {sha(plan)}")
    print("next: write the compact plan to a scratch file, then `plan.py verify` and `plan.py replace`")
    return 0


SPAN = re.compile(r"`([^`\n]{3,})`")
LOOKS = re.compile(r"[/.]\w|^(uv|cargo|python3?|bash|git|gh|\./)\b")


def kept_spans(text: str) -> set[str]:
    return {s for s in SPAN.findall(text) if LOOKS.search(s)}


def hard_problems(new_text: str) -> list[str]:
    heads = [norm_section(h[3:]) for h, _ in split_blocks(new_text) if h]
    probs = [f"missing section: {s}" for s in SECTIONS if s not in heads]
    t = tokens(len(new_text.encode()))
    if t > CAP_TOKENS:
        probs.append(f"{t} tokens, above the cap {CAP_TOKENS}")
    return probs


def cmd_verify(a) -> int:
    plan = resolve_plan(a.plan)
    new = Path(a.new).read_text()
    arch = plan.parent / "plan-archive"
    old_path = Path(a.old) if a.old else max(arch.glob("PLAN-*.md"), default=plan)
    old = old_path.read_text()
    notes = plan.parent / "notes"  # what moved to notes/ is kept, not lost
    haystack = new + "\n".join(f.read_text() for f in notes.glob("*.md")) if notes.is_dir() else new
    missing = [s for s in sorted(kept_spans(old)) if s not in haystack]
    probs = hard_problems(new)
    t = tokens(len(new.encode()))
    ledger_n = sum(1 for h, ls in split_blocks(new) for e in section_entries(ls)
                   if h and "tried" in h.lower())
    print(f"old: {short(old_path)} ({tokens(len(old.encode()))} tokens); new: {t} tokens (target {TARGET_TOKENS})")
    if t > TARGET_TOKENS * 1.25:
        print("warning: above the target by more than 25 percent, move run lists and results to notes/")
    if ledger_n > LEDGER_LINES:
        print(f"warning: Tried ledger has {ledger_n} entries (max {LEDGER_LINES}); move the oldest to notes/tried.md")
    print(f"paths and commands missing from the new plan: {len(missing)}")
    for m in missing[:40]:
        print(f"  - `{m}`")
    if len(missing) > 40:
        print(f"  ... {len(missing) - 40} more")
    for p in probs:
        print(f"error: {p}")
    print("verify: " + ("FAILED" if probs else "ok (restore or justify every missing item, then replace)"))
    return 1 if probs else 0


def cmd_replace(a) -> int:
    plan = resolve_plan(a.plan)
    new = Path(a.new).read_text()
    probs = hard_problems(new)
    if probs:
        print("refused: " + "; ".join(probs))
        return 1
    with locked(plan):
        if sha(plan) != a.expect:
            print("refused: the plan changed since `archive` (another session wrote to it). "
                  "Run `archive` again, merge the new entries into your compact version, then replace.")
            return 3
        atomic_write(plan, new if new.endswith("\n") else new + "\n")
    if plan.resolve().is_relative_to(plans_dir()) or at_home() or a.plan or (plans_dir() / "PLAN.md").exists():
        upsert_row(plan, None)
    print(f"replaced {short(plan)}")
    print(report_size(plan))
    return 0


# ---- find ------------------------------------------------------------------------------------
def cmd_find(a) -> int:
    task = " ".join(a.task)
    warn_english(task, "translate the task to English words before find")
    cwd = Path(a.cwd).resolve() if a.cwd else Path.cwd().resolve()
    if not is_home_or_support(cwd):
        p = cwd / ".agents" / "PLAN.md"
        print(f"verdict: continue\nplan: {short(p)}\nexists: {'yes' if p.exists() else 'no'}")
        return 0
    router = plans_dir() / "PLAN.md"
    t = set(words(task))
    best, best_score, ranked = None, 0, []
    for r in parse_rows(router.read_text()) if router.exists() else []:
        if r["section"] != "Current" or not expand(r["path"]).exists():
            continue
        score = len(t & row_words(r))
        ranked.append((score, r["desc"][:50]))
        if score > best_score or (score == best_score and best and r["touched"] > best["touched"]):
            best, best_score = r, score
    if best and (best_score >= 3 or (best_score >= 2 and len(t) <= 4)):
        print(f"verdict: continue\nplan: {best['path']}\ndescription: {best['desc']}\nscore: {best_score}")
    else:
        print("verdict: new")
        print('next: plan.py init --desc "<one line: what the work is, with its key nouns>"')
    for sc, d in sorted(ranked, reverse=True)[:3]:
        print(f"ranked: {sc} {d}")
    return 0


# ---- prune and merge (home plans only) -------------------------------------------------------
def norm_slug(s: str) -> str:
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", s)


def same_concept(a: dict, b: dict) -> bool:
    wa, wb = set(words(a["desc"])), set(words(b["desc"]))
    if not wa or not wb:
        return False
    shared = len(wa & wb)
    coef = shared / min(len(wa), len(wb))
    return (shared >= 3 and coef >= 0.6) or (shared >= 2 and coef >= 0.9)


def move_into(item: Path, dest_dir: Path, prefix: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / item.name
    if item.is_dir() and dest.is_dir():
        for child in list(item.iterdir()):
            move_into(child, dest, prefix)
        item.rmdir()
        return
    if dest.exists():
        dest = dest_dir / f"{prefix}-{item.name}"
    shutil.move(str(item), str(dest))


def to_archive(folder: Path, label: str) -> Path:
    arch = plans_dir() / ".archive"
    arch.mkdir(exist_ok=True)
    dest = arch / f"{label}-{date.today().isoformat()}"
    n = 1
    while dest.exists():
        n += 1
        dest = arch / f"{label}-{date.today().isoformat()}-{n}"
    shutil.move(str(folder), str(dest))
    os.utime(dest)  # the expiry clock starts now
    return dest


def merge_rows(src: dict, dst: dict, apply: bool) -> None:
    sdir, ddir = expand(src["path"]).parent, expand(dst["path"]).parent
    if apply:
        with locked(ddir / "PLAN.md"):
            text = (ddir / "PLAN.md").read_text()
            have = {"\n".join(e) for _, ls in split_blocks(text) for e in section_entries(ls)}
            for head, ls in split_blocks((sdir / "PLAN.md").read_text()):
                sec = norm_section(head[3:]) if head else None
                for e in section_entries(ls) if sec else []:
                    if "\n".join(e) not in have:
                        text = insert_entry(text, sec, e)
            atomic_write(ddir / "PLAN.md", text)
        for item in list(sdir.iterdir()):
            if item.name not in ("PLAN.md", "PLAN.md.lock", "plan-archive"):
                move_into(item, ddir, sdir.name)
        to_archive(sdir, sdir.name + "-merged")
    dst["tail"] = f"touched: {max(src['touched'] or '', dst['touched'] or '')}"


def cmd_prune(a) -> int:
    base, apply = plans_dir(), not a.dry_run
    if not base.is_dir():
        print("no home plans folder: nothing to prune")
        return 0
    router = base / "PLAN.md"
    today = date.today()
    log: list[str] = []
    with locked(router):
        rows = parse_rows(router.read_text()) if router.exists() else []
        listed = {r["path"] for r in rows}
        for d in sorted(base.iterdir()):  # adopt folders the router does not know (old dated folders)
            p = d / "PLAN.md"
            if d.is_dir() and not d.name.startswith(".") and p.exists() and short(p) not in listed:
                title = plan_goal(p) or p.read_text().split("\n", 1)[0].lstrip("# ").strip()
                touched = date.fromtimestamp(p.stat().st_mtime).isoformat()
                rows.append({"desc": clean_desc(f"{title} {' '.join(words(norm_slug(d.name)))}"),
                             "path": short(p), "tail": f"touched: {touched}", "section": "Current",
                             "touched": touched})
                log.append(f"adopted {d.name}")
        for r in rows:  # broken links
            if r["section"] == "Current" and not expand(r["path"]).exists():
                r.update(section="Done", tail=f"link broken: {today.isoformat()}")
                log.append(f"link broken {r['desc'][:40]}")
        inside = [r for r in rows if r["section"] == "Current" and expand(r["path"]).resolve().is_relative_to(base)]
        for r in list(inside):  # merge duplicates automatically, larger plan is the target
            for o in list(inside):
                if o is not r and o in inside and r in inside and same_concept(r, o):
                    big, small = sorted((r, o), key=lambda x: -expand(x["path"]).stat().st_size)
                    merge_rows(small, big, apply)
                    rows.remove(small)
                    inside.remove(small)
                    log.append(f"merged {expand(small['path']).parent.name} into {expand(big['path']).parent.name}")
        for r in inside:  # archive idle concepts without open Next items
            p = expand(r["path"])
            age = (today - date.fromisoformat(r["touched"])).days if r["touched"] else 0
            nxt = [e for h, ls in split_blocks(p.read_text()) if h and norm_section(h[3:]) == "Next"
                   for e in section_entries(ls)]
            if age > IDLE_DAYS and not nxt:
                name = p.parent.name
                if apply:
                    dest = to_archive(p.parent, name)
                    r["path"] = short(dest / "PLAN.md")
                r.update(section="Done", tail=f"archived: {today.isoformat()}")
                log.append(f"archived idle {name} ({age} days, no Next items)")
        arch = base / ".archive"
        if arch.is_dir():  # expire archived folders
            for d in arch.iterdir():
                if time.time() - d.stat().st_mtime > ARCHIVE_DAYS * 86400:
                    if apply:
                        shutil.rmtree(d) if d.is_dir() else d.unlink()
                    log.append(f"expired {d.name}")
        rows = [r for r in rows if not (r["section"] == "Done" and r["tail"].startswith("archived")
                                        and not expand(r["path"]).exists())]
        done = [r for r in rows if r["section"] == "Done"]
        for r in done[:-20]:
            rows.remove(r)
        if apply:
            write_rows(router, rows)
    print("\n".join(log) if log else "nothing to prune")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="pick the plan for a task (home: concept lookup)")
    f.add_argument("task", nargs="+")
    f.add_argument("--cwd", help="folder the session works in (default: current)")
    i = sub.add_parser("init", help="create a plan; in the home folder a new concept folder (id is random)")
    i.add_argument("--plan", help="project folder or plan file (default: new home concept, or ./.agents/PLAN.md)")
    i.add_argument("--desc", help="one line: what the work is, with its key nouns")
    d = sub.add_parser("add", help="append an entry; prints OVER CAP when the plan needs compaction")
    d.add_argument("--plan", help="plan file or folder (default ./.agents/PLAN.md)")
    d.add_argument("--desc", help="update the one-line description in the home router")
    d.add_argument("section", help="Done|Current|Next|Aborted|Key")
    d.add_argument("text", help="entry text, or - for stdin")
    c = sub.add_parser("check", help="size per section, verdict, expire old safety copies")
    c.add_argument("--plan")
    r = sub.add_parser("archive", help="verbatim safety copy; prints the hash for replace")
    r.add_argument("--plan")
    v = sub.add_parser("verify", help="compare a compact draft with the archived plan")
    v.add_argument("--plan")
    v.add_argument("--new", required=True)
    v.add_argument("--old")
    p = sub.add_parser("replace", help="install the compact draft if the plan did not change")
    p.add_argument("--plan")
    p.add_argument("--new", required=True)
    p.add_argument("--expect", required=True, help="hash printed by archive")
    u = sub.add_parser("prune", help="home plans: adopt, merge duplicates, archive idle, expire")
    u.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return {"find": cmd_find, "init": cmd_init, "add": cmd_add, "check": cmd_check, "archive": cmd_archive,
            "verify": cmd_verify, "replace": cmd_replace, "prune": cmd_prune}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
