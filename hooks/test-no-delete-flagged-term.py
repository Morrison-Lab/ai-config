#!/usr/bin/env python3
"""Tests for no-delete-flagged-term.py.

check-term-links itself is stubbed (`flagged`), so the cases pin this hook's
own judgment: which edits count as dropping a flagged term. Both the deny and
the pass branches are exercised, since a guard seen only to pass is
indistinguishable from one that cannot fire.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1
    else str(Path(__file__).with_name("no-delete-flagged-term.py"))
)

spec = importlib.util.spec_from_file_location("guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

BEFORE = (
    "# Sets\n"
    "\n"
    "Let $A$ be a finite set of labels.\n"
    "Every label is a string.\n"
)


class Repo:
    """A throwaway git repo holding page.qmd with BEFORE."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        subprocess.run(["git", "init", "-q", "-b", "main", root], check=True)
        Path(root, "page.qmd").write_text(BEFORE, encoding="utf-8")
        return root

    def __exit__(self, *exc):
        self.tmp.cleanup()


def run(root, tool_input, tool="Edit", findings=((3, "finite"),)):
    """Drive main() with check-term-links stubbed to report `findings`."""
    seen = {}

    def fake_flagged(git_root, rel, lines, notes):
        seen["lines"] = lines
        return [f for f in findings if f[0] in lines]

    guard.flagged = fake_flagged
    guard._notes_checks = lambda: object()
    payload = {"tool_name": tool, "cwd": root,
               "tool_input": {"file_path": "page.qmd", **tool_input}}
    buf = io.StringIO()
    stdin, sys.stdin = sys.stdin, io.StringIO(json.dumps(payload))
    try:
        with redirect_stdout(buf):
            guard.main()
    finally:
        sys.stdin = stdin
    out = buf.getvalue().strip()
    return (json.loads(out) if out else None), seen


def denied(result):
    return (result or {}).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


class TestDenies(unittest.TestCase):
    def test_dropping_the_flagged_word(self):
        with Repo() as root:
            res, seen = run(root, {"old_string": "a finite set", "new_string": "a set"})
        self.assertTrue(denied(res))
        self.assertIn("'finite'", res["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(seen["lines"], {3})

    def test_write_that_drops_the_word(self):
        with Repo() as root:
            res, _ = run(root, {"content": BEFORE.replace("finite ", "")}, tool="Write")
        self.assertTrue(denied(res))

    def test_multiedit_that_drops_the_word(self):
        edits = [{"old_string": "finite set", "new_string": "set"},
                 {"old_string": "a string", "new_string": "a short string"}]
        with Repo() as root:
            res, _ = run(root, {"edits": edits}, tool="MultiEdit")
        self.assertTrue(denied(res))


class TestPasses(unittest.TestCase):
    def test_linking_the_term(self):
        with Repo() as root:
            res, _ = run(root, {"old_string": "a finite set",
                                "new_string": "a [finite](sets.qmd#def-finite-set) set"})
        self.assertIsNone(res)

    def test_deleting_the_whole_line(self):
        with Repo() as root:
            res, _ = run(root, {"old_string": "Let $A$ be a finite set of labels.\n",
                                "new_string": ""})
        self.assertIsNone(res)

    def test_wholesale_rewrite(self):
        with Repo() as root:
            res, _ = run(root, {"old_string": "Let $A$ be a finite set of labels.",
                                "new_string": "Consider the vocabulary drawn from the corpus."})
        self.assertIsNone(res)

    def test_term_moved_elsewhere_in_the_file(self):
        with Repo() as root:
            res, _ = run(root, {"content": BEFORE.replace("a finite set", "a set").replace(
                "a string", "a string from a finite alphabet")}, tool="Write")
        self.assertIsNone(res)

    def test_unflagged_word_dropped(self):
        with Repo() as root:
            res, _ = run(root, {"old_string": "a finite set", "new_string": "a set"},
                         findings=())
        self.assertIsNone(res)

    def test_other_file_types_ignored(self):
        with Repo() as root:
            payload_input = {"file_path": "page.R", "old_string": "x", "new_string": "y"}
            res, _ = run(root, payload_input)
        self.assertIsNone(res)

    def test_bypass_variable(self):
        os.environ[guard.BYPASS_VAR] = "1"
        try:
            with Repo() as root:
                res, _ = run(root, {"old_string": "a finite set", "new_string": "a set"})
        finally:
            del os.environ[guard.BYPASS_VAR]
        self.assertIsNone(res)


class TestHelpers(unittest.TestCase):
    def test_count_is_whole_word_and_case_blind(self):
        self.assertEqual(guard.count("finite", "Finite, infinite, finite-dimensional"), 1)

    def test_after_text_refuses_a_missing_old_string(self):
        self.assertIsNone(guard.after_text("Edit", {"old_string": "zzz", "new_string": ""}, BEFORE))


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1])
