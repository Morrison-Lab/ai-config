#!/usr/bin/env python3
"""Unit tests for scripts/lib/ai_cli.py and scripts/detect-ai-clis.py."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import ai_cli


class TestAICLIHelper(unittest.TestCase):
    """Test AI CLI and developer tool detection helper functions."""

    def setUp(self):
        ai_cli.clear_executable_cache()

    def tearDown(self):
        ai_cli.clear_executable_cache()

    def test_empty_executable_name_returns_none(self):
        self.assertIsNone(ai_cli.find_executable(""))
        self.assertIsNone(ai_cli.find_executable("   "))
        self.assertFalse(ai_cli.is_tool_available(""))

    @patch.dict(os.environ, {"CUSTOMTOOL_PATH": "/custom/bin/mytool"}, clear=False)
    @patch("lib.ai_cli.is_executable_file", return_value=True)
    def test_find_executable_env_override(self, mock_is_exec):
        path = ai_cli.find_executable("customtool", use_cache=False)
        self.assertEqual(path, "/custom/bin/mytool")
        self.assertTrue(ai_cli.is_tool_available("customtool", use_cache=False))

    @patch("shutil.which")
    def test_find_executable_shutil_which(self, mock_which):
        mock_which.return_value = "/usr/bin/gh"
        path = ai_cli.find_executable("gh", use_cache=False)
        self.assertEqual(path, "/usr/bin/gh")
        self.assertTrue(ai_cli.is_gh_available(use_cache=False))

    @patch("shutil.which", return_value=None)
    @patch("lib.ai_cli.is_executable_file")
    def test_find_executable_fallback_dirs(self, mock_is_exec, mock_which):
        def fake_is_exec(p):
            return str(p).endswith(".local/bin/myfallbacktool")

        mock_is_exec.side_effect = fake_is_exec

        path = ai_cli.find_executable("myfallbacktool", fallback_to_dirs=True, use_cache=False)
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".local/bin/myfallbacktool"))

    @patch("shutil.which", return_value=None)
    @patch("lib.ai_cli.is_executable_file", return_value=False)
    def test_find_executable_not_found(self, mock_is_exec, mock_which):
        self.assertIsNone(ai_cli.find_executable("nonexistent_tool_xyz", use_cache=False))
        self.assertFalse(ai_cli.is_tool_available("nonexistent_tool_xyz", use_cache=False))

    @patch("shutil.which", return_value=None)
    @patch("lib.ai_cli.is_executable_file", return_value=False)
    def test_find_executable_fallback_to_dirs_false(self, mock_is_exec, mock_which):
        path = ai_cli.find_executable("claude", fallback_to_dirs=False, use_cache=False)
        self.assertIsNone(path)

    @patch("shutil.which")
    def test_find_executable_caching(self, mock_which):
        mock_which.return_value = "/usr/bin/gh"
        path1 = ai_cli.find_executable("gh", use_cache=True)
        self.assertEqual(path1, "/usr/bin/gh")
        mock_which.return_value = "/other/path/gh"
        path2 = ai_cli.find_executable("gh", use_cache=True)
        # Should return cached path1
        self.assertEqual(path2, "/usr/bin/gh")

        # After clearing cache, receives new path
        ai_cli.clear_executable_cache()
        path3 = ai_cli.find_executable("gh", use_cache=True)
        self.assertEqual(path3, "/other/path/gh")

    @patch("lib.ai_cli.find_executable")
    def test_cursor_alias_checks(self, mock_find):
        # When 'agent' is available
        mock_find.side_effect = lambda name, **k: "/bin/agent" if name == "agent" else None
        self.assertTrue(ai_cli.is_cursor_available(use_cache=False))
        self.assertEqual(ai_cli.find_ai_cli("cursor", use_cache=False), "/bin/agent")

        # When 'cursor' is available
        mock_find.side_effect = lambda name, **k: "/bin/cursor" if name == "cursor" else None
        self.assertTrue(ai_cli.is_cursor_available(use_cache=False))
        self.assertEqual(ai_cli.find_ai_cli("cursor", use_cache=False), "/bin/cursor")

    @patch("lib.ai_cli.find_executable")
    def test_antigravity_alias_checks(self, mock_find):
        # When 'agy' is available
        mock_find.side_effect = lambda name, **k: "/bin/agy" if name == "agy" else None
        self.assertTrue(ai_cli.is_agy_available(use_cache=False))

        # When 'antigravity' is available
        mock_find.side_effect = lambda name, **k: "/bin/antigravity" if name == "antigravity" else None
        self.assertTrue(ai_cli.is_agy_available(use_cache=False))

    @patch("lib.ai_cli.find_ai_cli")
    def test_detect_available_engines_priority(self, mock_find_ai):
        mock_find_ai.side_effect = lambda name, **k: f"/bin/{name}" if name in ("codex", "claude") else None

        engines = ai_cli.detect_available_engines(use_cache=False)
        self.assertEqual(engines, ["claude", "codex"])

        custom_order = ["antigravity", "codex", "claude"]
        engines_custom = ai_cli.detect_available_engines(priority_order=custom_order, use_cache=False)
        self.assertEqual(engines_custom, ["codex", "claude"])

    @patch("lib.ai_cli.find_ai_cli")
    @patch("lib.ai_cli.find_executable")
    def test_get_tool_status_report(self, mock_find_exec, mock_find_ai):
        mock_find_ai.side_effect = lambda name, **k: f"/bin/{name}" if name == "claude" else None
        mock_find_exec.side_effect = lambda name, **k: f"/bin/{name}" if name == "gh" else None

        report = ai_cli.get_tool_status_report()
        self.assertIn("ai_clis", report)
        self.assertIn("forge_tools", report)
        self.assertIn("available_engines", report)
        self.assertIn("claude", report["ai_clis"])
        self.assertTrue(report["ai_clis"]["claude"]["available"])
        self.assertTrue(report["forge_tools"]["gh"]["available"])

        table = ai_cli.format_tool_status_table(report)
        self.assertIn("AI CLI & Developer Tool Availability", table)
        self.assertIn("claude", table)
        self.assertIn("gh", table)


class TestDetectAICLIsCLI(unittest.TestCase):
    """Test CLI script scripts/detect-ai-clis.py."""

    def test_cli_json_output(self):
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "detect-ai-clis.py"), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("ai_clis", data)
        self.assertIn("forge_tools", data)
        self.assertIn("available_engines", data)

    def test_cli_text_output(self):
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "detect-ai-clis.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("AI CLI & Developer Tool Availability", res.stdout)
        self.assertIn("Forge & Developer Tools:", res.stdout)


if __name__ == "__main__":
    unittest.main()
