#!/usr/bin/env python3
"""Tests for no-delete-flagged-term.py.

TestDenies and TestPasses stub check-term-links (`flagged`), so they pin this
hook's own judgment: which edits count as dropping a flagged term. Both the
deny and the pass branches are exercised for each tool, since a guard seen
only to pass is indistinguishable from one that cannot fire. TestFlagged runs
the real `flagged` against a fake check script, covering the finding parser,
the rule and path filters, the diff it hands the check, and its fail-open
paths.
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
REAL_FLAGGED = guard.flagged  # run() stubs guard.flagged; TestFlagged needs the real one

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
    def test_multiedit_that_links_the_term(self):
        edits = [{"old_string": "finite set", "new_string": "[finite](sets.qmd#def-finite-set) set"},
                 {"old_string": "a string", "new_string": "a short string"}]
        with Repo() as root:
            res, _ = run(root, {"edits": edits}, tool="MultiEdit")
        self.assertIsNone(res)

    def test_linking_a_term_wrapped_across_lines(self):
        with Repo() as root:
            res, _ = run(root, {"old_string": "a finite set of labels.",
                                "new_string": "a [finite\nset](sets.qmd#def-finite-set) of labels."},
                         findings=((3, "finite set"),))
        self.assertIsNone(res)

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

    def test_count_matches_a_term_wrapped_across_lines(self):
        self.assertEqual(guard.count("finite set", "a finite\n  set here"), 1)

    def test_quoted_keeps_an_apostrophe(self):
        msg = "'Bayes' theorem' is a defined term; link its first use in this div."
        self.assertEqual(guard.QUOTED.search(msg).group("term"), "Bayes' theorem")
        msg = "Bold term 'Bayes' rule' has no definition div anywhere in the corpus."
        self.assertEqual(guard.QUOTED.search(msg).group("term"), "Bayes' rule")


class FakeNotes:
    """Stands in for no-push-with-failing-notes-checks.py around a fake check script."""

    def __init__(self, gha_dir, calls=True):
        self.gha_dir = gha_dir
        self.calls = calls
        self.TERMS_CACHE = os.path.join(gha_dir, "terms-cache")
        self.CHECKS = {"check-term-links": {"prefix": "TERM_LINKS_",
                                            "inputs": {"globs": "GLOBS"},
                                            "script": "fake-check.py"}}

    def find_calls(self, git_root):
        if not self.calls:
            return []
        return [{"name": "check-term-links", "ref": "v3", "inputs": {"globs": "*.qmd"}}]

    def ensure_gha(self, ref):
        return self.gha_dir

    def terms_from(self, git_root, call):
        return []


class TestFlagged(unittest.TestCase):
    """The real flagged(): parsing, filtering, and each fail-open path."""

    def call(self, script, calls=True):
        with tempfile.TemporaryDirectory() as gha:
            Path(gha, "fake-check.py").write_text(script, encoding="utf-8")
            err = io.StringIO()
            stderr, sys.stderr = sys.stderr, err
            try:
                out = REAL_FLAGGED(gha, "page.qmd", {3, 4}, FakeNotes(gha, calls))
            finally:
                sys.stderr = stderr
            return out, err.getvalue()

    def test_parses_and_filters_findings(self):
        script = (
            "import os\n"
            "assert os.environ['TERM_LINKS_GLOBS'] == '*.qmd'\n"
            "assert os.environ['TERM_LINKS_FAIL'] == 'false'\n"
            "diff = open(os.environ['TERM_LINKS_DIFF_FILE']).read()\n"
            "assert '+3,1' in diff and '+4,1' in diff, diff\n"
            "print(\"  page.qmd:3: [unlinked-first-use] 'Bayes' theorem' is a defined term; x\")\n"
            "print(\"  page.qmd:4: [no-definition] Bold term 'finite' has no definition div\")\n"
            "print(\"  page.qmd:4: [stale-allow] 'finite' is a defined term; x\")\n"
            "print(\"  other.qmd:3: [unlinked-first-use] 'set' is a defined term; x\")\n"
        )
        out, _ = self.call(script)
        self.assertEqual(out, [(3, "Bayes' theorem"), (4, "finite")])

    def test_check_error_fails_open_with_a_reason(self):
        out, err = self.call("import sys\nsys.exit('boom')\n")
        self.assertIsNone(out)
        self.assertIn("exited 1", err)
        self.assertIn("boom", err)

    def test_no_caller_fails_open_with_a_reason(self):
        out, err = self.call("print('unused')\n", calls=False)
        self.assertIsNone(out)
        self.assertIn("no check-term-links caller", err)


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1])
