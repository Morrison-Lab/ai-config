#!/usr/bin/env python3
"""Tests for the Antigravity hook command checker and renderer."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import agy_hooks  # noqa: E402
from lib.agy_hooks_fixtures import (
    CHECKER,
    ESCAPED_FORM,
    QUOTED_FORM,
    UNQUOTED_FORM,
    manifest_with,
)


class TestCommandProblems(unittest.TestCase):
    def test_escaped_quote_form_is_rejected(self):
        problems = agy_hooks.command_problems(ESCAPED_FORM)
        self.assertTrue(problems)
        self.assertTrue(any("backslash-escaped quote" in p for p in problems))

    def test_quoted_form_is_rejected_on_windows(self):
        self.assertTrue(agy_hooks.windows_problems(QUOTED_FORM))

    def test_unquoted_form_is_accepted_on_windows(self):
        self.assertEqual(agy_hooks.windows_problems(UNQUOTED_FORM), [])

    def test_empty_command_is_rejected(self):
        self.assertTrue(agy_hooks.command_problems("   "))

    def test_unbalanced_quote_is_rejected(self):
        self.assertTrue(any("odd number" in p for p in agy_hooks.command_problems('"a b')))


class TestCanonicalProblems(unittest.TestCase):
    def test_repo_manifest_passes(self):
        """Dogfood: the manifest actually shipped here must be renderable."""
        manifest = json.loads(CHECKER.CANONICAL_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(CHECKER.check_manifest(manifest, canonical=True), [])
        self.assertGreater(len(list(agy_hooks.iter_commands(manifest))), 0)

    def test_windows_path_in_canonical_manifest_is_rejected(self):
        findings = CHECKER.check_manifest(manifest_with(UNQUOTED_FORM), canonical=True)
        self.assertTrue(any("PreToolUse" in f for f in findings))
        self.assertTrue(any("Stop" in f for f in findings))
        self.assertTrue(any("does not start with" in f for f in findings))

    def test_a_command_with_two_defect_classes_reports_both(self):
        """A canonical-specific defect must not hide a command_problems one."""
        findings = agy_hooks.canonical_problems(ESCAPED_FORM)
        self.assertTrue(any("escaped" in f or "backslash" in f for f in findings))
        self.assertTrue(any("does not start with" in f for f in findings))

    def test_both_manifest_shapes_are_walked(self):
        found = [where for where, _ in agy_hooks.iter_commands(manifest_with(UNQUOTED_FORM))]
        self.assertEqual(len(found), 2)
        self.assertTrue(any("hooks[" in w for w in found))
        self.assertTrue(any("Stop" in w for w in found))



class TestEmptyManifestFails(unittest.TestCase):
    """A manifest that parses but carries no commands must not report OK."""

    def run_main(self, argv):
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            return CHECKER.main(argv), sink.getvalue()

    def test_a_command_less_manifest_is_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "hooks.json"
            empty.write_text("{}", encoding="utf-8")
            with patch.object(CHECKER, "CANONICAL_MANIFEST", empty):
                rc, out = self.run_main([])
        self.assertEqual(rc, 1)
        self.assertIn("carries no hook commands", out)


class TestWindowsStaleAndMetacharacters(unittest.TestCase):
    """A staged Windows manifest must not pass in its unrendered POSIX form."""

    POSIX = "python3 ~/.gemini/config/plugins/ai-config/hooks/x.py"

    def test_unrendered_posix_command_is_rejected_on_windows(self):
        findings = agy_hooks.windows_problems(self.POSIX)
        self.assertTrue(any("still starts with" in f for f in findings))
        self.assertTrue(any("does not expand" in f for f in findings))

    def test_msys_style_path_is_rejected_on_windows(self):
        findings = agy_hooks.windows_problems("/mingw64/bin/python3.exe C:/Users/x/.gemini/hooks/x.py")
        self.assertTrue(any("not a native Windows path" in f for f in findings))

    def test_native_windows_path_is_accepted_as_program(self):
        findings = agy_hooks.windows_problems("C:/Python313/python.exe C:/Users/x/.gemini/hooks/x.py")
        self.assertEqual(findings, [])

    def test_a_rendered_windows_command_passes(self):
        rendered = "C:/Python313/python.exe C:/Users/x/.gemini/hooks/x.py"
        self.assertEqual(agy_hooks.windows_problems(rendered), [])

    def test_each_cmd_metacharacter_is_rejected(self):
        for char in agy_hooks.CMD_METACHARACTERS:
            command = "C:/py/python.exe C:/plug" + char + "in/hooks/x.py"
            with self.subTest(char=char):
                findings = agy_hooks.cmd_metacharacter_problems(command)
                self.assertTrue(findings, char)
                self.assertIn(repr(char), findings[0])

    def test_assert_cmd_safe_rejects_a_metacharacter_path(self):
        with self.assertRaises(ValueError) as ctx:
            agy_hooks.assert_cmd_safe("C:/Program&Files/python.exe", "interpreter")
        self.assertIn("'&'", str(ctx.exception))

    def test_assert_cmd_safe_accepts_a_plain_path(self):
        agy_hooks.assert_cmd_safe("C:/Python313/python.exe", "interpreter")


class TestMissingInstalledManifest(unittest.TestCase):
    """An absent staged manifest is a defect once its directory exists."""

    def test_absent_and_required_is_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "hooks.json"
            report = CHECKER.check_file(missing, canonical=False, required=True)
        self.assertFalse(report["present"])
        self.assertTrue(any("is missing although" in f for f in report["findings"]))

    def test_a_required_missing_manifest_prints_its_finding(self):
        """The text CLI must not print SKIP over a finding; validate.yml reads it."""
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "plugins" / "ai-config" / "hooks.json"
            staged.parent.mkdir(parents=True)
            sink = io.StringIO()
            with patch.object(CHECKER, "installed_manifest_path", lambda: staged):
                with contextlib.redirect_stdout(sink):
                    rc = CHECKER.main(["--installed"])
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", sink.getvalue())
        self.assertIn("is missing although", sink.getvalue())
        self.assertNotIn("SKIP", sink.getvalue())

    def test_a_missing_canonical_manifest_fails(self):
        """It is checked into the repo, so absence means nothing was examined."""
        with tempfile.TemporaryDirectory() as tmp:
            sink = io.StringIO()
            original = CHECKER.CANONICAL_MANIFEST
            CHECKER.CANONICAL_MANIFEST = Path(tmp) / "hooks.json"
            try:
                with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    rc = CHECKER.main([])
            finally:
                CHECKER.CANONICAL_MANIFEST = original
        self.assertEqual(rc, 1)
        self.assertIn("checked into the repo", sink.getvalue())

    def test_absent_and_not_required_stays_a_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "hooks.json"
            report = CHECKER.check_file(missing, canonical=False)
        self.assertFalse(report["present"])
        self.assertEqual(report["findings"], [])


class TestNonStringCommand(unittest.TestCase):
    """A malformed manifest must produce a finding, never a traceback.

    command_problems already tolerated a non-string value, but both callers
    then ran string operations on it, so a `"command": null` crashed the
    checker and doctor.py reported only that it produced no report.
    """

    NON_STRINGS = (None, 12, 1.5, True, {}, [], ())

    def test_canonical_problems_reports_rather_than_raising(self):
        for value in self.NON_STRINGS:
            with self.subTest(value=value):
                self.assertEqual(agy_hooks.canonical_problems(value), ["command is empty"])

    def test_windows_problems_reports_rather_than_raising(self):
        for value in self.NON_STRINGS:
            with self.subTest(value=value):
                self.assertEqual(agy_hooks.windows_problems(value), ["command is empty"])

    def test_a_null_command_is_a_finding_end_to_end(self):
        manifest = {"hooks": {"Stop": [{"hooks": [{"command": None}]}]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hooks.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            report = CHECKER.check_file(path, canonical=True)
        self.assertTrue(any("command is empty" in f for f in report["findings"]))

if __name__ == "__main__":
    unittest.main()
