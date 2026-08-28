#!/usr/bin/env python3
"""Tests for no-heavy-work-on-head-node.py.

Both branches are exercised deliberately, because a guard that has only ever
been seen to pass is indistinguishable from one that cannot fire. The session
that wrote this ran on a compute node, where the guard allows everything -- so
running it once and seeing no block would have proved nothing.
"""
import importlib.util
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

# scripts/test_hooks.py passes the subject as argv[1]; fall back to the sibling
# file so a direct `python3 hooks/test-...py` run still works.
HOOK = (
    sys.argv[1]
    if len(sys.argv) > 1
    else str(Path(__file__).with_name("no-heavy-work-on-head-node.py"))
)

spec = importlib.util.spec_from_file_location("guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

HEAVY = "Rscript -e 'devtools::test()'"


def run(command, host="shiva", nodes=frozenset({"c1", "c2", "c3", "c4"}), env=None):
    """Drive main() with the host, cluster and environment faked."""
    guard.compute_nodes = lambda: nodes
    guard.os.uname = lambda: os.uname_result(("Linux", host, "", "", ""))
    saved, buf = dict(os.environ), io.StringIO()
    os.environ.clear()
    os.environ.update(env or {})
    stdin, sys.stdin = sys.stdin, io.StringIO(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}}
    ))
    try:
        with redirect_stdout(buf):
            guard.main()
    finally:
        sys.stdin = stdin
        os.environ.clear()
        os.environ.update(saved)
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

    # -- the case that actually happened ------------------------------------
    def test_the_reported_incident(self):
        """Verbatim shape of the command the sysadmin reported."""
        self.assert_blocked(
            'R --no-echo --no-restore -e Sys.setenv(NOT_CRAN="true");'
            " res <- devtools::test()"
        )

    def test_expensive_forms_all_blocked(self):
        for command in [
            HEAVY,
            "Rscript -e 'devtools::check()'",
            "Rscript -e 'lintr::lint_package()'",
            "Rscript -e 'renv::restore()'",
            "Rscript -e 'spelling::spell_check_package()'",
            "R CMD check .",
            "quarto render vignettes/articles/foo.qmd",
            "Rscript data-raw/precompute-all-validations.R",
        ]:
            with self.subTest(command=command):
                self.assert_blocked(command)

    def test_blocked_in_a_later_segment(self):
        """A guard that only reads the first word misses `cd x && <heavy>`."""
        self.assert_blocked("cd /home/<user>/Projects/bcs && " + HEAVY)

    # -- the branch that must NOT fire --------------------------------------
    def test_allowed_on_a_compute_node(self):
        """The single most important negative: on c2 there is nothing to fix."""
        self.assert_allowed(HEAVY, host="c2")

    def test_allowed_when_already_routed(self):
        for command in [
            "srun --cpus-per-task=8 --mem=32G " + HEAVY,
            "sbatch data-raw/ett-validation.sbatch",
        ]:
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_allowed_off_cluster(self):
        """No SLURM at all -- a laptop -- must not be gated."""
        self.assert_allowed(HEAVY, nodes=None)

    def test_cheap_r_is_not_gated(self):
        """Gating trivial lookups would train me to distrust the guard."""
        for command in [
            "Rscript -e 'cat(R.version.string)'",
            "Rscript -e 'packageVersion(\"dplyr\")'",
            "R --version",
        ]:
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_mentioning_it_is_not_running_it(self):
        """The anchor's whole job: text about the command is not the command."""
        for command in [
            "grep -rn 'devtools::test' scripts/",
            "echo 'run devtools::test() on a compute node'",
        ]:
            with self.subTest(command=command):
                self.assert_allowed(command)

    # -- the salloc trap ----------------------------------------------------
    def test_salloc_on_head_node_still_blocked(self):
        """An allocation reserves resources; it does not move you onto them."""
        reason = self.assert_blocked(HEAVY, env={"SLURM_JOB_ID": "142645"})
        self.assertIn("salloc trap", reason)

    def test_suggestion_mirrors_the_allocation(self):
        reason = self.assert_blocked(
            HEAVY, env={"SLURM_CPUS_PER_TASK": "24", "SLURM_MEM_PER_NODE": "65536"}
        )
        self.assertIn("--cpus-per-task=24", reason)
        self.assertIn("--mem=64G", reason)


if __name__ == "__main__":
    # argv[1] is the subject path, not a test name -- hide it from unittest.
    # unittest reports on stderr; scripts/test_hooks.py shows the last stdout
    # line, so emit a count there too rather than leaving it "(no output)".
    result = unittest.main(argv=[sys.argv[0]], verbosity=2, exit=False).result
    bad = len(result.failures) + len(result.errors)
    # Not testsRun - bad: subTest failures can outnumber the tests that ran,
    # which would print a negative count on exactly the failing run that most
    # needs to be legible.
    print(
        f"{result.testsRun}/{result.testsRun} passed"
        if not bad
        else f"{bad} failure(s) across {result.testsRun} tests"
    )
    sys.exit(1 if bad else 0)
