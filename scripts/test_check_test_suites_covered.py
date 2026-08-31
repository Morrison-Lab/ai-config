#!/usr/bin/env python3
"""Unit tests for scripts/check-test-suites-covered.py."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parent / "check-test-suites-covered.py"

spec = importlib.util.spec_from_file_location("check_test_suites_covered", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["check_test_suites_covered"] = mod
spec.loader.exec_module(mod)

check_coverage = mod.check_coverage
find_test_suites = mod.find_test_suites
extract_active_run_commands = mod.extract_active_run_commands
is_suite_executed = mod.is_suite_executed
main = mod.main


class TestFindTestSuites(unittest.TestCase):
    def test_find_test_suites_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            suites = find_test_suites(Path(tmpdir))
            self.assertEqual(suites, [])

    def test_find_test_suites_nonexistent_dir(self):
        suites = find_test_suites(Path("/nonexistent/path/here"))
        self.assertEqual(suites, [])

    def test_find_test_suites_filters_matching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "test_a.py").write_text("# test", encoding="utf-8")
            (td / "test_b.py").write_text("# test", encoding="utf-8")
            (td / "other.py").write_text("# other", encoding="utf-8")
            (td / "test_c.txt").write_text("# txt", encoding="utf-8")

            suites = find_test_suites(td)
            names = [s.name for s in suites]
            self.assertEqual(names, ["test_a.py", "test_b.py"])


class TestExtractAndCheckCoverage(unittest.TestCase):
    def test_workflow_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            with self.assertRaises(FileNotFoundError):
                check_coverage(td / "missing.yml", td)

    def test_no_test_suites_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            wf = td / "validate.yml"
            wf.write_text("steps:\n  - run: python3 scripts/test_a.py\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                check_coverage(wf, td)

    def test_all_covered_single_and_multiline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "test_a.py").write_text("# test", encoding="utf-8")
            (td / "test_b.py").write_text("# test", encoding="utf-8")
            (td / "test_c.py").write_text("# test", encoding="utf-8")
            wf = td / "validate.yml"
            wf.write_text(
                "steps:\n"
                "  - name: Run test a\n"
                "    run: python3 scripts/test_a.py\n"
                "  - name: Run multiline\n"
                "    run: |\n"
                "      python3 scripts/test_b.py\n"
                "      python3 scripts/test_c.py\n",
                encoding="utf-8",
            )

            covered, missing = check_coverage(wf, td)
            self.assertEqual(covered, ["test_a.py", "test_b.py", "test_c.py"])
            self.assertEqual(missing, [])

    def test_commented_out_line_does_not_cover(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "test_a.py").write_text("# test", encoding="utf-8")
            (td / "test_b.py").write_text("# test", encoding="utf-8")
            wf = td / "validate.yml"
            wf.write_text(
                "steps:\n"
                "  - name: Run test a\n"
                "    run: python3 scripts/test_a.py\n"
                "  # - run: python3 scripts/test_b.py\n",
                encoding="utf-8",
            )

            covered, missing = check_coverage(wf, td)
            self.assertEqual(covered, ["test_a.py"])
            self.assertEqual(missing, ["test_b.py"])

    def test_step_name_or_prose_mention_does_not_cover(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "test_a.py").write_text("# test", encoding="utf-8")
            (td / "test_b.py").write_text("# test", encoding="utf-8")
            wf = td / "validate.yml"
            wf.write_text(
                "steps:\n"
                "  - name: Run test a\n"
                "    run: python3 scripts/test_a.py\n"
                "  - name: Mention test_b.py without running it\n"
                "    run: echo 'no test here'\n",
                encoding="utf-8",
            )

            covered, missing = check_coverage(wf, td)
            self.assertEqual(covered, ["test_a.py"])
            self.assertEqual(missing, ["test_b.py"])


class TestMainCLI(unittest.TestCase):
    def test_main_success_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "test_a.py").write_text("# test", encoding="utf-8")
            wf = td / "validate.yml"
            wf.write_text("steps:\n  - run: python3 scripts/test_a.py\n", encoding="utf-8")

            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                code = main(["--workflow", str(wf), "--scripts-dir", str(td)])
            self.assertEqual(code, 0)
            self.assertIn("all 1 scripts/test_*.py test suites are gated", stdout.getvalue())

    def test_main_failure_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "test_a.py").write_text("# test", encoding="utf-8")
            (td / "test_b.py").write_text("# test", encoding="utf-8")
            wf = td / "validate.yml"
            wf.write_text("steps:\n  - run: python3 scripts/test_a.py\n", encoding="utf-8")

            stderr = io.StringIO()
            with patch("sys.stderr", stderr):
                code = main(["--workflow", str(wf), "--scripts-dir", str(td)])
            self.assertEqual(code, 1)
            self.assertIn("1 of 2 test suite(s)", stderr.getvalue())
            self.assertIn("test_b.py", stderr.getvalue())

    def test_main_success_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "test_a.py").write_text("# test", encoding="utf-8")
            wf = td / "validate.yml"
            wf.write_text("steps:\n  - run: python3 scripts/test_a.py\n", encoding="utf-8")

            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                code = main(["--workflow", str(wf), "--scripts-dir", str(td), "--json"])
            self.assertEqual(code, 0)
            data = json.loads(stdout.getvalue())
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["missing_count"], 0)

    def test_main_failure_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "test_a.py").write_text("# test", encoding="utf-8")
            (td / "test_b.py").write_text("# test", encoding="utf-8")
            wf = td / "validate.yml"
            wf.write_text("steps:\n  - run: python3 scripts/test_a.py\n", encoding="utf-8")

            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                code = main(["--workflow", str(wf), "--scripts-dir", str(td), "--json"])
            self.assertEqual(code, 1)
            data = json.loads(stdout.getvalue())
            self.assertEqual(data["status"], "missing_suites")
            self.assertEqual(data["total"], 2)
            self.assertEqual(data["missing"], ["test_b.py"])

    def test_main_missing_workflow_json(self):
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = main(["--workflow", "/nonexistent/path/validate.yml", "--json"])
        self.assertEqual(code, 2)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["status"], "error")


if __name__ == "__main__":
    unittest.main()
