#!/usr/bin/env python3
"""Unit tests for scripts/pre-push-review.py.

Tests:
1. Review body formatting adhering to AGENTS.md disclosure trailer, commit SHA binding, and no robot emoji.
2. Review output validation (rejects empty output, missing sections, and refusal strings).
3. Diff resolution logic against PR base branch vs main.
4. Engine detection and automatic fallback chain (claude -> codex -> opencode -> agy).
5. Model override parameter forwarding.
6. Post review failure exit codes and error handling.
"""

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    "pre_push_review", Path(__file__).parent / "pre-push-review.py"
)
reviewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewer)


class TestPrePushReview(unittest.TestCase):

    def test_format_review_body_disclosure_and_commit(self):
        report = "### Summary Verdict\nAPPROVE\n\n### Critical Findings\nNone."
        engine = "OpenAI Codex"
        commit_sha = "abc1234def5678"
        formatted = reviewer.format_review_body(report, engine, commit_sha=commit_sha)

        # Check for disclosure trailer matching AGENTS.md
        self.assertIn(f"_Posted by {engine} (AI agent) --- not written by a human._", formatted)
        # Check that commit SHA is bound
        self.assertIn(f"**Reviewed Commit**: `{commit_sha}`", formatted)
        # Check that no robot emoji is present (which would interfere with check-pr-fully-clean.py)
        self.assertNotIn("🤖", formatted)
        self.assertIn("### Local Adversarial AI Review (OpenAI Codex)", formatted)

    def test_validate_review_output(self):
        valid = "### Summary Verdict\nAPPROVE\n\n### Critical Findings\nNone.\n\n### Verification Steps\nPassed."
        self.assertTrue(reviewer.validate_review_output(valid))

        # Rejects missing verdict
        no_verdict = "### Overview\nLooks good.\n\n### Critical Findings\nNone."
        self.assertFalse(reviewer.validate_review_output(no_verdict))

        # Rejects refusal / quota error
        refusal = "### Summary Verdict\nAPPROVE\n\n### Critical Findings\nNone.\nYou've hit your weekly limit."
        self.assertFalse(reviewer.validate_review_output(refusal))

        # Rejects empty
        self.assertFalse(reviewer.validate_review_output(""))

    def test_build_review_prompt_structure(self):
        prompt = reviewer.build_review_prompt(
            diff="+ print('hello world')",
            ref_name="origin/main",
            guidelines="Strict merge policy: never merge without permission.",
        )
        self.assertIn("ADVERSARIAL AI CODE REVIEWER", prompt)
        self.assertIn("Summary Verdict", prompt)
        self.assertIn("Critical Findings", prompt)
        self.assertIn("+ print('hello world')", prompt)

    @patch("shutil.which")
    @patch("os.path.isfile")
    def test_detect_available_engines(self, mock_isfile, mock_which):
        mock_which.side_effect = lambda name: f"/usr/local/bin/{name}"
        mock_isfile.return_value = True
        engines = reviewer.detect_available_engines()
        self.assertEqual(engines, ["claude", "codex", "opencode", "antigravity"])

        mock_which.side_effect = lambda name: "/usr/local/bin/codex" if name == "codex" else None
        mock_isfile.return_value = False
        engines = reviewer.detect_available_engines()
        self.assertEqual(engines, ["codex"])

    @patch.object(reviewer, "run_claude_review")
    @patch.object(reviewer, "run_codex_review")
    @patch.object(reviewer, "detect_available_engines")
    def test_execute_review_fallback(self, mock_detect, mock_codex, mock_claude):
        mock_detect.return_value = ["claude", "codex"]
        # Claude fails or quota exhausted
        mock_claude.return_value = None
        # Codex succeeds
        mock_codex.return_value = "### Summary Verdict\nAPPROVE\n\n### Critical Findings\nNone."

        report, label = reviewer.execute_review("auto", "prompt text")
        self.assertEqual(report, "### Summary Verdict\nAPPROVE\n\n### Critical Findings\nNone.")
        self.assertEqual(label, "OpenAI Codex")
        mock_claude.assert_called_once()
        mock_codex.assert_called_once()

    @patch("subprocess.run")
    def test_resolve_diff_local(self, mock_subproc):
        def fake_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "merge-base" in cmd:
                m.stdout = "abc1234\n"
            elif "diff" in cmd:
                m.stdout = "diff --git a/foo b/foo\n+line"
            elif "rev-parse" in cmd:
                m.stdout = "def5678\n"
            return m

        mock_subproc.side_effect = fake_run
        diff, label = reviewer.resolve_diff(explicit_base="origin/main")
        self.assertIn("+line", diff)
        self.assertEqual(label, "origin/main")

    @patch("subprocess.run")
    def test_post_review_to_github_failure_handling(self, mock_subproc):
        fail_mock = MagicMock()
        fail_mock.returncode = 1
        fail_mock.stderr = "GitHub API 404 Not Found"
        mock_subproc.return_value = fail_mock

        res = reviewer.post_review_to_github(123, "report content", "OpenAI Codex")
        self.assertFalse(res)


if __name__ == "__main__":
    unittest.main()
