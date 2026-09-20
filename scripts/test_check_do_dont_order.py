#!/usr/bin/env python3
"""Tests for scripts/check-do-dont-order.py."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "check-do-dont-order.py"

sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util

spec = importlib.util.spec_from_file_location("check_do_dont_order", SCRIPT_PATH)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class TestExtractBlocks(unittest.TestCase):
    def test_clean_do_then_dont(self):
        text = """
Some introductory text.

- **Do:** first good thing.
- **Do:** second good thing.
- **Don't:** first bad thing.
- **Don't:** second bad thing.

Trailing text.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(len(blocks[0].bullets), 4)
        violations = checker.check_block("test.md", blocks[0])
        self.assertEqual(violations, [])

    def test_only_do_bullets(self):
        text = """
- **Do:** first good thing.
- **Do:** second good thing.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 1)
        violations = checker.check_block("test.md", blocks[0])
        self.assertEqual(violations, [])

    def test_only_dont_bullets(self):
        text = """
- **Don't:** first bad thing.
- **Don't:** second bad thing.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 1)
        violations = checker.check_block("test.md", blocks[0])
        self.assertEqual(violations, [])

    def test_interleaved_do_after_dont(self):
        text = """
- **Do:** good 1.
- **Don't:** bad 1.
- **Do:** good 2.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 1)
        violations = checker.check_block("test.md", blocks[0])
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].line_number, 4)
        self.assertEqual(violations[0].first_dont_line, 3)

    def test_multiple_misplaced_dos(self):
        text = """
- **Do:** good 1.
- **Don't:** bad 1.
- **Do:** good 2.
- **Don't:** bad 2.
- **Do:** good 3.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 1)
        violations = checker.check_block("test.md", blocks[0])
        self.assertEqual(len(violations), 2)
        self.assertEqual(violations[0].line_number, 4)
        self.assertEqual(violations[0].first_dont_line, 3)
        self.assertEqual(violations[1].line_number, 6)
        self.assertEqual(violations[1].first_dont_line, 3)

    def test_blank_line_resets_block(self):
        text = """
- **Do:** block 1 good.
- **Don't:** block 1 bad.

- **Do:** block 2 good.
- **Don't:** block 2 bad.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 2)
        v1 = checker.check_block("test.md", blocks[0])
        v2 = checker.check_block("test.md", blocks[1])
        self.assertEqual(v1, [])
        self.assertEqual(v2, [])

    def test_prose_line_resets_block(self):
        text = """
- **Don't:** block 1 bad.
Intervening paragraph explaining the rule.
- **Do:** block 2 good.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(checker.check_block("test.md", blocks[0]), [])
        self.assertEqual(checker.check_block("test.md", blocks[1]), [])

    def test_heading_resets_block(self):
        text = """
- **Don't:** bad thing.
## New Section
- **Do:** good thing.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(checker.check_block("test.md", blocks[0]), [])
        self.assertEqual(checker.check_block("test.md", blocks[1]), [])

    def test_thematic_break_resets_block(self):
        text = """
- **Don't:** bad thing.
---
- **Do:** good thing.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(checker.check_block("test.md", blocks[0]), [])
        self.assertEqual(checker.check_block("test.md", blocks[1]), [])

    def test_continuation_lines(self):
        text = """
- **Do:** first bullet with
  two spaces of continuation
  across three source lines.
- **Don't:** second bullet with
\ta tab of continuation.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(len(blocks[0].bullets), 2)
        violations = checker.check_block("test.md", blocks[0])
        self.assertEqual(violations, [])

    def test_code_fences_ignored(self):
        text = """
Here is an example code block quoting bad bullets:

```markdown
- **Don't:** this is in code.
- **Do:** this is in code too.
```

~~~
- **Don't:** in tilde fence.
- **Do:** in tilde fence.
~~~

- **Do:** actual good bullet.
- **Don't:** actual bad bullet.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(len(blocks[0].bullets), 2)
        violations = checker.check_block("test.md", blocks[0])
        self.assertEqual(violations, [])

    def test_indented_code_fences_ignored(self):
        text = """
   ```python
   # Inside an indented fence:
   # - **Don't:** inside fence
   # - **Do:** inside fence
   ```

- **Do:** top level good.
"""
        blocks = checker.extract_blocks_from_text(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(len(blocks[0].bullets), 1)
        self.assertEqual(checker.check_block("test.md", blocks[0]), [])


class TestCLIAndModes(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_cli_clean_file(self):
        clean_file = self.tmp_path / "clean.md"
        clean_file.write_text(
            "- **Do:** good.\n- **Don't:** bad.\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--strict", str(clean_file)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Checked 1 file(s), 1 Do/Don't block(s).", proc.stdout)
        self.assertIn("No Do/Don't ordering violations found.", proc.stdout)

    def test_cli_violation_advisory_vs_strict(self):
        bad_file = self.tmp_path / "bad.md"
        bad_file.write_text(
            "- **Don't:** bad.\n- **Do:** good.\n",
            encoding="utf-8",
        )
        # Default advisory exits 0
        proc_adv = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(bad_file)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_adv.returncode, 0)
        self.assertIn("Found 1 block(s) with Do after Don't", proc_adv.stdout)

        # Strict mode exits 1
        proc_strict = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--strict", str(bad_file)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc_strict.returncode, 1)
        self.assertIn("Found 1 block(s) with Do after Don't", proc_strict.stdout)

    def test_cli_json_format(self):
        bad_file = self.tmp_path / "sample.md"
        bad_file.write_text(
            "- **Do:** 1.\n- **Don't:** 2.\n- **Do:** 3.\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--json", str(bad_file)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["files_examined"], 1)
        self.assertEqual(data["blocks_examined"], 1)
        self.assertEqual(data["bad_blocks_count"], 1)
        self.assertEqual(data["misplaced_do_count"], 1)
        self.assertEqual(len(data["violations"]), 1)
        self.assertEqual(data["violations"][0]["line"], 3)
        self.assertEqual(data["violations"][0]["first_dont_line"], 2)

    def test_ignored_directories_skipped(self):
        # Create files in various ignored directory paths
        dirs_to_create = [
            self.tmp_path / ".worktrees" / "branch1",
            self.tmp_path / ".claude" / "worktrees" / "branch2",
            self.tmp_path / "_site",
            self.tmp_path / ".quarto",
            self.tmp_path / "node_modules" / "pkg",
            self.tmp_path / ".git" / "refs",
            self.tmp_path / "docs" / "valid",
        ]
        for d in dirs_to_create:
            d.mkdir(parents=True, exist_ok=True)
            (d / "sample.md").write_text("- **Do:** foo.\n", encoding="utf-8")

        discovered = checker.discover_files(self.tmp_path, [])
        rel_discovered = [p.relative_to(self.tmp_path).as_posix() for p in discovered]
        self.assertEqual(rel_discovered, ["docs/valid/sample.md"])

    def test_diff_scoped_filtering(self):
        # Set up a mini git repository
        git_dir = self.tmp_path / "repo"
        git_dir.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=git_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test Agent"],
            cwd=git_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "agent@test.local"],
            cwd=git_dir,
            check=True,
            capture_output=True,
        )

        f1 = git_dir / "f1.md"
        f2 = git_dir / "f2.md"
        f1.write_text("- **Do:** base 1.\n- **Don't:** base 2.\n", encoding="utf-8")
        f2.write_text("- **Don't:** bad.\n- **Do:** bad.\n", encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=git_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=git_dir,
            check=True,
            capture_output=True,
        )

        # Modify only f1.md with clean bullets
        f1.write_text("- **Do:** clean 1.\n- **Do:** clean 2.\n", encoding="utf-8")
        subprocess.run(["git", "add", "f1.md"], cwd=git_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "edit f1"],
            cwd=git_dir,
            check=True,
            capture_output=True,
        )

        # In diff-scoped mode against HEAD~1, f2.md (which has a violation) should be skipped
        report = checker.run_check(git_dir, [], base_ref="HEAD~1")
        self.assertEqual(report["files_examined"], 1)
        self.assertEqual(report["bad_blocks_count"], 0)

        # In full scan mode, f2.md violation is reported and both files examined
        report_full = checker.run_check(git_dir, [])
        self.assertEqual(report_full["files_examined"], 2)
        self.assertEqual(report_full["bad_blocks_count"], 1)

    def test_invalid_base_ref_falls_back(self):
        git_dir = self.tmp_path / "repo2"
        git_dir.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=git_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test Agent"],
            cwd=git_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "agent@test.local"],
            cwd=git_dir,
            check=True,
            capture_output=True,
        )

        f = git_dir / "file.md"
        f.write_text("- **Don't:** bad.\n- **Do:** bad.\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=git_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=git_dir,
            check=True,
            capture_output=True,
        )

        # Supplying an unresolvable base-ref falls back to full scan rather than 0 files examined
        report = checker.run_check(git_dir, [], base_ref="invalid-ref-does-not-exist")
        self.assertEqual(report["files_examined"], 1)
        self.assertEqual(report["bad_blocks_count"], 1)


if __name__ == "__main__":
    unittest.main()
