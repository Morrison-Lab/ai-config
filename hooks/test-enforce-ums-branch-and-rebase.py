#!/usr/bin/env python3
"""Test suite for hooks/enforce-ums-branch-and-rebase.py"""

import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("enforce_ums_branch_and_rebase", os.path.join(HERE, "enforce-ums-branch-and-rebase.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

inspect_command = mod.inspect_command
touches_memory_or_skill = mod.touches_memory_or_skill
main_func = mod.main


class TestEnforceUmsBranchAndRebase(unittest.TestCase):
    def test_touches_memory_or_skill(self):
        self.assertTrue(touches_memory_or_skill(["memories/preferences.md"]))
        self.assertTrue(touches_memory_or_skill(["MEMORY.md"]))
        self.assertTrue(touches_memory_or_skill(["CLAUDE.md"]))
        self.assertTrue(touches_memory_or_skill(["GEMINI.md"]))
        self.assertTrue(touches_memory_or_skill(["skills/ums/SKILL.md"]))
        self.assertFalse(touches_memory_or_skill(["src/main.py"]))
        self.assertFalse(touches_memory_or_skill(["hooks/no-unauthorized-merge.py"]))

    @patch.object(mod, "get_current_branch")
    @patch.object(mod, "get_staged_or_modified_files")
    @patch.object(mod, "is_behind_origin_main")
    def test_inspect_command_blocks_feature_branch(self, mock_behind, mock_files, mock_branch):
        mock_branch.return_value = "feature/my-feature"
        mock_files.return_value = ["memories/preferences.md"]
        mock_behind.return_value = False

        res = inspect_command("git commit -m 'update memory'")
        self.assertIsNotNone(res)
        self.assertIn("MECHANISTIC PROHIBITION", res)
        self.assertIn("feature/my-feature", res)

    @patch.object(mod, "get_current_branch")
    @patch.object(mod, "get_staged_or_modified_files")
    @patch.object(mod, "is_behind_origin_main")
    def test_inspect_command_allows_ums_slash_and_hyphen_branch(self, mock_behind, mock_files, mock_branch):
        mock_files.return_value = ["memories/preferences.md"]
        mock_behind.return_value = False

        mock_branch.return_value = "ums/my-learnings"
        self.assertIsNone(inspect_command("git commit -m 'update memory'"))

        mock_branch.return_value = "ums-my-learnings"
        self.assertIsNone(inspect_command("git commit -m 'update memory'"))

    @patch.object(mod, "get_current_branch")
    @patch.object(mod, "get_staged_or_modified_files")
    @patch.object(mod, "is_behind_origin_main")
    def test_inspect_command_blocks_stale_ums_branch(self, mock_behind, mock_files, mock_branch):
        mock_branch.return_value = "ums/my-learnings"
        mock_files.return_value = ["memories/preferences.md"]
        mock_behind.return_value = True

        res = inspect_command("git commit -m 'update memory'")
        self.assertIsNotNone(res)
        self.assertIn("behind origin/main", res)

    @patch.object(mod, "inspect_command")
    def test_main_emits_deny_json_on_stdout(self, mock_inspect):
        mock_inspect.return_value = "MECHANISTIC PROHIBITION: test reason"
        input_data = json.dumps({"tool_input": {"command": "git commit -m test"}, "cwd": "/tmp"})

        with patch("sys.stdin.read", return_value=input_data), patch("sys.stdin", sys.stdin):
            from io import StringIO
            stdout = StringIO()
            with patch("sys.stdout", stdout):
                code = main_func()

        self.assertEqual(code, 0)
        output = stdout.getvalue().strip()
        parsed = json.loads(output)
        self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(parsed["hookSpecificOutput"]["permissionDecisionReason"], "MECHANISTIC PROHIBITION: test reason")


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEnforceUmsBranchAndRebase)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(f"\n{result.testsRun}/{result.testsRun} passed")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
