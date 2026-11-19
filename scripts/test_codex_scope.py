#!/usr/bin/env python3
"""Tests for scripts/lib/codex_scope.py (ai-config#5084)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.lib.codex_scope import OVERRIDE_ENV, codex_allowed  # noqa: E402


class TestCodexAllowed(unittest.TestCase):

    def test_ucdh_remotes_allowed(self):
        for url in (
            "https://github.com/ucdavis/bcs",
            "https://github.com/ucdavis/bcs.git",
            "git@github.com:ucdavis/hac-reports.git",
            "https://github.com/UCDavis/hac.dashboard",
            "git@hc2-gitlab.ucdmc.ucdavis.edu:health-analytics-core/abridge.git",
            "https://hc2-gitlab.ucdmc.ucdavis.edu/bcs/pipeline",
            "https://hc2-gitlab.ucdmc.ucdavis.edu/health-analytics-core/sub/proj",
            "ssh://git@github.com:22/ucdavis/hac.git",
            "ssh://git@hc2-gitlab.ucdmc.ucdavis.edu:2222/bcs/x.git",
        ):
            with self.subTest(url=url), patch.dict(os.environ, {}, clear=True):
                self.assertTrue(codex_allowed(remote_url=url))

    def test_other_remotes_refused(self):
        for url in (
            "https://github.com/Morrison-Lab/ai-config",
            "https://github.com/Morrison-Lab/bcs-notes",
            "https://github.com/ucdavis/other-repo",
            "https://github.com/someone/hac",
            "https://gitlab.com/bcs/project",
            "https://gitlab.com/ucdavis/bcs",
            "https://evil.example.com/ucdavis/hac",
            "https://hc2-gitlab.ucdmc.ucdavis.edu.evil.com/bcs/x",
            "https://evil.github.com/ucdavis/hac",
            "https://notgithub.com/ucdavis/hac",
            "https://evil.com/hc2-gitlab.ucdmc.ucdavis.edu/bcs/x",
            "https://github.com/ucdavis/bcs/extra",
            "https://hc2-gitlab.ucdmc.ucdavis.edu/",
            "https://hc2-gitlab.ucdmc.ucdavis.edu/some-other-team/proj",
            "git@hc2-gitlab.ucdmc.ucdavis.edu:bcs.git",
            "https://hc2-gitlab.ucdmc.ucdavis.edu/bcsx/proj",
            "/home/user/local-clone",
            "",
        ):
            with self.subTest(url=url), patch.dict(os.environ, {}, clear=True):
                self.assertFalse(codex_allowed(remote_url=url))

    def test_override_wins_both_ways(self):
        with patch.dict(os.environ, {OVERRIDE_ENV: "1"}, clear=True):
            self.assertTrue(codex_allowed(remote_url="https://github.com/Morrison-Lab/lds"))
        with patch.dict(os.environ, {OVERRIDE_ENV: "0"}, clear=True):
            self.assertFalse(codex_allowed(remote_url="https://github.com/ucdavis/bcs"))

    def test_unreadable_remote_refuses(self):
        # Scrub only the override, so `git` stays on PATH.
        env = {k: v for k, v in os.environ.items() if k != OVERRIDE_ENV}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(codex_allowed(repo_dir="/nonexistent-dir-for-codex-scope-test"))

    def test_missing_git_refuses(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "scripts.lib.codex_scope.subprocess.run", side_effect=FileNotFoundError("git")
        ):
            self.assertFalse(codex_allowed())


if __name__ == "__main__":
    unittest.main()
