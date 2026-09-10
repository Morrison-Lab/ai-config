#!/usr/bin/env python3
"""Tests for warn-deferred-closing-keyword.py.

The two halves that matter are the POSITIVE controls (each of the three
measured occurrences must fire) and the NEGATIVE controls (a deliberate
`Closes #N` line, and an ordinary mid-sentence close with no cue, must stay
silent). A guard that fires on everything is as useless as one that fires on
nothing, per the lesson recorded on ai-config#3415.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "warn-deferred-closing-keyword.py")

spec = importlib.util.spec_from_file_location("wdck", HOOK)
wdck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wdck)


def run_hook(payload: dict) -> str:
    """Run the hook as a subprocess and return its additionalContext, or ""."""
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"hook exited {proc.returncode}: {proc.stderr}")
    if not proc.stdout.strip():
        return ""
    out = json.loads(proc.stdout)
    return out["hookSpecificOutput"]["additionalContext"]


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


class MeasuredOccurrences(unittest.TestCase):
    """Each real-world case the rule failed on must fire."""

    def test_gha_460_negated_sentence(self):
        body = "I have not closed #322 --- items 1, 3, 4, and 5 remain open there."
        self.assertIsNotNone(wdck.evaluate_body(body))

    def test_bcs_982_deferral_sentence(self):
        body = (
            "Per-stratum arrays, pooled artifacts, and the stratum-specific OR "
            "and CIF tables follow in a data PR that closes #923."
        )
        note = wdck.evaluate_body(body)
        self.assertIsNotNone(note)
        self.assertIn("closes #923", note)

    def test_future_tense_promise(self):
        body = "A later pull request will close #17 once the data lands."
        self.assertIsNotNone(wdck.evaluate_body(body))


class NegativeControls(unittest.TestCase):
    """A guard that never accepts valid input is worse than the hole it closes."""

    def test_deliberate_closing_line_is_silent(self):
        self.assertIsNone(wdck.evaluate_body("Some prose.\n\nCloses #923\n"))

    def test_line_initial_close_wins_over_a_cue_in_its_own_sentence(self):
        # The line-initial form is presumed deliberate even when the sentence
        # around it carries a deferral cue -- this is what the position test
        # buys, and it is the only case that distinguishes it.
        body = "- Closes #923 once the follow-up lands.\n"
        self.assertIsNone(wdck.evaluate_body(body))

    def test_deliberate_closing_line_in_list_is_silent(self):
        self.assertIsNone(wdck.evaluate_body("- Closes #923\n- Closes #924\n"))

    def test_midsentence_close_without_cue_is_silent(self):
        self.assertIsNone(wdck.evaluate_body("This change closes #123 outright."))

    def test_body_with_no_issue_reference_is_silent(self):
        self.assertIsNone(wdck.evaluate_body("This will not close anything later."))

    def test_refs_form_is_silent(self):
        body = "The remaining work will follow in a later PR. Refs #923"
        self.assertIsNone(wdck.evaluate_body(body))

    def test_empty_body_is_silent(self):
        self.assertIsNone(wdck.evaluate_body(""))

    def test_cue_in_a_different_sentence_is_silent(self):
        # "will" sits in the FIRST sentence only; the sentence carrying the
        # reference has no cue, so the scan must not reach across.
        body = "This work will land elsewhere. This closes #5."
        self.assertIsNone(wdck.evaluate_body(body))


class ReferenceForms(unittest.TestCase):
    def test_owner_repo_reference(self):
        body = "A follow-up will fix ucdavis/bcs#42."
        self.assertIsNotNone(wdck.evaluate_body(body))

    def test_url_reference(self):
        body = (
            "A follow-up will resolve "
            "https://github.com/ucdavis/bcs/issues/42 later."
        )
        self.assertIsNotNone(wdck.evaluate_body(body))

    def test_colon_separator(self):
        body = "A separate PR resolves: #99."
        self.assertIsNotNone(wdck.evaluate_body(body))

    def test_keyword_is_case_insensitive(self):
        body = "The follow-up PR CLOSES #7."
        self.assertIsNotNone(wdck.evaluate_body(body))


class CommandExtraction(unittest.TestCase):
    def test_inline_body_flag(self):
        note = run_hook(bash(
            'gh pr create --title t --body "a later PR that closes #923"'
        ))
        self.assertIn("closes #923", note)

    def test_commit_message_flag(self):
        note = run_hook(bash(
            'git commit -m "work; a follow-up will close #12"'
        ))
        self.assertIn("close #12", note)

    def test_heredoc_body(self):
        command = (
            "gh pr create --body-file - <<'EOF'\n"
            "Tables follow in a data PR that closes #923.\n"
            "EOF"
        )
        self.assertIn("closes #923", run_hook(bash(command)))

    def test_body_file_is_read(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write("A separate PR will close #77 afterwards.\n")
            path = handle.name
        try:
            note = run_hook(bash(f"gh pr create --title t --body-file {path}"))
            self.assertIn("close #77", note)
        finally:
            os.unlink(path)

    def test_gh_api_issue_body_patch(self):
        # A PATCH to the issue itself edits its DESCRIPTION, which GitHub does
        # scan.
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write("The follow-up will close #88.\n")
            path = handle.name
        try:
            note = run_hook(bash(
                f"gh api -X PATCH repos/o/r/issues/1 -F body=@{path}"
            ))
            self.assertIn("close #88", note)
        finally:
            os.unlink(path)


class CommentsAreOutOfScope(unittest.TestCase):
    """GitHub's closing-keyword parser reads a PR or issue DESCRIPTION and a
    commit message. It never reads a plain comment, so warning on one would
    assert something false."""

    BODY = "The follow-up will close #88."

    def test_gh_pr_comment_is_silent(self):
        self.assertEqual(
            run_hook(bash(f'gh pr comment 1 --body "{self.BODY}"')), ""
        )

    def test_gh_issue_comment_is_silent(self):
        self.assertEqual(
            run_hook(bash(f'gh issue comment 1 --body "{self.BODY}"')), ""
        )

    def test_gh_api_comments_endpoint_is_silent(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write(self.BODY + "\n")
            path = handle.name
        try:
            self.assertEqual(
                run_hook(bash(
                    f"gh api repos/o/r/issues/1/comments -F body=@{path}"
                )),
                "",
            )
        finally:
            os.unlink(path)

    def test_gh_api_single_comment_patch_is_silent(self):
        self.assertEqual(
            run_hook(bash(
                f'gh api -X PATCH repos/o/r/issues/comments/5 -f body="{self.BODY}"'
            )),
            "",
        )

    def test_add_issue_comment_mcp_tool_is_silent(self):
        payload = {
            "tool_name": "mcp__github__add_issue_comment",
            "tool_input": {"body": "A follow-up PR that closes #923."},
        }
        self.assertEqual(run_hook(payload), "")

    def test_pending_review_comment_mcp_tool_is_silent(self):
        payload = {
            "tool_name": "mcp__github__add_comment_to_pending_review",
            "tool_input": {"body": "A follow-up PR that closes #923."},
        }
        self.assertEqual(run_hook(payload), "")

    def test_a_real_description_write_alongside_a_comment_still_fires(self):
        # The exclusion covers a lone `gh api` to a comments endpoint, not a
        # compound command that also edits a description.
        note = run_hook(bash(
            'gh api repos/o/r/issues/1/comments -f body="hi" && '
            'gh pr edit 2 --body "a follow-up will close #88"'
        ))
        self.assertIn("close #88", note)

    def test_unrelated_command_is_silent(self):
        self.assertEqual(run_hook(bash('echo "a later PR closes #923"')), "")

    def test_unreadable_body_file_is_silent(self):
        command = "gh pr create --title t --body-file /nonexistent/path/xyz.md"
        self.assertEqual(run_hook(bash(command)), "")


class McpSurface(unittest.TestCase):
    def test_create_pull_request_body(self):
        payload = {
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"body": "A follow-up PR that closes #923."},
        }
        self.assertIn("closes #923", run_hook(payload))

    def test_unrelated_mcp_tool_is_silent(self):
        payload = {
            "tool_name": "mcp__github__get_me",
            "tool_input": {"body": "A follow-up PR that closes #923."},
        }
        self.assertEqual(run_hook(payload), "")


class FailsOpen(unittest.TestCase):
    def test_malformed_payload(self):
        proc = subprocess.run(
            [sys.executable, HOOK], input="not json",
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_non_dict_payload(self):
        self.assertEqual(run_hook_raw("[1, 2, 3]"), "")

    def test_missing_command(self):
        self.assertEqual(run_hook({"tool_name": "Bash", "tool_input": {}}), "")


def run_hook_raw(text: str) -> str:
    proc = subprocess.run(
        [sys.executable, HOOK], input=text,
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


if __name__ == "__main__":
    # argv[1] is the subject path, not a test name -- hide it from unittest.
    # unittest reports on stderr; scripts/test_hooks.py shows the last stdout
    # line, so emit a count there too rather than leaving it "(no output)".
    result = unittest.main(argv=[sys.argv[0]], verbosity=2, exit=False).result
    bad = len(result.failures) + len(result.errors)
    print(
        f"{result.testsRun}/{result.testsRun} passed"
        if not bad
        else f"{bad} failure(s) across {result.testsRun} tests"
    )
    sys.exit(1 if bad else 0)
