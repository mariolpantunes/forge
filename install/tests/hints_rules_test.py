"""Static gate for the FORGE hints rules (user directives of 2026-10-16).

Run: python3 -m unittest install/tests/hints_rules_test.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = {"plan-keeper", "skill-authoring"}
MAX_BULLET = 160
HINTS = (ROOT / "AGENTS.md").read_text()
MOIM = (ROOT / "moim.md").read_text()
BULLETS = [ln for ln in HINTS.splitlines() if re.match(r"^(- |\d+\. )", ln)]
SKILLS = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}


class HintsRules(unittest.TestCase):
    def test_bullets_are_singular(self):
        for b in BULLETS:
            with self.subTest(b=b[:60]):
                self.assertLessEqual(len(b), MAX_BULLET, "bullet too long")
                self.assertNotIn(";", b, "two instructions in one bullet")
                self.assertNotRegex(b, r"\([^)]*\(", "nested parentheses")
                self.assertLessEqual(b.count("("), 1, "more than one parenthesis")

    def test_only_core_skills_are_named(self):
        for name, text in (("AGENTS.md", HINTS), ("moim.md", MOIM)):
            named = {s for s in SKILLS if re.search(rf"(?<![\w-]){re.escape(s)}(?![\w-])", text)}
            self.assertEqual(named - CORE, set(), f"{name} names non-core skills")

    def test_core_skills_are_named(self):
        for name, text in (("AGENTS.md", HINTS), ("moim.md", MOIM)):
            for s in CORE:
                self.assertIn(s, text, f"{name} must name {s}")

    def test_bp_skills_are_not_listed(self):
        for text in (HINTS, MOIM):
            self.assertIsNone(re.search(r"\bbp-(?!\*)[a-z]+", text), "list bp-* only as the generic glob")
            self.assertEqual(len(re.findall(r"bp-\*", HINTS)), 1, "exactly one generic bp-* bullet")

    def test_no_known_contradiction_phrases(self):
        self.assertNotRegex(HINTS, r"(?i)every task")
        self.assertNotIn("rg -m1", HINTS + MOIM, "agents list their skills natively; no search command")
        self.assertNotRegex(HINTS, r"(?i)ask the user.*library|library.*ask the user")


if __name__ == "__main__":
    unittest.main()
