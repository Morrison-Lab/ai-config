#!/usr/bin/env python3
"""Tests for no-rm-live-render-intermediate.py.

Both branches are exercised deliberately, per
`test-no-heavy-work-on-head-node.py`'s own note: a guard seen only to pass is
indistinguishable from one that cannot fire.
"""
import importlib.util
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

# scripts/test_hooks.py passes the subject as argv[1]; fall back to the
# sibling file so a direct `python3 hooks/test-...py` run still works.
HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1
    else str(Path(__file__).with_name("no-rm-live-render-intermediate.py"))
)

spec = importlib.util.spec_from_file_location("guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

RENDERING = "12345 quarto render inst/analysis/paper/paper-with-supplement.qmd"


def run(command, process=RENDERING):
    """Drive main() with the live-process check faked."""
    guard.live_render_process = lambda: process
    buf = io.StringIO()
    stdin, sys.stdin = sys.stdin, io.StringIO(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}}
    ))
    try:
        with redirect_stdout(buf):
            guard.main()
    finally:
        sys.stdin = stdin
    out = buf.getvalue().strip()
    return json.loads(out) if out else None


class TestBlocks(unittest.TestCase):
    def assert_blocked(self, command, **kw):
        result = run(command, **kw)
        self.assertIsNotNone(result, f"expected a block for: {command}")
        decision = result["hookSpecificOutput"]["permissionDecision"]
        self.assertEqual(decision, "deny")
        return result["hookSpecificOutput"]["permissionDecisionReason"]

    def assert_allowed(self, command, **kw):
        self.assertIsNone(run(command, **kw), f"expected no block for: {command}")

    # -- the reported incident, and its sibling shapes -----------------------
    def test_rm_rmarkdown_with_live_render_denied(self):
        reason = self.assert_blocked(
            "rm inst/analysis/paper/paper-with-supplement.rmarkdown"
        )
        self.assertIn("paper-with-supplement.rmarkdown", reason)
        self.assertIn("quarto render", reason)

    def test_rm_rf_files_dir_denied(self):
        self.assert_blocked("rm -rf foo_files/")

    def test_find_delete_denied(self):
        self.assert_blocked("find . -name '*.knit.md' -delete")

    def test_git_clean_denied(self):
        self.assert_blocked("git clean -fd paper.knit.md")

    def test_dotquarto_dir_denied(self):
        self.assert_blocked("rm -rf .quarto")

    def test_knit_qmd_denied(self):
        self.assert_blocked("rm report.knit.qmd")

    def test_quarto_ipynb_denied(self):
        self.assert_blocked("rm notebook.quarto_ipynb")

    # -- no live render: nothing to protect against --------------------------
    def test_rm_rmarkdown_without_live_render_allowed(self):
        """The single most important negative: no render, nothing to fix."""
        self.assert_allowed(
            "rm inst/analysis/paper/paper-with-supplement.rmarkdown",
            process=None,
        )

    # -- a live render, but the target is not an intermediate at all ---------
    def test_non_intermediate_file_allowed(self):
        self.assert_allowed("rm inst/analysis/paper/notes.txt")

    def test_non_intermediate_with_live_render_allowed(self):
        self.assert_allowed("rm -rf build/", process=RENDERING)

    # -- override -------------------------------------------------------------
    def test_override_env_var_allowed(self):
        self.assert_allowed(
            "ALLOW_RM_RENDER_INTERMEDIATE=1 rm paper.rmarkdown"
        )

    def test_override_mention_elsewhere_not_honoured(self):
        """A mention of the override string is not a real assignment."""
        self.assert_blocked(
            "echo ALLOW_RM_RENDER_INTERMEDIATE=1 && rm paper.rmarkdown"
        )

    # -- text that only MENTIONS an intermediate, never deletes one ----------
    def test_mention_in_echo_not_denied(self):
        self.assert_allowed("echo 'cleaning up paper.rmarkdown next'")

    def test_mention_in_grep_not_denied(self):
        self.assert_allowed("grep -rn '.rmarkdown' scripts/")

    def test_commit_message_mention_not_denied(self):
        self.assert_allowed(
            'git commit -m "regenerate paper.knit.md on next render"'
        )

    # -- git clean dry run deletes nothing ------------------------------------
    def test_git_clean_dry_run_allowed(self):
        self.assert_allowed("git clean -n paper.knit.md")

    # -- mutation check: the process check must be load-bearing --------------
    def test_deny_depends_on_the_process_check(self):
        """If the process check were stubbed to always return `None`, the
        reported-incident test above would stop failing to catch anything --
        it would pass vacuously. Confirm the same command that denies with a
        live render allows once the process check reports none, so the deny
        assertion is provably tied to `live_render_process` rather than to
        the deletion match alone."""
        command = "rm inst/analysis/paper/paper-with-supplement.rmarkdown"
        self.assert_blocked(command, process=RENDERING)
        self.assert_allowed(command, process=None)


if __name__ == "__main__":
    # argv[1] is the subject path, not a test name -- hide it from unittest.
    result = unittest.main(argv=[sys.argv[0]], verbosity=2, exit=False).result
    bad = len(result.failures) + len(result.errors)
    print(
        f"{result.testsRun}/{result.testsRun} passed"
        if not bad
        else f"{bad} failure(s) across {result.testsRun} tests"
    )
    sys.exit(1 if bad else 0)
