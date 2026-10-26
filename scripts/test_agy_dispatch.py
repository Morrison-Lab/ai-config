"""Tests for scripts/agy-dispatch.py: failure detection and review formatting."""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "agy_dispatch", Path(__file__).with_name("agy-dispatch.py")
)
agy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agy)


def done(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


def fake_run(agy_result, status=""):
    """Route `agy` calls to agy_result and `git status` to a clean tree."""

    def run(cmd, **kw):
        return agy_result if cmd[0] == "agy" else done(status)

    return run


class DispatchTest(unittest.TestCase):
    def dispatch(self, agy_result, status=""):
        with mock.patch.object(agy, "run", fake_run(agy_result, status)):
            return agy.dispatch("brief", "m", "1m", ".")

    def test_returns_output(self):
        self.assertEqual(self.dispatch(done("hello\n")), "hello")

    def test_denial_line_fails_despite_exit_zero(self):
        denied = done("jetski: no output produced --- a tool required")
        with self.assertRaises(SystemExit):
            self.dispatch(denied)

    def test_empty_output_fails(self):
        with self.assertRaises(SystemExit):
            self.dispatch(done("  \n"))

    def test_nonzero_exit_fails(self):
        with self.assertRaises(SystemExit):
            self.dispatch(done("x", code=1))

    def test_checkout_edits_fail(self):
        with self.assertRaises(SystemExit):
            self.dispatch(done("ok"), status=" M file.py\n")

    def test_git_status_failure_fails(self):
        def run(cmd, **kw):
            if cmd[0] == "agy":
                return done("ok")
            return done("", "not a repo", 128)

        with mock.patch.object(agy, "run", run), self.assertRaises(SystemExit):
            agy.dispatch("brief", "m", "1m", ".")

    def test_oversized_brief_fails(self):
        with self.assertRaises(SystemExit):
            agy.dispatch("x" * (agy.MAX_BRIEF_BYTES + 1), "m", "1m", ".")


class ReviewTest(unittest.TestCase):
    def review(self, body):
        calls = iter([
            done('{"headRefOid": "abc123", "title": "T"}'),
            done("diff text"),
        ])
        with mock.patch.object(agy, "run", lambda *a, **k: next(calls)), \
                mock.patch.object(agy, "dispatch", return_value=body), \
                mock.patch("sys.argv", ["x", "review", "o/r", "7"]), \
                mock.patch("builtins.print") as out:
            agy.main()
        return out.call_args[0][0]

    def test_clean_verdict_and_single_verdict_line(self):
        text = self.review("Checked: a\nVerdict: Clean")
        self.assertIn("Reviewed-Commit: abc123", text)
        self.assertEqual(text.count("Verdict:"), 1)
        self.assertIn("Verdict: Clean", text)
        self.assertTrue(text.endswith(agy.FOOTER))

    def test_one_line_clean_verdict_is_not_clean(self):
        text = self.review("Verdict: Clean")
        self.assertIn("Verdict: Needs more work", text)

    def test_missing_verdict_is_not_clean(self):
        text = self.review("Checked: a\nsome finding")
        self.assertIn("Verdict: Needs more work", text)


if __name__ == "__main__":
    unittest.main()
