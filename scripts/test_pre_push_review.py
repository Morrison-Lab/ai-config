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
from unittest.mock import MagicMock, mock_open, patch

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
        self.assertIn("_Posted by Local Pre-push Review Hook (AI agent) --- not written by a human._", formatted)
        # Check that commit SHA is bound
        self.assertIn(f"**Reviewed Commit**: `{commit_sha}`", formatted)
        # Check that no robot emoji is present (which would interfere with check-pr-fully-clean.py)
        self.assertNotIn("🤖", formatted)
        self.assertIn("### Local Adversarial AI Review (OpenAI Codex)", formatted)

    def test_validate_review_output(self):
        commit = "12345678abcdef00"
        valid = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations & Non-Blocking Suggestions\n"
            "Looks clean and well-structured.\n\n"
            "### Verification Steps\n"
            "- All unit tests passed.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(valid, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean)

        # Test various explicit clean findings strings
        clean_findings = [
            "No critical findings.",
            "No blocking issues found.",
            "No issues found.",
            "Zero critical findings.",
            "None.",
            "No."
        ]
        for cf in clean_findings:
            cf_report = valid.replace("None.\n\n", cf + "\n\n")
            is_valid_cf, is_clean_cf, _ = reviewer.parse_review_verdict(cf_report, expected_commit_sha=commit)
            self.assertTrue(is_valid_cf, f"Failed on clean findings string: {cf}")
            self.assertTrue(is_clean_cf, f"Failed on clean findings string: {cf}")

        # Missing fingerprint when expected
        is_valid, _, reason = reviewer.parse_review_verdict(valid, expected_commit_sha="99999999")
        self.assertFalse(is_valid)
        self.assertIn("mismatch", reason)

        # Short fingerprint SHA rejected
        short_sha_report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            "Reviewed-Commit: b"
        )
        is_valid, _, reason = reviewer.parse_review_verdict(short_sha_report, expected_commit_sha="b2c4191f")
        self.assertFalse(is_valid)
        self.assertIn("mismatch", reason)

        # NOT APPROVED, DISAPPROVED, Never approve, Do not approve are NOT clean
        for neg in [
            "Verdict: NOT APPROVED.",
            "Verdict: DISAPPROVED.",
            "Verdict: UNAPPROVED.",
            "Verdict: BLOCKED.",
            "Verdict: NEEDS WORK.",
            "Verdict: CHANGES REQUESTED.",
            "Verdict: Not ready for merge.",
            "Verdict: Cannot approve",
            "Verdict: Never approve",
            "Verdict: Do not approve",
            "Verdict: Ready for merge — must not merge.",
            "Verdict: Ready for merge — should not be merged.",
            "Verdict: Ready for merge — unsafe to merge.",
            "Verdict: Ready for merge — not safe to merge.",
            "Verdict: Ready for merge — cannot merge.",
        ]:
            neg_report = (
                f"### Summary Verdict\n"
                f"{neg}\n\n"
                "### Critical Findings\n"
                "1. Bug found.\n\n"
                "### Observations\nNone.\n\n"
                "### Verification Steps\nNone."
            )
            is_valid, is_clean, _ = reviewer.parse_review_verdict(neg_report)
            self.assertTrue(is_valid)
            self.assertFalse(is_clean)

        # "safe to merge" should NOT be caught as a blocker
        safe_to_merge_report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge.\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nThe reviewed change is safe to merge.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(safe_to_merge_report, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean, msg=f"Should be clean but failed with: {reason}")

        # Extended heading with blockers: ### Critical Findings (blocking) is caught
        extended_heading_report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings (blocking)\n"
            "1. Major data loss on unverified commit.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone."
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(extended_heading_report)
        self.assertFalse(is_clean)

        # Prefix collisions and unknown verdicts are rejected as invalid (is_valid=False)
        for invalid_v in ["Ready for merger", "Ready for merge someday", "banana", "POTATO", "Almost ready"]:
            inv_report = (
                f"### Summary Verdict\n"
                f"Verdict: {invalid_v}\n\n"
                "### Critical Findings\n"
                "None.\n\n"
                "### Observations\nNone.\n\n"
                "### Verification Steps\nNone.\n"
                f"Reviewed-Commit: {commit}"
            )
            is_valid, is_clean, reason = reviewer.parse_review_verdict(inv_report, expected_commit_sha=commit)
            self.assertFalse(is_valid)
            self.assertIn("Unrecognized", reason)

        # Qualified verdicts with valid rationale are parsed correctly
        rationale_report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge \u2014 all tests pass and documentation is verified.\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(rationale_report, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean)

        # None. followed by numbered blocker is NOT clean
        sneaky_findings = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n"
            "1. Must fix before merge: data loss.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone."
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(sneaky_findings)
        self.assertFalse(is_clean)

        # Full-length fingerprint mismatch with 7 matching chars but differing suffix is rejected
        is_valid, is_clean, reason = reviewer.parse_review_verdict(
            "### Summary Verdict\nVerdict: Ready for merge\n\n### Critical Findings\nNone.\n\n### Observations\nNone.\n\n### Verification Steps\nNone.\nReviewed-Commit: 1234567fdeadbeef",
            expected_commit_sha="12345678abcdef00",
        )
        self.assertFalse(is_valid)
        self.assertIn("mismatch", reason)

        # Contradictory fingerprints in the same report (one matching, one differing) is rejected
        contradictory_report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}\n"
            "Reviewed-Commit: deadbeef12345678"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(contradictory_report, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertIn("mismatch", reason)

        # Clean verdict followed by Needs work verdict yields is_clean=False
        multiple_verdicts_report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Summary Verdict\n"
            "Verdict: Needs work \u2014 bug found\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(multiple_verdicts_report, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertFalse(is_clean)

        # Initial clean Critical Findings followed by a second blocking Critical Findings yields is_clean=False
        multiple_findings_report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Critical Findings\n"
            "1. Major regression in workflow.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(multiple_findings_report, expected_commit_sha=commit)
        self.assertFalse(is_clean)

        # Clean verdict with rationale without negative words is accepted as clean
        clean_with_rationale = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge \u2014 CI passed cleanly.\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(clean_with_rationale, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean)

        # Contradictory rationale fails the review
        contradictory_rationale = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge \u2014 do not merge.\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(contradictory_rationale, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertFalse(is_clean)

        # Report entirely inside a backtick code fence is rejected as missing top-level structure
        fenced_report = (
            "```markdown\n"
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}\n"
            "```"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(fenced_report, expected_commit_sha=commit)
        self.assertFalse(is_valid)

        # Empty Critical Findings section is rejected as invalid
        empty_findings_report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(empty_findings_report, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertIn("cannot be empty", reason)

        # Report with an unbalanced/unterminated code fence is rejected
        unterminated_fence_report = (
            "```markdown\n"
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(unterminated_fence_report, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertIn("Unbalanced or unterminated", reason)

        # Report entirely inside a tilde code fence is also rejected
        tilde_fenced_report = (
            "~~~markdown\n"
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}\n"
            "~~~"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(tilde_fenced_report, expected_commit_sha=commit)
        self.assertFalse(is_valid)

        # Mixed fences (outer backtick containing inner tildes) are rejected
        mixed_fence_report = (
            "```markdown\n"
            "~~~markdown\n"
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}\n"
            "~~~\n"
            "```"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(mixed_fence_report, expected_commit_sha=commit)
        self.assertFalse(is_valid)

        # Nested same-character fences (4-backtick outer wrapping 3-backtick inner) are rejected
        nested_same_char_report = (
            "````markdown\n"
            "```markdown\n"
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}\n"
            "```\n"
            "````"
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(nested_same_char_report, expected_commit_sha=commit)
        self.assertFalse(is_valid)

        # Adversarial wording inside findings (contains "None" in sentence but lists numbered blocker)
        adv_findings = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "## Critical Findings\n"
            "1. None of the posting paths verify the SHA; must fix before merge.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone."
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(adv_findings)
        self.assertFalse(is_clean)

        # Contradictory report with clean Critical Findings but blocker in Observations is rejected
        obs_blocker_report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\n"
            "BLOCKING: data loss occurs on unhandled error.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(obs_blocker_report, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertIn("Contradictory output", reason)

        # Contradictory report with 'must be fixed before merge'
        obs_must_fix_report = (
            "### Summary Verdict\n"
            "Verdict: CLEAN\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\n"
            "This must be fixed before merge.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(obs_must_fix_report, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertIn("Contradictory output", reason)

        # Rejects contradictory APPROVE with critical blocker
        contradictory = (
            "### Summary Verdict\n"
            "Verdict: APPROVE\n\n"
            "### Critical Findings\n"
            "1. Severe blocking bug in execution pipeline.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone."
        )
        is_valid, is_clean, _ = reviewer.parse_review_verdict(contradictory)
        self.assertFalse(is_valid)

        # Rejects missing required section (missing Verification Steps)
        missing_section = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\n"
            "None."
        )
        is_valid, _, _ = reviewer.parse_review_verdict(missing_section)
        self.assertFalse(is_valid)

        # Rejects refusal / quota error
        refusal = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            "You've hit your weekly limit."
        )
        is_valid, _, _ = reviewer.parse_review_verdict(refusal)
        self.assertFalse(is_valid)

        # Rejects empty
        is_valid, _, _ = reviewer.parse_review_verdict("")
        self.assertFalse(is_valid)

    @patch("subprocess.run")
    def test_build_review_prompt_structure(self, mock_run):
        mock_run.return_value = MagicMock(stdout="feature-branch\n", returncode=0)

        prompt = reviewer.build_review_prompt(
            diff="+ print('hello world')",
            ref_name="origin/main",
            guidelines="Strict merge policy: never merge without permission.",
            head_sha="00000000"
        )
        self.assertIn("ADVERSARIAL AI CODE REVIEWER", prompt)
        self.assertIn("Context: feature-branch (diff against origin/main)", prompt)
        self.assertIn("Strict merge policy: never merge without permission.", prompt)
        self.assertIn("+ print('hello world')", prompt)
        self.assertIn("Reviewed-Commit: 00000000", prompt)

    @patch("os.path.isfile", return_value=True)
    @patch("shutil.which", return_value=True)
    def test_detect_available_engines(self, mock_which, mock_isfile):
        engines = reviewer.detect_available_engines()
        self.assertEqual(engines, ["claude", "cursor", "codex", "opencode", "antigravity"])


    @patch.object(reviewer, "run_claude_review")
    @patch.object(reviewer, "run_codex_review")
    @patch.object(reviewer, "detect_available_engines")
    def test_execute_review_fallback(self, mock_detect, mock_codex, mock_claude):
        mock_detect.return_value = ["claude", "codex"]
        # Claude fails or quota exhausted
        mock_claude.return_value = None
        # Codex succeeds
        mock_codex.return_value = (
            "### Summary Verdict\nVerdict: Ready for merge\n\n"
            "### Critical Findings\nNone.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nPassed."
        )

        report, label = reviewer.execute_review("auto", "prompt text")
        self.assertEqual(report, mock_codex.return_value)
        self.assertEqual(label, "OpenAI Codex")
        mock_claude.assert_called_once()
        mock_codex.assert_called_once()
    @patch.object(reviewer, "run_claude_review")
    @patch.object(reviewer, "run_codex_review")
    @patch.object(reviewer, "detect_available_engines")
    def test_execute_review_alternate_invoker_exclusion(self, mock_detect, mock_codex, mock_claude):
        mock_detect.return_value = ["claude", "codex"]
        mock_codex.return_value = "### Summary Verdict\nVerdict: Ready for merge"
        mock_claude.return_value = "### Summary Verdict\nVerdict: Ready for merge"

        # When CLAUDE_SESSION_ID is set, Claude is excluded from 'alternate'
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "12345"}, clear=True):
            with patch.object(reviewer, "get_next_alternate_engine", return_value="codex") as mock_get_next:
                reviewer.execute_review("alternate", "prompt text")
                mock_get_next.assert_called_with(["codex"])

        # When ANTIGRAVITY_AGENT is set, antigravity is excluded
        mock_detect.return_value = ["claude", "antigravity"]
        with patch.dict(os.environ, {"ANTIGRAVITY_AGENT": "1"}, clear=True):
            with patch.object(reviewer, "get_next_alternate_engine", return_value="claude") as mock_get_next:
                reviewer.execute_review("alternate", "prompt text")
                mock_get_next.assert_called_with(["claude"])

        # When Cursor is set via AGENT_NAME, cursor is excluded
        mock_detect.return_value = ["claude", "cursor"]
        with patch.dict(os.environ, {"AGENT_NAME": "Cursor Grok 4.6"}, clear=True):
            with patch.object(reviewer, "get_next_alternate_engine", return_value="claude") as mock_get_next:
                reviewer.execute_review("alternate", "prompt text")
                mock_get_next.assert_called_with(["claude"])

        # When OPENCODE_SESSION_ID is set, opencode is excluded
        mock_detect.return_value = ["claude", "opencode"]
        with patch.dict(os.environ, {"OPENCODE_SESSION_ID": "123"}, clear=True):
            with patch.object(reviewer, "get_next_alternate_engine", return_value="claude") as mock_get_next:
                reviewer.execute_review("alternate", "prompt text")
                mock_get_next.assert_called_with(["claude"])

        # When CODEX_THREAD_ID is set and only codex is available, it fails and returns None
        mock_detect.return_value = ["codex"]
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "67890"}, clear=True):
            with patch.object(reviewer, "log_error") as mock_log_error:
                report, label = reviewer.execute_review("alternate", "prompt text")
                self.assertIsNone(report)
                mock_log_error.assert_called_with("No alternate AI CLI found (invoking agents ['codex'] were excluded).")

        # When multiple harness markers coexist, ALL are excluded
        mock_detect.return_value = ["claude", "codex", "antigravity"]
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "111", "ANTIGRAVITY_AGENT": "1"}, clear=True):
            with patch.object(reviewer, "get_next_alternate_engine", return_value="claude") as mock_get_next:
                reviewer.execute_review("alternate", "prompt text")
                mock_get_next.assert_called_with(["claude"])

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
        diff, label = reviewer.resolve_diff("head123", explicit_base="origin/main")
        self.assertIn("+line", diff)
        self.assertEqual(label, "origin/main")

    @patch("subprocess.run")
    @patch.object(reviewer, "get_pr_head_sha")
    def test_post_review_empty_commit_sha_fails_closed(self, mock_get_sha, mock_subproc):
        mock_get_sha.return_value = "remote_sha_9999"
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_subproc.return_value = mock_res

        res = reviewer.post_review_to_github(
            pr_number=123,
            report="### Summary Verdict\nVerdict: Ready for merge",
            engine_name="OpenAI Codex",
            commit_sha="",
        )
        self.assertFalse(res)
        mock_subproc.assert_not_called()

    @patch("subprocess.run")
    @patch.object(reviewer, "get_pr_head_sha")
    def test_post_review_differing_head_sha_fails_closed(self, mock_get_sha, mock_subproc):
        mock_get_sha.return_value = "remote_sha_9999"
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_subproc.return_value = mock_res

        res = reviewer.post_review_to_github(
            pr_number=123,
            report="### Summary Verdict\nVerdict: Ready for merge\n\n### Critical Findings\nNone.\n\n### Observations\nNone.\n\n### Verification Steps\nPassed.",
            engine_name="OpenAI Codex",
            commit_sha="local_sha_1111",
        )
        self.assertFalse(res)
        mock_subproc.assert_not_called()

    @patch("subprocess.run")
    @patch.object(reviewer, "get_pr_head_sha")
    def test_post_review_unresolved_remote_sha_fails_closed(self, mock_get_sha, mock_subproc):
        mock_get_sha.return_value = None  # Failed to fetch remote PR head SHA
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_subproc.return_value = mock_res

        res = reviewer.post_review_to_github(
            pr_number=123,
            report="### Summary Verdict\nVerdict: Ready for merge\n\n### Critical Findings\nNone.\n\n### Observations\nNone.\n\n### Verification Steps\nPassed.",
            engine_name="OpenAI Codex",
            commit_sha="local_sha_1111",
        )
        self.assertFalse(res)
        mock_subproc.assert_not_called()

    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_runner_model_forwarding(self, mock_which, mock_subproc, mock_tf):
        mock_file = MagicMock()
        mock_file.name = "/tmp/mockfile"
        mock_tf.return_value.__enter__.return_value = mock_file

        mock_which.return_value = "/opt/homebrew/bin/codex"
        valid_report = (
            "### Summary Verdict\nVerdict: Ready for merge\n\n"
            "### Critical Findings\nNone.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            "Reviewed-Commit: abc12345"
        )
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = valid_report
        mock_subproc.return_value = mock_res

        out = reviewer.run_codex_review("prompt", model="gpt-5.6-sol", expected_commit_sha="abc12345")
        self.assertEqual(out, valid_report)
        cmd_args = mock_subproc.call_args[0][0]
        self.assertIn("-m", cmd_args)
        self.assertIn("gpt-5.6-sol", cmd_args)

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.unlink")
    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_all_runners_cli_contracts(self, mock_which, mock_subproc, mock_tf, mock_unlink, mock_file_open):
        mock_file = MagicMock()
        mock_file.name = "/tmp/mockfile"
        mock_tf.return_value.__enter__.return_value = mock_file

        valid_report = (
            "### Summary Verdict\nVerdict: Ready for merge\n\n"
            "### Critical Findings\nNone.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\nNone.\n"
            "Reviewed-Commit: abc12345"
        )
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = valid_report
        mock_subproc.return_value = mock_res

        # Test Claude runner
        mock_which.return_value = "/opt/homebrew/bin/claude"
        out_claude = reviewer.run_claude_review("prompt", model="claude-3-5-sonnet", expected_commit_sha="abc12345")
        self.assertEqual(out_claude, valid_report)
        claude_cmd = mock_subproc.call_args[0][0]
        self.assertIn("--model", claude_cmd)
        self.assertIn("claude-3-5-sonnet", claude_cmd)

        # Test Cursor runner
        mock_which.return_value = "/opt/homebrew/bin/agent"
        out_cursor = reviewer.run_cursor_review("prompt", model="claude-3.7-sonnet", expected_commit_sha="abc12345")
        self.assertEqual(out_cursor, valid_report)
        cursor_cmd = mock_subproc.call_args[0][0]
        self.assertIn("--trust", cursor_cmd)
        self.assertIn("--print", cursor_cmd)
        self.assertEqual(mock_subproc.call_args[1].get("input"), "prompt")

        # Test Antigravity runner
        mock_which.return_value = "/opt/homebrew/bin/agy"
        out_agy = reviewer.run_antigravity_review("prompt", model="claude-3-7-sonnet", expected_commit_sha="abc12345")
        self.assertEqual(out_agy, valid_report)
        agy_cmd = mock_subproc.call_args[0][0]
        self.assertIn("--model", agy_cmd)
        self.assertIn("claude-3-7-sonnet", agy_cmd)

        # Test OpenCode runner uses bounded file mechanism
        mock_which.return_value = "/opt/homebrew/bin/opencode"
        out_oc = reviewer.run_opencode_review("prompt", model="anthropic/claude-3.7-sonnet", expected_commit_sha="abc12345")
        self.assertEqual(out_oc, valid_report)
        oc_cmd = mock_subproc.call_args[0][0]
        self.assertIn("--pure", oc_cmd)
        self.assertIn("--file", oc_cmd)
        self.assertNotIn("prompt", oc_cmd)
        self.assertIn("-m", oc_cmd)
        self.assertIn("anthropic/claude-3.7-sonnet", oc_cmd)

    def test_get_next_alternate_engine_rotation(self):
        engines = ["claude", "cursor", "codex", "opencode", "antigravity"]
        # When no prior state exists, starts with first available engine
        with patch("os.path.isfile", return_value=False):
            e1 = reviewer.get_next_alternate_engine(engines)
            self.assertEqual(e1, "claude")

        # When last engine was claude, next is cursor
        with patch("os.path.isfile", return_value=True), patch("builtins.open", mock_open(read_data='{"last_engine_name": "claude"}')):
            e2 = reviewer.get_next_alternate_engine(engines)
            self.assertEqual(e2, "cursor")

        # When last engine was cursor, next is codex
        with patch("os.path.isfile", return_value=True), patch("builtins.open", mock_open(read_data='{"last_engine_name": "cursor"}')):
            e3 = reviewer.get_next_alternate_engine(engines)
            self.assertEqual(e3, "codex")

        # When last engine was antigravity, wraps around to claude
        with patch("os.path.isfile", return_value=True), patch("builtins.open", mock_open(read_data='{"last_engine_name": "antigravity"}')):
            e4 = reviewer.get_next_alternate_engine(engines)
            self.assertEqual(e4, "claude")

        # When next engine in order is not available, skips to next available
        with patch("os.path.isfile", return_value=True), patch("builtins.open", mock_open(read_data='{"last_engine_name": "claude"}')):
            subset_engines = ["claude", "antigravity"]
            e5 = reviewer.get_next_alternate_engine(subset_engines)
            self.assertEqual(e5, "antigravity")


    @patch.object(reviewer, "get_pr_head_sha")
    @patch("subprocess.run")
    def test_post_review_to_github_failure_handling(self, mock_subproc, mock_get_sha):
        mock_get_sha.return_value = "12345678"
        fail_mock = MagicMock()
        fail_mock.returncode = 1
        fail_mock.stderr = "GitHub API 404 Not Found"
        mock_subproc.return_value = fail_mock

        res = reviewer.post_review_to_github(123, "report content", "OpenAI Codex", commit_sha="12345678")
        self.assertFalse(res)
        mock_subproc.assert_called_once()


if __name__ == "__main__":
    unittest.main()
