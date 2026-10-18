#!/usr/bin/env python3
"""Tests for scripts/lib/maintainer_feedback.py and its two consumers.

`check-pr-fully-clean.py` imports the library; the merge hook keeps its own
copy because a hook cannot import `scripts/lib`. The parity test feeds both
the same items so the copies cannot drift apart (ai-config#4611).
"""
import importlib.util
import io
import contextlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import maintainer_feedback as lib  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load("gate_copy", ROOT / "hooks" / "enforce-mwc-review-gate.py")
checker = load("checker_copy", ROOT / "scripts" / "check-pr-fully-clean.py")

PUSHED = "2026-10-17T06:00:00Z"
LATER = "2026-10-17T06:30:00Z"
EARLIER = "2026-10-17T05:30:00Z"


def user(login):
    return {"login": login}


def pr_data(comments=(), reviews=(), review_comments=()):
    return {
        "commits": [{"committedDate": PUSHED}],
        "comments": list(comments),
        "reviews": list(reviews),
        "reviewComments": list(review_comments),
    }


def comment(body, login="d-morrison", when=LATER):
    return {"author": user(login), "body": body, "createdAt": when}


def review(body, login="d-morrison", when=LATER):
    return {"author": user(login), "body": body, "submittedAt": when}


class FakePR:
    def __init__(self, data, review_comments):
        self._data = data
        self.review_comments = review_comments


BODIES = [
    "Define this directly.",
    "Approved, but rename the helper.",
    "/mwc all",
    "merge it",
    "LGTM.",
    "",
    "   ",
    "_Posted by Claude Code (AI agent) --- not written by a human._",
]


class TestLibrary(unittest.TestCase):
    def test_comment_after_push_is_reported(self):
        out = lib.unread_maintainer_feedback(pr_data([comment("Nit.")]))
        self.assertEqual(out, [f"comment by d-morrison at {LATER}"])

    def test_item_at_or_before_push_is_not_reported(self):
        for when in (EARLIER, PUSHED):
            with self.subTest(when=when):
                self.assertEqual(
                    lib.unread_maintainer_feedback(pr_data([comment("Nit.", when=when)])), [])

    def test_each_kind_is_reported_with_its_label(self):
        data = pr_data(
            [comment("a")], [review("b")],
            [{"author": user("d-morrison"), "body": "c", "createdAt": LATER}])
        kinds = [x.split(" by ")[0] for x in lib.unread_maintainer_feedback(data)]
        self.assertEqual(kinds, ["comment", "review", "inline comment"])

    def test_other_author_is_not_reported(self):
        self.assertEqual(
            lib.unread_maintainer_feedback(pr_data([comment("Nit.", login="someone")])), [])

    def test_missing_commits_reports_nothing(self):
        data = pr_data([comment("Nit.")])
        data["commits"] = []
        self.assertEqual(lib.unread_maintainer_feedback(data), [])


class TestParityWithTheHook(unittest.TestCase):
    def test_same_verdict_for_every_body_kind(self):
        for body in BODIES:
            data = pr_data(
                [comment(body)], [review(body)],
                [{"author": user("d-morrison"), "body": body, "createdAt": LATER}])
            with self.subTest(body=body):
                self.assertEqual(
                    lib.unread_maintainer_feedback(data),
                    hook.unread_maintainer_feedback(data))

    def test_same_grant_pattern_and_marker_pattern(self):
        self.assertEqual(lib.EXEMPT_RE.pattern, hook.MAINTAINER_FEEDBACK_EXEMPT_RE.pattern)
        self.assertEqual(lib.AGENT_AUTHORSHIP_RE.pattern, hook.AGENT_AUTHORSHIP_RE.pattern)


class TestCheckerGate(unittest.TestCase):
    def run_check(self, data, review_comments=()):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ok, issues = checker.check_maintainer_feedback(FakePR(data, list(review_comments)))
        return ok, issues, out.getvalue()

    def test_clean_when_nothing_is_newer_than_the_push(self):
        ok, issues, out = self.run_check(pr_data([comment("Nit.", when=EARLIER)]))
        self.assertTrue(ok)
        self.assertEqual(issues, [])
        self.assertIn("No maintainer feedback", out)

    def test_comment_after_push_blocks(self):
        ok, issues, _ = self.run_check(pr_data([comment("Define this directly.")]))
        self.assertFalse(ok)
        self.assertEqual(len(issues), 1)
        self.assertIn("Maintainer feedback newer than the last push", issues[0])
        self.assertFalse(issues[0].startswith("NOTE: "))

    def test_inline_comment_comes_from_review_comments_property(self):
        rc = {"author": user("d-morrison"), "body": "Name the codomain.", "createdAt": LATER}
        ok, issues, _ = self.run_check(pr_data(), [rc])
        self.assertFalse(ok)
        self.assertIn("inline comment", issues[0])

    def test_bare_grant_does_not_block(self):
        ok, _, _ = self.run_check(pr_data([comment("/mwc all")]))
        self.assertTrue(ok)

    def test_payload_without_inline_comments_still_checks_the_rest(self):
        class NoInline:
            def __init__(self, data, _unused):
                self._data = data

            @property
            def review_comments(self):
                raise checker.PayloadError("payload has no 'review_comments'")

        data = pr_data([comment("Define this directly.")])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ok, issues = checker.check_maintainer_feedback(NoInline(data, []))
        self.assertFalse(ok)
        self.assertEqual(len(issues), 1)
        clean = io.StringIO()
        with contextlib.redirect_stdout(clean):
            ok, _ = checker.check_maintainer_feedback(NoInline(pr_data(), []))
        self.assertTrue(ok)
        self.assertIn("not checked", clean.getvalue())

    def run_main(self, data):
        """main() with every other check passing, so only this one decides."""
        args = SimpleNamespace(from_json="", pr_number="1", repo="o/r", quorum=1)
        fake = FakePR(data, [])
        fake.head_sha, fake.branch, fake.state = "a" * 40, "b", "OPEN"
        fake.commit_date, fake.review_decision = PUSHED, ""
        out = io.StringIO()
        with patch.object(checker, "parse_args", return_value=args), \
                patch.object(checker, "resolve_repo", return_value="o/r"), \
                patch.object(checker, "get_pr_info", return_value=fake), \
                patch.object(checker, "check_ci_runs", return_value=(True, [])), \
                patch.object(checker, "check_review_threads", return_value=(True, [])), \
                patch.object(checker, "check_review_comments", return_value=(True, [])), \
                patch.object(checker, "check_base_drift", return_value=(True, [])), \
                contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as raised:
                checker.main()
        return raised.exception.code, out.getvalue()

    def test_main_exits_1_on_unread_feedback(self):
        code, text = self.run_main(pr_data([comment("Define this directly.")]))
        self.assertEqual(code, 1)
        self.assertIn("Maintainer feedback newer than the last push", text)

    def test_main_exits_0_when_feedback_is_answered(self):
        code, text = self.run_main(pr_data([comment("Define this directly.", when=EARLIER)]))
        self.assertEqual(code, 0)
        self.assertIn("FULLY CLEAN", text)

    def test_checker_does_not_mutate_the_pr_data(self):
        data = pr_data([comment("Nit.")])
        self.run_check(data, [{"author": user("d-morrison"), "body": "x", "createdAt": LATER}])
        self.assertEqual(data["reviewComments"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
