#!/usr/bin/env python3
"""Regression tests for gen-topic-map.py (ai-config#949).

Each case runs the real script as a subprocess against a scratch tree. The
negative cases matter most: a --check that nobody has watched fail is a guess.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "gen-topic-map.py"


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True, text=True,
    )


def make_tree(root: Path) -> None:
    (root / "docs").mkdir()
    skill = root / "skills" / "reprexes"
    skill.mkdir(parents=True)
    skill.joinpath("SKILL.md").write_text(
        '---\nname: reprexes\ndescription: "Build minimal reproducible example."\n'
        "keywords: reprex, minimal example\n---\nbody\n"
    )
    frag = root / "shared" / "principles"
    frag.mkdir(parents=True)
    frag.joinpath("fail-fast.md").write_text("Fail fast.\nStop early.\n\n## Rules\n")
    frag.joinpath("fail-fast.cases.md").write_text("Companion text.\n")


class TopicMapTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_tree(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def test_generates_rows_and_keywords(self):
        self.assertEqual(run(self.root).returncode, 0)
        text = (self.root / "docs" / "topic-map.md").read_text()
        self.assertIn("| `skills/reprexes/SKILL.md` | Build minimal reproducible example. | reprex, minimal example |", text)
        self.assertIn("| `shared/principles/fail-fast.md` | Fail fast. Stop early. |  |", text)

    def test_companion_files_are_skipped(self):
        run(self.root)
        text = (self.root / "docs" / "topic-map.md").read_text()
        self.assertNotIn("fail-fast.cases.md", text)

    def test_relative_links_are_reduced_to_their_text(self):
        frag = self.root / "shared" / "principles" / "linked.md"
        frag.write_text("See [the rule](issue-first.md) and [more](../../CLAUDE.md#x).\n")
        run(self.root)
        text = (self.root / "docs" / "topic-map.md").read_text()
        self.assertIn("See the rule and more.", text)
        self.assertNotIn("issue-first.md", text)

    def test_check_passes_when_fresh(self):
        run(self.root)
        self.assertEqual(run(self.root, "--check").returncode, 0)

    def test_check_fails_when_missing(self):
        self.assertEqual(run(self.root, "--check").returncode, 1)

    def test_check_fails_when_a_file_is_added(self):
        run(self.root)
        new = self.root / "skills" / "extra"
        new.mkdir()
        new.joinpath("SKILL.md").write_text("---\nname: extra\ndescription: New.\n---\n")
        result = run(self.root, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stderr)

    def test_map_is_not_vacuous_on_the_real_repo(self):
        real = Path(__file__).resolve().parent.parent
        self.assertEqual(run(real, "--check").returncode, 0)
        self.assertGreater((real / "docs" / "topic-map.md").read_text().count("\n| `"), 100)


if __name__ == "__main__":
    unittest.main()
