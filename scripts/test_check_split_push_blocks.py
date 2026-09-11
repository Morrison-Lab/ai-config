#!/usr/bin/env python3
"""Cases for scripts/check-split-push-blocks.py.

The checker decides a mechanical property of a recipe, so its own cases are
the record of what that property means: which spellings name a directory,
which read a variable a separate Bash call never inherits, and what an empty
sweep reports.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NL = chr(10)
MARKER = "Push as a separate Bash call"
FENCE = "```bash"
CLOSE = "```"


def load_checker():
    """Import the checker by path, since its filename is not a module name."""
    path = REPO / "scripts" / "check-split-push-blocks.py"
    spec = importlib.util.spec_from_file_location("check_split_push", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()


def recipe(push_body, earlier_body="cd ../repo-slug"):
    """A minimal SKILL.md carrying one earlier block and one push block."""
    parts = [
        FENCE, earlier_body, CLOSE, "",
        MARKER + " here:", "",
        FENCE, push_body, CLOSE, "",
    ]
    return NL.join(parts)


class TestNamesItsDirectory(unittest.TestCase):
    def test_an_absolute_git_c_names_it(self):
        self.assertTrue(CHECKER.names_its_directory("git -C /abs push" + NL))

    def test_an_absolute_cd_names_it(self):
        self.assertTrue(CHECKER.names_its_directory("cd /abs" + NL))

    def test_a_drive_letter_cd_names_it(self):
        self.assertTrue(CHECKER.names_its_directory("cd C:/abs" + NL))

    def test_a_relative_cd_does_not_name_it(self):
        # It assumes the reset behaviour: run from inside that sibling, the
        # same path does not resolve.
        self.assertFalse(CHECKER.names_its_directory("cd ../repo-slug" + NL))

    def test_a_bare_git_does_not(self):
        self.assertFalse(CHECKER.names_its_directory("git push" + NL))

    def test_a_relative_git_c_does_not_name_it(self):
        self.assertFalse(CHECKER.names_its_directory("git -C ../sibling push" + NL))

    def test_a_branch_name_containing_the_flag_is_not_the_flag(self):
        body = "git push -u origin fix/issue-C"
        self.assertFalse(CHECKER.names_its_directory(body + NL))

    def test_a_second_call_chained_behind_an_anchored_one_is_seen(self):
        body = "git -C /abs commit --allow-empty -m x && git push"
        self.assertFalse(CHECKER.names_its_directory(body + NL))

    def test_a_derived_absolute_target_is_accepted(self):
        # Its value is not in the block, and the recipes that build one
        # anchor it on an absolute root.
        body = chr(34).join(["git -C ", "$repo/worktrees/x", " push"])
        self.assertTrue(CHECKER.names_its_directory(body + NL))
    def test_a_git_named_in_a_comment_is_not_a_call(self):
        body = NL.join([
            "# avoid $(git rev-parse) here",
            chr(34).join(["git -C ", "/abs", " push"]),
        ])
        self.assertTrue(CHECKER.names_its_directory(body + NL))

    def test_an_inner_substitution_is_not_swallowed_by_its_outer_call(self):
        body = "git -C /abs push origin $(git branch --show-current)"
        self.assertFalse(CHECKER.names_its_directory(body + NL))

    def test_a_backtick_substitution_counts_too(self):
        body = "repo=`git rev-parse --show-toplevel`" + NL + "git -C /abs push"
        self.assertFalse(CHECKER.names_its_directory(body + NL))

    def test_whitespace_after_the_substitution_opener_counts_too(self):
        body = "repo=$( git rev-parse --show-toplevel )" + NL + "git -C /abs push"
        self.assertFalse(CHECKER.names_its_directory(body + NL))
    def test_a_git_inside_a_substitution_does_not(self):
        # The substitution runs wherever the caller happened to be, so the
        # block is as cwd-dependent as a bare git call.
        body = NL.join([
            chr(34).join(["repo=", "$(git rev-parse --show-toplevel)", ""]),
            chr(34).join(["git -C ", "$repo", " push"]),
        ])
        self.assertFalse(CHECKER.names_its_directory(body + NL))


class TestProblemsIn(unittest.TestCase):
    def test_a_cwd_dependent_push_after_an_earlier_cd_fails(self):
        problems = CHECKER.problems_in(recipe("git push"))
        self.assertTrue(any("neither cds nor passes" in p for p in problems))

    def test_an_absolute_git_c_push_passes(self):
        self.assertEqual(CHECKER.problems_in(recipe("git -C /abs push")), [])

    def test_a_variable_the_block_never_set_is_reported(self):
        body = chr(34).join(["git -C ", "$wt", " push"])
        problems = CHECKER.problems_in(recipe(body))
        self.assertTrue(any("$wt" in p for p in problems))

    def test_a_variable_the_block_sets_itself_is_fine(self):
        body = NL.join(["wt=/abs", chr(34).join(["git -C ", "$wt", " push"])])
        self.assertEqual(CHECKER.problems_in(recipe(body)), [])

    def test_an_ambient_name_needs_no_assignment(self):
        body = chr(34).join(["git -C ", "$HOME/r", " push"])
        self.assertEqual(CHECKER.problems_in(recipe(body)), [])

    def test_no_earlier_cd_leaves_the_directory_question_open(self):
        problems = CHECKER.problems_in(recipe("git push", earlier_body="ls"))
        self.assertEqual(problems, [])


class TestSweep(unittest.TestCase):
    def test_an_empty_corpus_fails_rather_than_reporting_clean(self):
        # A zero from a sweep that never ran is indistinguishable from a zero
        # from a clean corpus, so the checker refuses the first.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(CHECKER.main(["check", tmp]), 1)

    def test_the_real_corpus_passes(self):
        self.assertEqual(CHECKER.main(["check", str(REPO)]), 0)


if __name__ == "__main__":
    unittest.main()
