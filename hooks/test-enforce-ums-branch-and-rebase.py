#!/usr/bin/env python3
"""Test suite for hooks/enforce-ums-branch-and-rebase.py"""

import importlib.util
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
    def test_inspect_command_allows_ums_branch(self, mock_behind, mock_files, mock_branch):
        mock_branch.return_value = "ums/my-learnings"
        mock_files.return_value = ["memories/preferences.md"]
        mock_behind.return_value = False

        res = inspect_command("git commit -m 'update memory'")
        self.assertIsNone(res)

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


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEnforceUmsBranchAndRebase)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(f"\n{result.testsRun}/{result.testsRun} passed")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
