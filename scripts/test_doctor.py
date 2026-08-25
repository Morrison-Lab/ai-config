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
    def test_check_consumer_installs(self, mock_run_cmd):
        mock_run_cmd.return_value = (0, "ok", "")
        res = doctor.check_consumer_installs()
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], "OK")

        mock_run_cmd.return_value = (1, "stale entries found", "")
        res_warn = doctor.check_consumer_installs()
        self.assertFalse(res_warn["ok"])
        self.assertEqual(res_warn["status"], "WARN")

    @patch("doctor.check_git_status")
    @patch("doctor.check_submodules")
    @patch("doctor.check_codex_wrappers")
    @patch("doctor.check_hook_catalog")
    @patch("doctor.check_consumer_installs")
    def test_run_doctor_healthy(self, m_installs, m_hooks, m_wrappers, m_subm, m_git):
        m_git.return_value = {"name": "git_status", "ok": True, "status": "OK", "details": "ok"}
        m_subm.return_value = {"name": "submodules", "ok": True, "status": "OK", "details": "ok"}
        m_wrappers.return_value = {"name": "codex_wrappers", "ok": True, "status": "OK", "details": "ok"}
        m_hooks.return_value = {"name": "hook_catalog", "ok": True, "status": "OK", "details": "ok"}
        m_installs.return_value = {"name": "consumer_install", "ok": True, "status": "OK", "details": "ok"}

        report = doctor.run_doctor()
        self.assertTrue(report["all_ok"])
        self.assertEqual(report["overall_status"], "HEALTHY")

        text = doctor.format_text_report(report)
        self.assertIn("HEALTHY", text)
        self.assertIn("ai-config Doctor Diagnostic Report", text)


if __name__ == "__main__":
    unittest.main()
