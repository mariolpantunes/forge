"""Tests for plan-keeper plan.py in a throwaway HOME. Usage: python3 -m unittest plan_keeper_test.py"""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

SCRIPT = Path(os.environ.get("PLAN_SCRIPT", Path(__file__).resolve().parent.parent / "skills/plan-keeper/scripts/plan.py"))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        self.plans = self.home / ".agents" / "plans"
        self.env = {**os.environ, "PLAN_KEEPER_HOME": str(self.home)}
        self.env.pop("PLAN_KEEPER_PLANS", None)

    def tearDown(self):
        self.tmp.cleanup()

    def run_plan(self, *args, cwd=None, code=0):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd or self.home, env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r.stdout + r.stderr

    def new_concept(self, desc, text="started"):
        out = self.run_plan("init", "--desc", desc)
        plan = [ln.split(": ", 1)[1] for ln in out.splitlines() if ln.startswith("plan: ")][0]
        self.run_plan("add", "--plan", plan, "Done", text)
        return plan


class HomeRouter(Base):
    def test_find_new_on_empty_router(self):
        out = self.run_plan("find", "write", "a", "paper", "about", "privacy")
        self.assertIn("verdict: new", out)
        self.assertIn("init --desc", out)

    def test_add_in_home_needs_plan(self):
        out = self.run_plan("add", "Done", "x", code=1)
        self.assertIn("--plan", out)

    def test_add_to_unknown_home_plan_is_refused(self):
        out = self.run_plan("add", "--plan", str(self.plans / "deadbeef"), "Done", "x", code=1)
        self.assertIn("init --desc", out)

    def test_portuguese_text_gets_a_warning(self):
        out = self.run_plan("init", "--desc", "preparar um curso de IA para a UNAVE com 12 horas")
        self.assertIn("in English", out)
        out = self.run_plan("init", "--desc", "course on AI for the university")
        self.assertNotIn("in English", out)
        out = self.run_plan("find", "preciso", "de", "um", "curso", "de", "IA")
        self.assertIn("translate", out)

    def test_init_needs_description(self):
        self.run_plan("init", code=1)

    def test_create_find_continue(self):
        plan = self.new_concept("tune the forge hints file for the agents")
        self.assertRegex(plan, r"/\.agents/plans/[0-9a-f]{8}/PLAN\.md$|^~/\.agents/plans/[0-9a-f]{8}/PLAN\.md$")
        router = (self.plans / "PLAN.md").read_text()
        self.assertIn("- tune the forge hints file for the agents | ~/.agents/plans/", router)
        out = self.run_plan("find", "update", "the", "forge", "hints", "file")
        self.assertIn("verdict: continue", out)
        self.assertIn("description: tune the forge hints file", out)
        out = self.run_plan("find", "write", "a", "paper", "about", "differential", "privacy")
        self.assertIn("verdict: new", out)

    def test_two_concepts_get_two_folders(self):
        self.new_concept("tune the forge hints file for the agents")
        self.new_concept("paper on differential privacy for smart meters")
        self.assertEqual(len([d for d in self.plans.iterdir() if d.is_dir()]), 2)
        out = self.run_plan("find", "continue", "the", "privacy", "paper", "on", "smart", "meters")
        self.assertIn("description: paper on differential privacy", out)

    def test_other_project_gets_entry_and_gitignore(self):
        proj = self.home / "git" / "demo"
        (proj / ".git").mkdir(parents=True)
        out = self.run_plan("add", "--plan", str(proj), "Done", "fixed typo in README")
        self.assertIn("added .agents/ to", out)
        self.assertIn(".agents/", (proj / ".gitignore").read_text())
        self.assertIn("fixed typo in README", (proj / ".agents" / "PLAN.md").read_text())
        self.assertIn(str(proj).replace(str(self.home), "~"), (self.plans / "PLAN.md").read_text())
        # a second add does not duplicate the gitignore line or the router row
        self.run_plan("add", "--plan", str(proj), "--desc", "demo project for tests", "Done", "second")
        self.assertEqual((proj / ".gitignore").read_text().count(".agents/"), 1)
        self.assertEqual((self.plans / "PLAN.md").read_text().count("/.agents/PLAN.md"), 1)
        self.assertIn("- demo project for tests | ", (self.plans / "PLAN.md").read_text())

    def test_project_add_uses_cwd_plan(self):
        proj = self.home / "git" / "demo"
        proj.mkdir(parents=True)
        out = self.run_plan("add", "Current", "doing X", cwd=proj)
        self.assertIn("ok:", out)
        self.assertTrue((proj / ".agents" / "PLAN.md").exists())
        self.assertFalse((self.plans / "PLAN.md").exists())


class Entries(Base):
    def test_long_entry_goes_to_notes(self):
        proj = self.home / "p"
        proj.mkdir()
        long = "result table\n" + "\n".join(f"row {i} " + "x" * 60 for i in range(20))
        self.run_plan("add", "Key", long, cwd=proj)
        text = (proj / ".agents" / "PLAN.md").read_text()
        self.assertIn("-> notes/", text)
        self.assertEqual(len(list((proj / ".agents" / "notes").glob("*.md"))), 1)
        self.assertNotIn("row 19", text)

    def test_section_order_and_alias(self):
        proj = self.home / "p"
        proj.mkdir()
        self.run_plan("add", "Done", "a", cwd=proj)
        self.run_plan("add", "key", "b", cwd=proj)
        text = (proj / ".agents" / "PLAN.md").read_text()
        self.assertLess(text.index("## Done"), text.index("## Key knowledge"))
        self.assertLess(text.index("- " + date.today().isoformat() + " a"), text.index("## Current"))

    def test_over_cap_warning(self):
        proj = self.home / "p"
        (proj / ".agents").mkdir(parents=True)
        (proj / ".agents" / "PLAN.md").write_text("# P\n\n## Done\n" + "- line of history, filler text here\n" * 1000
                                                  + "\n## Current\n\n## Next\n\n## Aborted\n\n## Key knowledge\n")
        out = self.run_plan("add", "Next", "one more", cwd=proj)
        self.assertIn("OVER CAP", out)
        out = self.run_plan("check", cwd=proj)
        self.assertIn("verdict compact", out)

    def test_parallel_adds_lose_nothing(self):
        proj = self.home / "p"
        proj.mkdir()
        self.run_plan("add", "Done", "seed", cwd=proj)
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda i: self.run_plan("add", "Done", f"parallel entry {i}", cwd=proj), range(16)))
        text = (proj / ".agents" / "PLAN.md").read_text()
        for i in range(16):
            self.assertIn(f"parallel entry {i}\n", text)


class Compact(Base):
    def setUp(self):
        super().setUp()
        self.proj = self.home / "p"
        self.proj.mkdir()
        self.plan = self.proj / ".agents" / "PLAN.md"
        self.run_plan("add", "Done", "ran `uv run train.py --seed 1` -> `out/m1.pt`", cwd=self.proj)
        self.run_plan("add", "Aborted", "tried dropout 0.9: worse, see `out/log1.txt`", cwd=self.proj)

    def test_flow(self):
        out = self.run_plan("archive", cwd=self.proj)
        h = [ln.split(": ")[1] for ln in out.splitlines() if ln.startswith("hash:")][0]
        draft = self.proj / "draft.md"
        good = self.plan.read_text()
        draft.write_text(good.replace("`out/m1.pt`", ""))
        out = self.run_plan("verify", "--new", str(draft), cwd=self.proj)
        self.assertIn("missing from the new plan: 1", out)
        self.assertIn("out/m1.pt", out)
        (self.proj / ".agents" / "notes").mkdir()
        (self.proj / ".agents" / "notes" / "moved.md").write_text("`out/m1.pt`\n")
        out = self.run_plan("verify", "--new", str(draft), cwd=self.proj)
        self.assertIn("missing from the new plan: 0", out)
        (self.proj / ".agents" / "notes" / "moved.md").unlink()
        draft.write_text("# P\n\n## Done\n")
        out = self.run_plan("verify", "--new", str(draft), cwd=self.proj, code=1)
        self.assertIn("missing section", out)
        draft.write_text(good)
        self.run_plan("add", "Done", "written by another session", cwd=self.proj)
        out = self.run_plan("replace", "--new", str(draft), "--expect", h, cwd=self.proj, code=3)
        self.assertIn("changed since", out)
        h2 = [ln.split(": ")[1] for ln in self.run_plan("archive", cwd=self.proj).splitlines() if ln.startswith("hash:")][0]
        draft.write_text(self.plan.read_text().replace("seed", "SEED"))
        out = self.run_plan("replace", "--new", str(draft), "--expect", h2, cwd=self.proj)
        self.assertIn("replaced", out)
        self.assertTrue(list((self.proj / ".agents" / "plan-archive").glob("PLAN-*.md")))

    def test_archive_expires(self):
        self.run_plan("archive", cwd=self.proj)
        f = next((self.proj / ".agents" / "plan-archive").glob("PLAN-*.md"))
        old = time.time() - 40 * 86400
        os.utime(f, (old, old))
        out = self.run_plan("check", cwd=self.proj)
        self.assertIn("expired 1", out)
        self.assertFalse(f.exists())


class Prune(Base):
    def make(self, name, title, nxt=False, age=0):
        d = self.plans / name
        d.mkdir(parents=True)
        (d / "PLAN.md").write_text(f"# {title}\n\n## Done\n- {name} done item\n\n## Current\n\n## Next\n"
                                   + ("- open item\n" if nxt else "") + "\n## Aborted\n\n## Key knowledge\n")
        (d / "extra.txt").write_text(name)
        t = time.time() - age * 86400
        os.utime(d / "PLAN.md", (t, t))

    def test_adopt_merge_archive_expire(self):
        self.make("2026-10-01-forge-hints", "forge hints file tuning for agents")
        self.make("c0ffee01", "tune forge hints file for agents", nxt=True)
        self.make("old-topic", "old stuff to forget", age=40)
        self.make("busy-topic", "busy things in progress", nxt=True, age=40)
        out = self.run_plan("prune")
        self.assertIn("merged", out)
        self.assertIn("archived idle old-topic", out)
        self.assertTrue((self.plans / "busy-topic" / "PLAN.md").exists())
        left = [d for d in (self.plans / "2026-10-01-forge-hints", self.plans / "c0ffee01") if d.exists()]
        self.assertEqual(len(left), 1)
        merged = (left[0] / "PLAN.md").read_text()
        self.assertIn("2026-10-01-forge-hints done item", merged)
        self.assertIn("c0ffee01 done item", merged)
        self.assertTrue((left[0] / "extra.txt").exists())
        self.assertTrue(list((self.plans / ".archive").glob("old-topic-*")))
        router = (self.plans / "PLAN.md").read_text()
        self.assertIn("archived: " + date.today().isoformat(), router)
        # expiry: age the archived folders
        for d in (self.plans / ".archive").iterdir():
            t = time.time() - 40 * 86400
            os.utime(d, (t, t))
        out = self.run_plan("prune")
        self.assertIn("expired", out)
        self.assertFalse(list((self.plans / ".archive").iterdir()))
        self.assertNotIn("old stuff", (self.plans / "PLAN.md").read_text())

    def test_dry_run_changes_nothing(self):
        self.make("2026-10-01-privacy-paper", "paper on privacy of smart meters")
        self.make("a1b2c3d4", "paper on privacy of smart meters data")
        out = self.run_plan("prune", "--dry-run")
        self.assertIn("merged", out)
        self.assertTrue((self.plans / "2026-10-01-privacy-paper").exists())

    def test_prune_without_folder(self):
        self.assertIn("nothing to prune", self.run_plan("prune"))


class SupportFolderRules(Base):
    def test_agents_plan_file_is_refused(self):
        out = self.run_plan("add", "--plan", str(self.home / ".agents" / "PLAN.md"), "Done", "x", code=1)
        self.assertIn("never write ~/.agents/PLAN.md", out)

    def test_support_folder_counts_as_home(self):
        (self.home / ".agents").mkdir(exist_ok=True)
        out = self.run_plan("find", "tune", "the", "hints", cwd=self.home / ".agents")
        self.assertIn("verdict: new", out)

    def test_add_prints_router_and_replace_updates_it(self):
        plan = self.new_concept("tune the forge hints file")
        out = self.run_plan("add", "--plan", plan, "Done", "second step")
        self.assertIn("router:", out)
        out = self.run_plan("archive", "--plan", plan)
        digest = [ln.split()[-1] for ln in out.splitlines() if "hash" in ln or "sha" in ln][-1]
        new = self.home / "compact.md"
        new.write_text(Path(plan.replace("~", str(self.home), 1)).read_text())
        out = self.run_plan("replace", "--plan", plan, "--new", str(new), "--expect", digest)
        self.assertIn("replaced", out)
        self.assertIn("tune the forge hints file", (self.plans / "PLAN.md").read_text())

    def test_project_init_with_plan_links_router_only_when_asked(self):
        proj = self.home / "git" / "demo2"
        (proj / ".git").mkdir(parents=True)
        self.run_plan("init", "--plan", str(proj), "--desc", "second demo project")
        self.assertIn("second demo project", (self.plans / "PLAN.md").read_text())


if __name__ == "__main__":
    unittest.main()
