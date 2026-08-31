#!/usr/bin/env python3
"""Unit tests for scripts/doctor.py preflight diagnostic tool."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import doctor


class TestDoctor(unittest.TestCase):
    """Test doctor check functions and report generation."""

    @patch("doctor.run_cmd")
    def test_check_git_status_ok(self, mock_run_cmd):
        mock_run_cmd.side_effect = [
            (0, "true", ""),  # is-inside-work-tree
            (0, "main", ""),  # branch
            (0, "", ""),      # status
            (0, "worktree /path/to/wt", ""),  # worktree list
        ]
        res = doctor.check_git_status()
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "OK")
        self.assertEqual(res["branch"], "main")
        self.assertTrue(res["clean"])

    @patch("doctor.run_cmd")
    def test_check_git_status_not_repo(self, mock_run_cmd):
        mock_run_cmd.return_value = (1, "", "fatal: not a git repository")
        res = doctor.check_git_status()
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "FAIL")

    @patch("doctor.run_cmd")
    def test_check_submodules(self, mock_run_cmd):
        # All initialized
        mock_run_cmd.return_value = (0, " 123456 shared/sembr-skills (heads/main)", "")
        res = doctor.check_submodules()
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "OK")

        # Uninitialized
        mock_run_cmd.return_value = (0, "-123456 shared/sembr-skills", "")
        res_warn = doctor.check_submodules()
        self.assertFalse(res_warn["ok"])
        self.assertEqual(res_warn["status"], "WARN")
        self.assertIn("shared/sembr-skills", res_warn["uninitialized"])

        # Error
        mock_run_cmd.return_value = (1, "", "git submodule command failed")
        res_fail = doctor.check_submodules()
        self.assertFalse(res_fail["ok"])
        self.assertEqual(res_fail["status"], "FAIL")

    @patch("doctor.run_cmd")
    def test_check_codex_wrappers(self, mock_run_cmd):
        mock_run_cmd.return_value = (0, "ok", "")
        res = doctor.check_codex_wrappers()
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "OK")

        mock_run_cmd.return_value = (1, "", "drift detected")
        res_fail = doctor.check_codex_wrappers()
        self.assertFalse(res_fail["ok"])
        self.assertEqual(res_fail["status"], "FAIL")

    @patch("doctor.run_cmd")
    def test_check_hook_catalog(self, mock_run_cmd):
        mock_run_cmd.return_value = (0, "all match", "")
        res = doctor.check_hook_catalog()
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "OK")

    @patch("doctor.run_cmd")
    def test_check_context_closure(self, mock_run_cmd):
        mock_run_cmd.return_value = (0, "budget ok", "")
        res = doctor.check_context_closure()
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "OK")

        mock_run_cmd.return_value = (1, "", "budget exceeded")
        res_fail = doctor.check_context_closure()
        self.assertFalse(res_fail["ok"])
        self.assertEqual(res_fail["status"], "FAIL")

    def test_strip_jsonc_comments(self):
        jsonc_sample = """{
            // Line comment
            "key": "value // not a comment",
            /* Block comment */
            "nested": {
                "num": 42 /* inline block */
            }
        }"""
        clean = doctor.strip_jsonc_comments(jsonc_sample)
        data = json.loads(clean)
        self.assertEqual(data["key"], "value // not a comment")
        self.assertEqual(data["nested"]["num"], 42)

    def test_strip_jsonc_trailing_commas(self):
        jsonc_with_trailing = """{
            "items": [
                1,
                2,
                3,
            ],
            "nested": {
                "a": "hello",
                "b": "world",
            },
            "quoted_comma": "keep this comma, inside string",
        }"""
        clean = doctor.strip_jsonc_comments(jsonc_with_trailing)
        data = json.loads(clean)
        self.assertEqual(data["items"], [1, 2, 3])
        self.assertEqual(data["nested"]["a"], "hello")
        self.assertEqual(data["nested"]["b"], "world")
        self.assertEqual(data["quoted_comma"], "keep this comma, inside string")

    def test_check_jsonc_configs_valid(self):
        res = doctor.check_jsonc_configs()
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "OK")
        self.assertGreater(res["checked_count"], 0)

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_file")
    def test_check_jsonc_configs_invalid(self, mock_is_file, mock_read_text):
        mock_is_file.return_value = True
        # Missing comma between keys -> invalid JSONC
        mock_read_text.return_value = '{\n  "provider": {}\n  "agent": {}\n}'
        res = doctor.check_jsonc_configs()
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("Invalid JSON/JSONC", res["details"])

    @patch("doctor.check_git_status")
    @patch("doctor.check_submodules")
    @patch("doctor.check_codex_wrappers")
    @patch("doctor.check_hook_catalog")
    @patch("doctor.check_context_closure")
    @patch("doctor.check_jsonc_configs")
    def test_run_doctor_healthy(self, m_jsonc, m_closure, m_hooks, m_wrappers, m_subm, m_git):
        m_git.return_value = {"name": "git_status", "ok": True, "status": "OK", "details": "ok"}
        m_subm.return_value = {"name": "submodules", "ok": True, "status": "OK", "details": "ok"}
        m_wrappers.return_value = {"name": "codex_wrappers", "ok": True, "status": "OK", "details": "ok"}
        m_hooks.return_value = {"name": "hook_catalog", "ok": True, "status": "OK", "details": "ok"}
        m_closure.return_value = {"name": "context_budget", "ok": True, "status": "OK", "details": "ok"}
        m_jsonc.return_value = {"name": "jsonc_configs", "ok": True, "status": "OK", "details": "ok"}

        report = doctor.run_doctor()
        self.assertTrue(report["all_ok"])
        self.assertEqual(report["overall_status"], "HEALTHY")

        text = doctor.format_text_report(report)
        self.assertIn("HEALTHY", text)
        self.assertIn("ai-config Doctor Diagnostic Report", text)


if __name__ == "__main__":
    unittest.main()
