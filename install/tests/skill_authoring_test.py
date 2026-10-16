"""Tests for skill-authoring/scripts/skill.py (find, put, check, merge) in a temp skills root.

Run: python3 -m unittest install/tests/skill_authoring_test.py
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/skill-authoring/scripts/skill.py"
MD = '---\nname: {n}\ndescription: "{d}"\n---\n\n# {n}\n\n1. Run `uv run ~/.agents/skills/{n}/scripts/x.py`.\n'


def sk(root, name, desc, files=None):
    d = root / name
    (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text(MD.format(n=name, d=desc))
    for rel, text in (files or {}).items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text)
    return d


class SkillPy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "skills"
        self.root.mkdir()
        sk(self.root, "pdf-notes", "Extract notes from PDF files. Use when a PDF must be summarised.", {"scripts/x.py": "print(1)\n"})

    def tearDown(self):
        self.tmp.cleanup()

    def sp(self, *args, stdin=None):
        r = subprocess.run([str(SCRIPT), "--root", str(self.root), *args], input=stdin, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_find_extend_and_new(self):
        rc, out = self.sp("find", "extract notes from a PDF file")
        self.assertIn("verdict: extend pdf-notes", out)
        rc, out = self.sp("find", "train a neural network on images")
        self.assertIn("verdict: new", out)

    def test_put_writes_and_updates_sha(self):
        rc, out = self.sp("show", "pdf-notes")
        sha = out.split("tree-sha: ")[1].split()[0]
        rc, out = self.sp("put", "pdf-notes", "references/a.md", "--base", sha, stdin="detail\n")
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.root / "pdf-notes/references/a.md").read_text(), "detail\n")

    def test_put_refuses_stale_base(self):
        rc, out = self.sp("put", "pdf-notes", "references/a.md", "--base", "deadbeef", stdin="x\n")
        self.assertEqual(rc, 3)
        self.assertFalse((self.root / "pdf-notes/references/a.md").exists())

    def test_put_refuses_personal_content_and_restores(self):
        rc, out = self.sp("put", "pdf-notes", "references/a.md", stdin="see /home/someone/data and a@b.org\n")
        self.assertEqual(rc, 2, out)
        self.assertIn("not generic", out)
        self.assertFalse((self.root / "pdf-notes/references/a.md").exists())

    def test_put_refuses_path_escape(self):
        rc, out = self.sp("put", "pdf-notes", "../other/SKILL.md", stdin="x\n")
        self.assertNotEqual(rc, 0)

    def test_parallel_puts_are_not_corrupted(self):
        procs = [subprocess.Popen([str(SCRIPT), "--root", str(self.root), "put", "pdf-notes", f"references/r{i}.md"],
                                  stdin=subprocess.PIPE, text=True, stdout=subprocess.DEVNULL) for i in range(6)]
        for i, p in enumerate(procs):
            p.communicate(f"content {i}\n")
        for i in range(6):
            self.assertEqual((self.root / f"pdf-notes/references/r{i}.md").read_text(), f"content {i}\n")

    def test_merge_dry_run_then_apply(self):
        sk(self.root, "pdf-summary", "Summarise PDF files. Use when a PDF needs a summary.",
           {"scripts/y.py": "print(2)\n", "scripts/x.py": "print('other')\n", "references/r.md": "see ~/.agents/skills/pdf-summary/scripts/y.py\n"})
        rc, out = self.sp("merge", "pdf-notes", "pdf-summary")
        self.assertIn("dry run", out)
        self.assertTrue((self.root / "pdf-summary").exists())
        rc, out = self.sp("merge", "pdf-notes", "pdf-summary", "--apply")
        self.assertFalse((self.root / "pdf-summary").exists(), out)
        keep = self.root / "pdf-notes"
        self.assertTrue((keep / "scripts/y.py").exists())
        self.assertTrue((keep / "references/merged-from-pdf-summary/scripts/x.py").exists())
        self.assertIn("skills/pdf-notes/scripts/y.py", (keep / "references/r.md").read_text())
        self.assertTrue((keep / "references/pdf-summary.md").exists())
        self.assertEqual(len(list((Path(self.tmp.name) / "skill-archive").iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
