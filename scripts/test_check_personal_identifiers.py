#!/usr/bin/env python3
"""Tests for scripts/check-personal-identifiers.py."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "check_personal_identifiers", ROOT / "scripts" / "check-personal-identifiers.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class TestCountHits(unittest.TestCase):
    def test_each_identifier_kind_counts(self):
        text = "\n".join([
            "ssh cf463-02", "the DEM-MBP-02 keychain", "/home/morri313/x",
            "/Users/ezramorrison/Documents", "D:\\GitHub", "morri313", "dougmor",
            "login dem-extra1",
        ])
        self.assertEqual(checker.count_hits(text), 8)

    def test_org_and_repo_owner_are_not_counted(self):
        self.assertEqual(checker.count_hits("Morrison-Lab/gha and d-morrison"), 0)

    def test_a_generic_machine_name_is_not_counted(self):
        self.assertEqual(checker.count_hits("ssh cf9-01 and my-laptop"), 0)


class TestScope(unittest.TestCase):
    def test_shared_rules_skills_and_hooks_are_in_scope(self):
        for path in ("shared/workflow/x.md", "skills/ums/SKILL.md",
                     "hooks/no-x.py", "scripts/pr-scope.py", "AGENTS.md"):
            self.assertTrue(checker.in_scope(path), path)

    def test_memories_tests_cases_and_docs_are_out_of_scope(self):
        for path in ("memories/shell.md", "hooks/test-no-x.py",
                     "scripts/test_pr_scope.py", "CLAUDE.cases.md",
                     "docs/index.html", "examples/branch-rulesets/DECISIONS.md",
                     "skills/x/image.png"):
            self.assertFalse(checker.in_scope(path), path)


class TestCompare(unittest.TestCase):
    def test_a_file_over_its_baseline_is_a_finding(self):
        found = checker.compare({"shared/a.md": 3}, {"shared/a.md": 2})
        self.assertEqual(len(found), 1)
        self.assertIn("shared/a.md", found[0])

    def test_a_new_file_with_a_hit_is_a_finding(self):
        self.assertEqual(len(checker.compare({"shared/new.md": 1}, {})), 1)

    def test_a_file_at_or_under_its_baseline_passes(self):
        self.assertEqual(checker.compare({"shared/a.md": 2, "shared/b.md": 1},
                                         {"shared/a.md": 2, "shared/b.md": 4}), [])


class TestRepoBaseline(unittest.TestCase):
    """Negative control: the scan must see the occurrences the baseline records."""

    def test_the_scan_finds_something_and_the_tree_is_within_baseline(self):
        counts = checker.scan(checker.tracked_files())
        baseline = json.loads(checker.BASELINE.read_text(encoding="utf-8"))
        self.assertGreater(sum(counts.values()), 0)
        self.assertEqual(checker.compare(counts, baseline), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
