#!/usr/bin/env python3
"""Tests for the Antigravity hook command checker and renderer."""
from __future__ import annotations

import json
import sys
import unittest
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

    def test_both_manifest_shapes_are_walked(self):
        found = [where for where, _ in agy_hooks.iter_commands(manifest_with(UNQUOTED_FORM))]
        self.assertEqual(len(found), 2)
        self.assertTrue(any("hooks[" in w for w in found))
        self.assertTrue(any("Stop" in w for w in found))


if __name__ == "__main__":
    unittest.main()
