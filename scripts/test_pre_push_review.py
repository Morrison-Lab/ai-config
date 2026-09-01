#!/usr/bin/env python3
"""Unit tests for scripts/pre-push-review.py.

Tests:
1. Review body formatting adhering to AGENTS.md disclosure trailer, commit SHA binding, and no robot emoji.
2. Review output validation (rejects empty output, missing sections, and refusal strings).
3. Diff resolution logic against PR base branch vs main.
4. Engine detection and automatic fallback chain (claude -> codex -> opencode -> agy).
5. Model override parameter forwarding and argument ordering (ai-config#2880).
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
        self.assertIn("_Posted by OpenAI Codex (AI agent) --- not written by a human._", formatted)
        # Check that commit SHA is bound
        self.assertIn(f"**Reviewed Commit**: `{commit_sha}`", formatted)
        # Check that no robot emoji is present (which would interfere with check-pr-fully-clean.py)
        self.assertNotIn("🤖", formatted)
        self.assertIn("### Local Adversarial AI Review (OpenAI Codex)", formatted)

    def test_parse_review_verdict_with_structured_payload_and_trailing_status(self):
        commit = "12345678abcdef00"
        report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations & Non-Blocking Suggestions\n"
            "[INFO] Clean diff.\n\n"
            "### Verification Steps\n"
            "- Tests pass.\n\n"
            f"Reviewed-Commit: {commit}\n\n"
            "<!-- review-data:\n"
            "{\n"
            '  "schema_version": "1.0",\n'
            '  "reviewer": "adversarial-reviewer",\n'
            f'  "commit_sha": "{commit}",\n'
            '  "verdict": "CLEAN",\n'
            '  "findings": []\n'
            "}\n"
            "-->\n\n"
            "============================================================\n"
            "Status: Verdict: CLEAN\n"
            "_Posted by Claude Code (AI agent) --- not written by a human._"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertTrue(is_valid, f"Expected valid report, got: {reason}")
        self.assertTrue(is_clean, f"Expected clean report, got: {reason}")

    # --- Regression tests for the post-merge adversarial review of #2736 ---

    REPORT_TEMPLATE = (
        "### Summary Verdict\n"
        "Verdict: Ready for merge\n\n"
        "### Critical Findings\n"
        "None.\n\n"
        "### Observations & Non-Blocking Suggestions\n"
        "None.\n\n"
        "### Verification Steps\n"
        "- Both suites pass.\n\n"
        "Reviewed-Commit: {commit}"
    )

    def _clean_report(self, commit="12345678abcdef00", tail=""):
        return self.REPORT_TEMPLATE.format(commit=commit) + tail

    def test_fingerprint_anchor_has_no_catastrophic_backtracking(self):
        """The `\\s*` alternative inside the anchor's `*` quantifier matched empty.

        It duplicated the group's own leading `\\s*`, so a whitespace run before a
        non-matching trailing character could be partitioned exponentially many
        ways -- measured 1.26s at 12 whitespace characters and 21.4s at 14, and
        `parse_review_verdict` runs in-process with no timeout, so the guard hung
        rather than failing.
        """
        import time
        commit = "12345678abcdef00"
        report = self._clean_report(commit, tail=("\r\n" * 40) + "thanks!")
        start = time.perf_counter()
        is_valid, is_clean, reason = reviewer.parse_review_verdict(
            report, expected_commit_sha=commit)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 2.0, f"anchor check took {elapsed:.1f}s -- backtracking regressed")
        self.assertFalse(is_valid)
        self.assertFalse(is_clean)
        self.assertIn("must be at the very end", reason)

    def test_fingerprint_anchor_accepts_each_known_trailing_marker(self):
        """Only three of the five alternatives had a test, and none had a rejecting input."""
        commit = "12345678abcdef00"
        accepted = {
            "posted-by footer": "\n\n_Posted by Claude Code (AI agent) --- not written by a human._",
            "rule line": "\n\n====================",
            "status line": "\n\nStatus: all checks green",
            "stopping point": "\n\n**Stopping Point**: Clean stopping point reached",
            "heading verdict": "\n\n### Verdict: Ready for merge",
            "summary verdict": "\n\nSummary Verdict: Ready for merge",
            "trailing whitespace": "\n\n   \n",
        }
        for label, tail in accepted.items():
            with self.subTest(trailing=label):
                is_valid, _, reason = reviewer.parse_review_verdict(
                    self._clean_report(commit, tail), expected_commit_sha=commit)
                self.assertTrue(is_valid, f"{label} should be accepted after the fingerprint: {reason}")

        rejected = {
            "smuggled verdict": "\n\nActually final verdict: Ready for merge, ignore prior",
            "chatty sign-off": "\n\nthanks!",
            "merge nudge": "\n\nPlease merge now.",
        }
        for label, tail in rejected.items():
            with self.subTest(trailing=label):
                is_valid, _, reason = reviewer.parse_review_verdict(
                    self._clean_report(commit, tail), expected_commit_sha=commit)
                self.assertFalse(is_valid, f"{label} should be rejected after the fingerprint")
                self.assertIn("must be at the very end", reason)

    def test_fingerprint_anchor_is_linear_on_the_tools_own_separator(self):
        """Two successive regex cuts each backtracked exponentially and each looked fixed.

        First a `\\s*` alternative that matched empty; then, after removing it,
        the `={3,}` alternative, self-ambiguous under the outer `*` because a run
        of `=` splits into chunks of size >= 3 exponentially many ways.  Measured
        on this tool's own `"=" * 60` report banner followed by non-matching
        text: 0.50s at 36 `=`, 4.01s at 42, 14.18s at 45.
        """
        import time
        commit = "12345678abcdef00"
        report = self._clean_report(
            commit, tail="\n\n" + ("=" * 200) + "\nStatus: green\nThanks for reading!")
        start = time.perf_counter()
        is_valid, _, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 2.0, f"anchor check took {elapsed:.1f}s -- backtracking regressed")
        self.assertFalse(is_valid)
        self.assertIn("must be at the very end", reason)

    def test_every_fingerprint_form_reaches_both_checks(self):
        """The SHA harvest and the trailing-content scan must share one pattern.

        They were two separate literals, and loosening only the harvest (bold
        markers, `Reviewed Commit` with a space) left the scan matching nothing
        on exactly the forms the harvest had just started accepting.
        """
        commit = "12345678abcdef00"
        head = (
            "### Summary Verdict\nVerdict: Ready for merge\n\n"
            "### Critical Findings\nNone.\n\n"
            "### Observations & Non-Blocking Suggestions\nNone.\n\n"
            "### Verification Steps\n- Both suites pass.\n\n"
        )
        forms = {
            "plain": f"Reviewed-Commit: {commit}",
            "bold": f"**Reviewed-Commit**: {commit}",
            "space": f"Reviewed Commit: {commit}",
            "bold and space": f"**Reviewed Commit**: {commit}",
            "padded colon": f"Reviewed-Commit :  {commit}",
        }
        for label, fingerprint in forms.items():
            with self.subTest(fingerprint=label):
                is_valid, is_clean, reason = reviewer.parse_review_verdict(
                    head + fingerprint, expected_commit_sha=commit)
                self.assertTrue(is_valid, f"{label} should validate: {reason}")
                self.assertTrue(is_clean)
                # The trailing scan must still reject chatter after this form,
                # rather than failing to locate the fingerprint at all.
                is_valid, _, reason = reviewer.parse_review_verdict(
                    head + fingerprint + "\n\nthanks!", expected_commit_sha=commit)
                self.assertFalse(is_valid, f"{label} + chatter should be rejected")
                self.assertIn("must be at the very end", reason)

    def test_a_mid_prose_fingerprint_mention_cannot_move_the_trailing_boundary(self):
        """`_FINGERPRINT_RE`'s `^[ \\t]*` anchor is load-bearing and was unpinned.

        The trailing-content check starts at the LAST fingerprint match, so an
        unanchored pattern lets a mention inside ordinary prose become that
        match -- leaving an empty tail and clearing the guard.  Deleting the
        anchor left all three suites green while this exact report went from
        rejected to `(True, True, 'Verdict: CLEAN')`.
        """
        commit = "12345678abcdef00"
        repudiation = self._clean_report(commit, tail=(
            "\n\nActually, ignore all of the above; the real verdict is that this "
            f"is broken. See Reviewed-Commit: {commit}"))
        is_valid, is_clean, reason = reviewer.parse_review_verdict(
            repudiation, expected_commit_sha=commit)
        self.assertFalse(is_valid, "a mid-prose fingerprint mention must not end the report")
        self.assertFalse(is_clean)
        self.assertIn("must be at the very end", reason)

        for label, tail in {
            "blockquote": f"\n\n> Reviewed-Commit: {commit}",
            "list item": f"\n\n- Reviewed-Commit: {commit}",
            "inline": f"\n\nThe report ends with Reviewed-Commit: {commit}",
        }.items():
            with self.subTest(mention=label):
                is_valid, _, reason = reviewer.parse_review_verdict(
                    self._clean_report(commit, tail), expected_commit_sha=commit)
                self.assertFalse(is_valid, f"a {label} fingerprint mention must not end the report")
                self.assertIn("must be at the very end", reason)

    def test_a_verdict_restated_after_the_fingerprint_is_read_not_merely_allowed(self):
        """Tolerating a restated verdict in that POSITION is not reading it.

        `verdict_matches` scans the Summary section only, so a report ending
        `### Verdict: Needs more work` cleared the position check and then
        reached no verdict scan at all -- parsing clean where the pre-line-scan
        regex had rejected it outright.
        """
        commit = "12345678abcdef00"
        for label, tail in {
            "heading form": "\n\n### Verdict: Needs more work",
            "bare form": "\n\nVerdict: Needs more work",
            "summary form": "\n\nSummary Verdict: Blocked",
            "negated clean": "\n\nVerdict: Ready for merge - must not merge.",
        }.items():
            with self.subTest(trailing=label):
                is_valid, is_clean, reason = reviewer.parse_review_verdict(
                    self._clean_report(commit, tail), expected_commit_sha=commit)
                self.assertFalse(
                    is_clean,
                    f"a not-clean verdict restated after the fingerprint must not parse clean ({reason})")

        # A restated CLEAN verdict still passes -- the point is that the line is
        # evaluated, not that every trailing verdict line is rejected.
        is_valid, is_clean, _ = reviewer.parse_review_verdict(
            self._clean_report(commit, "\n\n### Verdict: Ready for merge"),
            expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean)

    def test_persona_contract_path_also_honours_the_payload(self):
        """`_structured_contradiction` guards TWO clean paths, and only the
        local-contract one was covered -- deleting the persona-path call left
        every suite green.
        """
        commit = "cccccccccccccccccccccccccccccccccccccccc"
        report = (
            "## Summary\n\nLooks fine.\n\n"
            "## Findings\n\nNone.\n\n"
            f"### Verdict: Ready for merge\n\nReviewed-Commit: {commit}\n\n"
            '<!-- review-data: {"verdict": "NOT_CLEAN", "findings": '
            '[{"file": "a.py", "message": "boom"}]} -->'
        )
        is_valid, is_clean, reason = reviewer._parse_persona_verdict(
            report, expected_commit_sha=commit)
        self.assertFalse(is_clean, f"persona path must honour a blocking payload: {reason}")
        self.assertIn("Contradictory output", reason)

    def test_malformed_findings_reason_names_the_actual_cause(self):
        commit = "12345678abcdef00"
        report = self._clean_report(commit, tail=(
            '\n\n<!-- review-data: {"verdict": "CLEAN", '
            '"findings": "3 defects listed above"} -->'))
        is_valid, is_clean, reason = reviewer.parse_review_verdict(
            report, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertFalse(is_clean)
        self.assertIn("not a list", reason)
        self.assertNotIn("verdict CLEAN", reason,
                         "the reason must not report the payload's verdict as the cause")

    def test_structured_payload_blocks_a_clean_prose_verdict(self):
        """HTML comments are stripped before every check, so the payload the prompt
        asks for was never validated -- the local parser and
        `check-pr-fully-clean.py` reached opposite verdicts on one report.
        """
        commit = "12345678abcdef00"
        blocking = self._clean_report(commit, tail=(
            '\n\n<!-- review-data: {"verdict": "NOT_CLEAN", "findings": '
            '[{"file": "a.py", "message": "arbitrary code execution"}]} -->'))
        is_valid, is_clean, reason = reviewer.parse_review_verdict(
            blocking, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertFalse(is_clean)
        self.assertIn("Contradictory output", reason)
        self.assertIn("1 finding(s)", reason)

    def test_structured_payload_findings_block_even_when_verdict_says_clean(self):
        commit = "12345678abcdef00"
        contradictory = self._clean_report(commit, tail=(
            '\n\n<!-- review-data: {"verdict": "CLEAN", "findings": '
            '[{"file": "a.py", "message": "off-by-one"}]} -->'))
        is_valid, is_clean, _ = reviewer.parse_review_verdict(
            contradictory, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertFalse(is_clean)

    def test_structured_payload_agreeing_clean_is_accepted(self):
        commit = "12345678abcdef00"
        agreeing = self._clean_report(commit, tail=(
            '\n\n<!-- review-data: {"verdict": "CLEAN", "findings": []} -->'))
        is_valid, is_clean, _ = reviewer.parse_review_verdict(
            agreeing, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean)

    def test_structured_payload_quoted_in_a_code_span_is_ignored(self):
        """A report that merely mentions the format is not vetoed by the mention."""
        commit = "12345678abcdef00"
        mentioned = self._clean_report(commit, tail=(
            '\n\nSchema: `<!-- review-data: {"verdict": "NOT_CLEAN", "findings": '
            '[{"file": "a.py", "message": "x"}]} -->`\n\n'
            f"Reviewed-Commit: {commit}"))
        is_valid, is_clean, _ = reviewer.parse_review_verdict(
            mentioned, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean)

    def test_validate_review_output(self):
        commit = "12345678abcdef00"
        valid = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations & Non-Blocking Suggestions\n"
            "[INFO] Looks clean and well-structured.\n\n"
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
        # Rejected as MISSING rather than as a mismatch, since `_FINGERPRINT_RE`
        # bounds the sha at `{7,40}` (as the pre-push hook's own REVIEWED_COMMIT
        # does) and so does not harvest a one-character value at all. Either
        # reason is a rejection; the assertion names both so a future change of
        # mechanism is visible rather than silently re-passing.
        self.assertTrue(
            "mismatch" in reason or "Missing required" in reason,
            f"a one-character fingerprint must be rejected, got: {reason}")

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
            "Verdict: Ready for merge \u2014 must not merge.",
            "Verdict: Ready for merge \u2014 should not be merged.",
            "Verdict: Ready for merge \u2014 unsafe to merge.",
            "Verdict: Ready for merge \u2014 not safe to merge.",
            "Verdict: Ready for merge \u2014 cannot merge.",
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
            "### Observations\n[INFO] The reviewed change is safe to merge.\n\n"
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
        is_valid, is_clean, reason = reviewer.parse_review_verdict(rationale_report, expected_commit_sha=commit)
        self.assertFalse(is_clean)

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

        # Clean verdict with ANY rationale is rejected as strict grammar
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
        self.assertFalse(is_clean)

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
        diff, base_sha, base_ref, label = reviewer.resolve_diff("head123", explicit_base="origin/main")
        self.assertIn("+line", diff)
        self.assertEqual(label, "origin/main")

    @patch("subprocess.run")
    def test_resolve_diff_local_branch_before_initial_push_auto_detect_main(self, mock_subproc):
        def fake_run(cmd, **kwargs):
            m = MagicMock()
            if "merge-base" in cmd:
                m.returncode = 0
                m.stdout = "mb_commit_111\n"
            elif "diff" in cmd:
                m.returncode = 0
                m.stdout = "diff --git a/new.py b/new.py\n+new line"
            elif "symbolic-ref" in cmd:
                m.returncode = 1
                m.stdout = ""
            elif "rev-parse" in cmd and "--verify" in cmd:
                if "origin/main" in cmd:
                    m.returncode = 0
                    m.stdout = "main_commit_222\n"
                else:
                    m.returncode = 1
            else:
                m.returncode = 0
            return m

        mock_subproc.side_effect = fake_run
        diff, base_sha, base_ref, label = reviewer.resolve_diff("head123")
        self.assertIn("+new line", diff)
        self.assertEqual(base_ref, "origin/main")
        self.assertEqual(base_sha, "mb_commit_111")
        self.assertEqual(label, "origin/main")

    @patch("subprocess.run")
    def test_resolve_diff_symbolic_origin_head(self, mock_subproc):
        def fake_run(cmd, **kwargs):
            m = MagicMock()
            if "merge-base" in cmd:
                m.returncode = 0
                m.stdout = "mb_commit_333\n"
            elif "diff" in cmd:
                m.returncode = 0
                m.stdout = "diff --git a/trunk.py b/trunk.py\n+trunk line"
            elif "symbolic-ref" in cmd:
                m.returncode = 0
                m.stdout = "origin/trunk\n"
            elif "rev-parse" in cmd and "--verify" in cmd:
                if "origin/trunk" in cmd:
                    m.returncode = 0
                    m.stdout = "trunk_commit_444\n"
                else:
                    m.returncode = 1
            else:
                m.returncode = 0
            return m

        mock_subproc.side_effect = fake_run
        diff, base_sha, base_ref, label = reviewer.resolve_diff("head123")
        self.assertIn("+trunk line", diff)
        self.assertEqual(base_ref, "origin/trunk")
        self.assertEqual(base_sha, "mb_commit_333")

    @patch("subprocess.run")
    def test_resolve_diff_explicit_base_prefers_origin_prefix(self, mock_subproc):
        def fake_run(cmd, **kwargs):
            m = MagicMock()
            if "merge-base" in cmd:
                m.returncode = 0
                m.stdout = "mb_commit_555\n"
            elif "diff" in cmd:
                m.returncode = 0
                m.stdout = "diff --git a/a.py b/a.py\n+line"
            elif "rev-parse" in cmd and "--verify" in cmd:
                # Both origin/main and main verify, but origin/main should be preferred
                if "origin/main" in cmd:
                    m.returncode = 0
                    m.stdout = "remote_main_sha\n"
                elif "main" in cmd:
                    m.returncode = 0
                    m.stdout = "stale_local_main_sha\n"
                else:
                    m.returncode = 1
            else:
                m.returncode = 0
            return m

        mock_subproc.side_effect = fake_run
        diff, base_sha, base_ref, label = reviewer.resolve_diff("head123", explicit_base="main")
        self.assertIn("+line", diff)
        self.assertEqual(base_ref, "origin/main")
        self.assertEqual(base_sha, "mb_commit_555")

    @patch("subprocess.run")
    def test_resolve_diff_explicit_base_with_origin_prefix_fallback(self, mock_subproc):
        def fake_run(cmd, **kwargs):
            m = MagicMock()
            if "merge-base" in cmd:
                m.returncode = 0
                m.stdout = "mb_commit_666\n"
            elif "diff" in cmd:
                m.returncode = 0
                m.stdout = "diff --git a/a.py b/a.py\n+line"
            elif "rev-parse" in cmd and "--verify" in cmd:
                # origin/local-only does not exist on remote, but local-only exists locally
                if "origin/local-only" in cmd:
                    m.returncode = 1
                elif "local-only" in cmd:
                    m.returncode = 0
                    m.stdout = "commit_666\n"
                else:
                    m.returncode = 1
            else:
                m.returncode = 0
            return m

        mock_subproc.side_effect = fake_run
        diff, base_sha, base_ref, label = reviewer.resolve_diff("head123", explicit_base="origin/local-only")
        self.assertIn("+line", diff)
        self.assertEqual(base_ref, "local-only")
        self.assertEqual(base_sha, "mb_commit_666")

    @patch("subprocess.run")
    def test_resolve_diff_explicit_base_without_origin_prefix_fallback(self, mock_subproc):
        def fake_run(cmd, **kwargs):
            m = MagicMock()
            if "merge-base" in cmd:
                m.returncode = 0
                m.stdout = "mb_commit_777\n"
            elif "diff" in cmd:
                m.returncode = 0
                m.stdout = "diff --git a/b.py b/b.py\n+line"
            elif "rev-parse" in cmd and "--verify" in cmd:
                # origin/local-branch does not exist, but local-branch does
                if "origin/local-branch" in cmd:
                    m.returncode = 1
                elif "local-branch" in cmd:
                    m.returncode = 0
                    m.stdout = "commit_888\n"
                else:
                    m.returncode = 1
            else:
                m.returncode = 0
            return m

        mock_subproc.side_effect = fake_run
        diff, base_sha, base_ref, label = reviewer.resolve_diff("head123", explicit_base="local-branch")
        self.assertIn("+line", diff)
        self.assertEqual(base_ref, "local-branch")

    @patch("subprocess.run")
    def test_resolve_diff_missing_explicit_base_exits(self, mock_subproc):
        def fake_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 1
            m.stdout = ""
            return m

        mock_subproc.side_effect = fake_run
        with self.assertRaises(SystemExit):
            reviewer.resolve_diff("head123", explicit_base="totally-nonexistent-ref")

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

    @patch("os.makedirs")
    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_runner_model_forwarding(self, mock_which, mock_subproc, mock_tf, mock_makedirs):
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
        self.assertLess(cmd_args.index("-m"), cmd_args.index("-"))

    @patch("builtins.open", new_callable=mock_open)
    @patch("os.makedirs")
    @patch("os.unlink")
    @patch("tempfile.NamedTemporaryFile")
    @patch("subprocess.run")
    @patch("shutil.which")
    def test_all_runners_cli_contracts(self, mock_which, mock_subproc, mock_tf, mock_unlink, mock_makedirs, mock_file_open):
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
        self.assertLess(claude_cmd.index("--model"), claude_cmd.index("-p"))

        # Test Cursor runner
        mock_which.return_value = "/opt/homebrew/bin/agent"
        out_cursor = reviewer.run_cursor_review("prompt", model="claude-3.7-sonnet", expected_commit_sha="abc12345")
        self.assertEqual(out_cursor, valid_report)
        cursor_cmd = mock_subproc.call_args[0][0]
        self.assertIn("--trust", cursor_cmd)
        self.assertIn("--print", cursor_cmd)
        print_idx = cursor_cmd.index("--print"); self.assertEqual(cursor_cmd[print_idx + 1], "prompt")

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

        # Verify it created the agent in the correct directory
        import os
        expected_dir = os.path.expanduser("~/.config/opencode/agents")
        mock_tf.assert_any_call(mode="w", suffix=".md", dir=expected_dir, delete=False)
        self.assertIn("--file", oc_cmd)
        self.assertNotIn("prompt", oc_cmd)
        self.assertIn("-m", oc_cmd)
        self.assertIn("anthropic/claude-3.7-sonnet", oc_cmd)
        self.assertLess(oc_cmd.index("-m"), oc_cmd.index("--file"))

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

    def test_non_blocking_observations(self):
        commit = "12345678abcdef0012345678abcdef0012345678"
        report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge.\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\n"
            "[INFO] Non-blocking issue found in documentation.\n"
            "[INFO] This is a non-blocking bug.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean, f"Should be clean but got: {reason}")


    def test_benign_p0_p1_wording(self):
        commit = "12345678abcdef0012345678abcdef0012345678"
        report = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge.\n\n"
            "### Critical Findings\n"
            "None.\n\n"
            "### Observations\n"
            "[INFO] No P0 issues.\n"
            "[INFO] Zero P1 bugs.\n"
            "[INFO] There are non-blocking findings.\n"
            "[INFO] No P2 flaws.\n\n"
            "### Verification Steps\nNone.\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertTrue(is_clean, f"Should be clean but got: {reason}")
    @patch("sys.stdout.isatty", return_value=False)
    @patch.dict(os.environ, {"AGENT_NAME": "human"}, clear=True)
    @patch.object(reviewer, "detect_available_engines", return_value=["codex", "claude"])
    @patch.object(reviewer, "run_codex_review")
    def test_alternate_proceeds_without_invoker(self, mock_codex, mock_detect, mock_isatty):
        mock_codex.return_value = "report"
        report, label = reviewer.execute_review("alternate", "prompt")
        self.assertEqual(report, "report")
        self.assertEqual(label, "OpenAI Codex")



    @patch.object(reviewer, "detect_available_engines")
    def test_alternate_fallback_chain(self, mock_detect):
        mock_detect.return_value = ["codex", "claude", "opencode"]

        call_count = 0
        def fake_codex(*a, **k):
            nonlocal call_count; call_count += 1; return None
        def fake_claude(*a, **k):
            nonlocal call_count; call_count += 1; return None
        def fake_opencode(*a, **k):
            nonlocal call_count; call_count += 1; return "success report"

        with patch.dict(os.environ, {"AGENT_NAME": "antigravity"}, clear=True):
            with patch.object(reviewer, "get_next_alternate_engine", side_effect=["codex", "claude", "opencode"]):
                with patch.object(reviewer, "run_codex_review", side_effect=fake_codex):
                    with patch.object(reviewer, "run_claude_review", side_effect=fake_claude):
                        with patch.object(reviewer, "run_opencode_review", side_effect=fake_opencode):
                            report, label = reviewer.execute_review("alternate", "prompt")
                            self.assertEqual(report, "success report")
                            self.assertEqual(label, "OpenCode")

    @patch("shutil.which")
    @patch("os.path.isfile")
    @patch("subprocess.run")
    def test_antigravity_command_contract(self, mock_run, mock_isfile, mock_which):
        mock_which.return_value = "/usr/local/bin/agy"
        mock_isfile.return_value = True
        mock_run.return_value.stdout = "valid output"
        reviewer.run_antigravity_review("my_prompt", expected_commit_sha="abc")

        called_args = mock_run.call_args[0][0]
        self.assertEqual(called_args[0], "/usr/local/bin/agy")
        self.assertIn("--print", called_args)
        # Check that the prompt immediately follows --print
        print_idx = called_args.index("--print")
        self.assertEqual(called_args[print_idx + 1], "my_prompt")


    @patch("subprocess.run")
    def test_sandbox_isolation_removes_agent_configs(self, mock_run):
        import subprocess
        mock_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="true\n")
        mock_run.return_value = mock_result
        with patch("os.chdir"):
            with patch.object(reviewer, "execute_review", return_value=("report", "label")):
                with patch("sys.argv", ["pre-push-review.py", "--engine", "codex"]):
                    try:
                        reviewer.main()
                    except SystemExit:
                        pass

        rm_call = None
        for call in mock_run.call_args_list:
            args = call[0][0]
            if args and args[0] == "rm" and "-rf" in args:
                rm_call = args
                break

        self.assertIsNotNone(rm_call, "Sandbox cleanup rm -rf was not called")
        self.assertIn(".cursor", rm_call)
        self.assertIn(".agents", rm_call)
        self.assertIn("opencode.json", rm_call)
        self.assertIn(".mcp.json", rm_call)


    @patch.object(reviewer, "run_cursor_review")
    def test_execute_review_dispatches_cursor(self, mock_run_cursor):
        mock_run_cursor.return_value = "report"
        report, label = reviewer.execute_review("cursor", "prompt")
        self.assertEqual(report, "report")
        self.assertEqual(label, "Cursor Agent")


    def test_persona_contract_clean_accepted(self):
        # ai-config#2309: the adversarial-reviewer persona contract
        # (Summary / Findings / Verdict / Reviewed-Commit) must be accepted
        # via the hook's own parse_report(), not rejected as missing the
        # local contract's sections.
        commit = "abc123def4567890"
        report = (
            "### Summary of Changes\n"
            "One commit rewording a docstring.\n\n"
            "### Findings\n"
            "No actionable findings identified.\n\n"
            "### Verdict: Ready for merge\n\n"
            f"Reviewed-Commit: {commit}\n"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertTrue(is_valid, reason)
        self.assertTrue(is_clean, reason)
        self.assertIn("persona", reason)

    def test_persona_contract_needs_work(self):
        commit = "abc123def4567890"
        report = (
            "### Summary of Changes\n"
            "One commit.\n\n"
            "### Findings\n"
            "1. [Defect] scripts/x.py:1 -- broken.\n\n"
            "### Verdict: Needs more work\n\n"
            f"Reviewed-Commit: {commit}\n"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertTrue(is_valid, reason)
        self.assertFalse(is_clean, reason)

    def test_persona_contract_sha_gates(self):
        commit = "abc123def4567890"
        base = (
            "### Summary of Changes\n"
            "One commit.\n\n"
            "### Findings\n"
            "None identified.\n\n"
            "### Verdict: Ready for merge\n\n"
        )
        # Missing fingerprint entirely
        is_valid, _, reason = reviewer.parse_review_verdict(base, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertIn("fingerprint", reason.lower())
        # Wrong fingerprint
        wrong = base + "Reviewed-Commit: 9999999999999999\n"
        is_valid, _, reason = reviewer.parse_review_verdict(wrong, expected_commit_sha=commit)
        self.assertFalse(is_valid)
        self.assertIn("mismatch", reason.lower())

    def test_persona_contract_does_not_shadow_local(self):
        # A report carrying the LOCAL contract's four sections must still be
        # parsed by the local path, including its stricter checks -- the
        # persona fallback fires only when a local section is absent.
        commit = "abc123def4567890"
        local = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "A real, unresolved finding sits here.\n\n"
            "### Observations\nNone.\n\n"
            "### Verification Steps\n- ran tests\n"
            f"Reviewed-Commit: {commit}"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(local, expected_commit_sha=commit)
        # Local path rejects a clean verdict over a non-clean findings body.
        self.assertFalse(is_valid)
        self.assertNotIn("persona", reason)

    def test_persona_hybrid_report_stays_on_strict_path(self):
        # A report carrying ANY local-only section (here Critical Findings)
        # plus persona headings must be graded by the strict local path --
        # dropping one local section cannot buy the laxer parser.
        commit = "abc123def4567890"
        hybrid = (
            "### Summary Verdict\n"
            "Verdict: Ready for merge\n\n"
            "### Critical Findings\n"
            "[P0] blocking bug: data loss on save.\n\n"
            "### Findings\n"
            "None.\n\n"
            "### Verdict: Ready for merge\n\n"
            f"Reviewed-Commit: {commit}\n"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(hybrid, expected_commit_sha=commit)
        self.assertFalse(is_clean, reason)
        self.assertNotIn("persona", reason)

    def test_persona_commented_out_verdict_not_parsed(self):
        commit = "abc123def4567890"
        report = (
            "### Summary of Changes\nx\n\n"
            "### Findings\n1. [Defect] broken.\n\n"
            "### Verdict: Needs more work\n\n"
            "<!--\nVerdict: Ready for merge\n-->\n"
            f"Reviewed-Commit: {commit}\n"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertTrue(is_valid, reason)
        self.assertFalse(is_clean, reason)

    def test_persona_trailing_qualification_rejected(self):
        commit = "abc123def4567890"
        report = (
            "### Summary of Changes\nx\n\n"
            "### Findings\n1. [Defect] XYZ is broken.\n\n"
            "### Verdict: Ready for merge -- after fixing XYZ\n\n"
            f"Reviewed-Commit: {commit}\n"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertFalse(is_valid, reason)
        self.assertIn("qualification", reason.lower())

    def test_persona_comment_strip_cannot_synthesize_fences(self):
        # Deleting comment spans could juxtapose backticks into a fence
        # marker that never existed in the raw text, letting parse_report's
        # internal re-blanking hide a later Needs-more-work line. The strip
        # is offset-preserving, so the blocking verdict must survive.
        commit = "abc123def4567890"
        report = (
            "### Summary of Changes\nx\n\n"
            "### Findings\nNone.\n\n"
            "### Verdict: Ready for merge\n"
            f"Reviewed-Commit: {commit}\n"
            "``<!-- -->`\n"
            "### Verdict: Needs more work\n"
            "``<!-- -->`\n"
        )
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertFalse(is_clean, reason)

    def test_persona_comment_strip_cannot_promote_indentation(self):
        # Round-4 variant: a comment terminator at line start directly before
        # a backtick/tilde run substitutes to <=3 spaces plus the run, which
        # is inside FENCE's indent bound -- a fence synthesized from a line
        # that matched nothing raw. Two such lines would pair inside
        # parse_report's re-blank and hide the blocking verdict between them.
        commit = "abc123def4567890"
        for run in ("```", "~~~"):
            report = (
                "### Summary of Changes\nx\n\n"
                "### Findings\nNone.\n\n"
                "### Verdict: Ready for merge\n"
                f"Reviewed-Commit: {commit}\n"
                f"<!-- a\n-->{run}\n"
                "### Verdict: Needs more work\n"
                f"<!-- b\n-->{run}\n"
            )
            is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
            self.assertFalse(is_clean, f"{run}: {reason}")

    def test_persona_contract_refusal_detected(self):
        report = (
            "### Summary of Changes\nx\n\n"
            "### Findings\nNone.\n\n"
            "### Verdict: Ready for merge\n\n"
            "You have hit your weekly limit.\n"
            "Reviewed-Commit: abc123def4567890\n"
        )
        is_valid, _, reason = reviewer.parse_review_verdict(report, expected_commit_sha="abc123def4567890")
        self.assertFalse(is_valid)
        self.assertIn("refusal", reason.lower())

    def test_verdict_negated_blockers_accepted(self):
        report = "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations & Non-Blocking Suggestions\n[INFO] prevents data loss.\n[INFO] No critical vulnerability was introduced.\n### Verification Steps\nNone"
        is_valid, is_clean, _ = reviewer.parse_review_verdict(report)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean)

    def test_verdict_p1_crash_rejected(self):
        report = "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations & Non-Blocking Suggestions\nP1: the command crashes.\n### Verification Steps\nNone"
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report)
        self.assertFalse(is_clean)
        self.assertIn("Contradictory output", reason)


    def test_oversized_prompt_skips_antigravity_and_cursor(self):
        huge_prompt = "A" * 800001
        self.assertIsNone(reviewer.run_antigravity_review(huge_prompt))
        self.assertIsNone(reviewer.run_cursor_review(huge_prompt))

    def test_verdict_clean_discussing_blocking_status(self):
        commit = "12345678abcdef00"
        report = "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations & Non-Blocking Suggestions\n[INFO] No prior blocking findings were resolved.\n[INFO] The issue of the UI blocking the main thread was fixed.\n### Verification Steps\nNone\nReviewed-Commit: " + commit
        is_valid, is_clean, _ = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertTrue(is_valid)
        self.assertTrue(is_clean)

    def test_verdict_false_negatives_rejected(self):
        commit = "12345678abcdef00"
        reports = [
            "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations & Non-Blocking Suggestions\n[INFO] The fix addresses no fewer than three blocking issues in the auth module.\n### Verification Steps\nNone\nReviewed-Commit: " + commit,
            "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations & Non-Blocking Suggestions\n[INFO] This bug is blocking issue #123 and must be resolved first.\n### Verification Steps\nNone\nReviewed-Commit: " + commit,
            "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations & Non-Blocking Suggestions\n[INFO] The regression was blocking issue tracking for release.\n### Verification Steps\nNone\nReviewed-Commit: " + commit,
        ]
        for report in reports:
            is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
            self.assertFalse(is_clean, f"Report should be rejected: {report}")
            self.assertIn("Contradictory output: clean verdict but report contains blocking phrase", reason)

    def test_verdict_no_blockers_found(self):
        commit = "12345678abcdef00"
        for phrase in (
            "No blockers found.",
            "No known blockers remain outstanding.",
            "No previously known blockers remain.",
            "No newly known blockers remain.",
            "No new, previously known blockers remain.",
            "Zero blockers identified in this review.",
            "There are no blockers preventing merge.",
        ):
            report = f"### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations & Non-Blocking Suggestions\n[INFO] {phrase}\n### Verification Steps\nNone\nReviewed-Commit: {commit}"
            is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
            self.assertTrue(is_valid, f"Expected valid for '{phrase}', got: {reason}")
            self.assertTrue(is_clean, f"Expected clean for '{phrase}', got: {reason}")

    def test_verdict_mislabeled_blocker(self):
        commit = "12345678abcdef00"
        report = "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations & Non-Blocking Suggestions\n[MINOR] The command crashes on every invocation and is not ready for merge.\n### Verification Steps\nNone\nReviewed-Commit: " + commit
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertFalse(is_clean)
        self.assertIn("Contradictory output: clean verdict but report contains blocking phrase", reason)

    def test_verdict_observations_header_variants(self):
        commit = "12345678abcdef00"

        # Test "## Observations"
        report1 = "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n## Observations\nObservation: The command always crashes before producing output.\n### Verification Steps\nNone\nReviewed-Commit: " + commit
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report1, expected_commit_sha=commit)
        self.assertFalse(is_clean)
        self.assertIn("Contradictory output: unclassified free-text observation", reason)

        # Test "### Observations"
        report2 = "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations\nThe command always crashes before producing output.\n### Verification Steps\nNone\nReviewed-Commit: " + commit
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report2, expected_commit_sha=commit)
        self.assertFalse(is_clean)
        self.assertIn("Contradictory output: unclassified free-text observation", reason)

    def test_verdict_contradiction_in_observations(self):
        commit = "12345678abcdef00"
        report = "### Summary Verdict\nVerdict: Ready for merge\n### Critical Findings\nNone.\n### Observations & Non-Blocking Suggestions\nObservation: The command always crashes before producing output.\n### Verification Steps\nNone\nReviewed-Commit: " + commit
        is_valid, is_clean, reason = reviewer.parse_review_verdict(report, expected_commit_sha=commit)
        self.assertFalse(is_clean)
        self.assertIn("Contradictory output: unclassified free-text observation", reason)

    def test_multibyte_oversized_prompts(self):
        multibyte_prompt = "🔥" * 200001
        self.assertTrue(len(multibyte_prompt) < 800000)
        self.assertTrue(len(multibyte_prompt.encode("utf-8")) > 800000)
        self.assertIsNone(reviewer.run_antigravity_review(multibyte_prompt))
        self.assertIsNone(reviewer.run_cursor_review(multibyte_prompt))

    @patch.object(reviewer, "run_antigravity_review", return_value="report")
    @patch.object(reviewer, "run_cursor_review", return_value="report")
    @patch.object(reviewer, "run_codex_review", return_value="report")
    @patch.object(reviewer, "run_claude_review", return_value="report")
    @patch.object(reviewer, "run_opencode_review", return_value="report")
    @patch.object(reviewer, "detect_available_engines", return_value=["claude", "codex", "cursor", "antigravity", "opencode"])
    @patch("sys.stdout.isatty", return_value=True)
    def test_alternate_invocation_without_agent_name(self, mock_isatty, mock_detect, mock_opencode, mock_claude, mock_codex, mock_cursor, mock_anti):
        import os
        orig_agent = os.environ.get("AGENT_NAME")
        if "AGENT_NAME" in os.environ:
            del os.environ["AGENT_NAME"]

        # Clear specific env vars that might leak harness status
        env_vars = ["CLAUDE_SESSION_ID", "GEMINI_SESSION_ID", "ANTIGRAVITY_AGENT", "OPENCODE_SESSION_ID", "CODEX_THREAD_ID"]
        orig_envs = {k: os.environ.get(k) for k in env_vars}
        for k in env_vars:
            if k in os.environ:
                del os.environ[k]

        try:
            report, label = reviewer.execute_review("alternate", "prompt", exclude_engine="")
            self.assertEqual(report, "report")
        finally:
            if orig_agent is not None:
                os.environ["AGENT_NAME"] = orig_agent
            for k, v in orig_envs.items():
                if v is not None:
                    os.environ[k] = v
                elif k in os.environ:
                    del os.environ[k]

if __name__ == "__main__":
    unittest.main()
