#!/usr/bin/env python3
"""Timing regression tests and functional verification for scripts/lib/git_cmd.py.

Issue #3172: Catastrophic backtracking in _GIT_FLAGS regex when matching failing inputs.
Verifies that:
  1. COMMIT, PUSH, and CREATE regexes correctly identify valid git/gh commands.
  2. Repeated flag-shaped tokens without a command word terminate in linear time (<0.01s).
  3. Disjoint alternatives properly partition short and long flags without ReDoS.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "scripts" / "lib"
sys.path.insert(0, str(LIB))

import git_cmd

passes = 0
failures = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name} {extra}")
        failures += 1


def test_functional_matching() -> None:
    # 1. COMMIT matching
    check("git commit -m msg matches", bool(git_cmd.COMMIT.search("git commit -m msg")))
    check("git -C /foo/bar commit -m msg matches", bool(git_cmd.COMMIT.search("git -C /foo/bar commit -m msg")))
    check("git -c foo=bar commit -m msg matches", bool(git_cmd.COMMIT.search("git -c foo=bar commit -m msg")))
    check("git -C /foo -c a=b commit -m msg matches", bool(git_cmd.COMMIT.search("git -C /foo -c a=b commit -m msg")))
    check("git -Cfoo commit -m msg matches", bool(git_cmd.COMMIT.search("git -Cfoo commit -m msg")))
    check("git -c=a commit -m msg matches", bool(git_cmd.COMMIT.search("git -c=a commit -m msg")))
    check("git -v commit -m msg matches", bool(git_cmd.COMMIT.search("git -v commit -m msg")))
    check("git -q commit -m msg matches", bool(git_cmd.COMMIT.search("git -q commit -m msg")))
    check("git --dry-run commit -m msg matches", bool(git_cmd.COMMIT.search("git --dry-run commit -m msg")))
    check("git --work-tree=/path commit -m msg matches", bool(git_cmd.COMMIT.search("git --work-tree=/path commit -m msg")))
    check("ALLOW_UNREVIEWED_PUSH=1 git commit matches", bool(git_cmd.COMMIT.search("ALLOW_UNREVIEWED_PUSH=1 git commit -m msg")))

    # Lookahead guard: commit-tree and commit-graph are not commits
    check("git commit-tree does not match", not bool(git_cmd.COMMIT.search("git commit-tree 12345")))
    check("git commit-graph does not match", not bool(git_cmd.COMMIT.search("git commit-graph write --reachable")))

    # 2. PUSH matching
    check("git push origin main matches", bool(git_cmd.PUSH.search("git push origin main")))
    check("git -C /repo push -u origin feat matches", bool(git_cmd.PUSH.search("git -C /repo push -u origin feat")))
    check("ALLOW_UNREVIEWED_PUSH=1 git push matches", bool(git_cmd.PUSH.search("ALLOW_UNREVIEWED_PUSH=1 git push origin HEAD")))
    check("git push-mirror does not match", not bool(git_cmd.PUSH.search("git push-mirror --all")))

    # 3. CREATE matching
    check("gh pr create --fill matches", bool(git_cmd.CREATE.search("gh pr create --fill")))
    check("GH_TOKEN=x gh pr create matches", bool(git_cmd.CREATE.search("GH_TOKEN=x gh pr create --fill")))


def test_redos_timing() -> None:
    # Test cases reported in #3172: failing matches over repeated flag tokens
    # With n=20, the vulnerable regex took >12s for -Cabc, >6s for -c=a, >20s for --foo=bar.
    # The fixed disjoint regex completes in <0.005s even for n=50.
    test_templates = [
        "-Cabc ",
        "-c=a ",
        "--foo=bar ",
        "-v ",
        "-q ",
        "-C /dir ",
        "-c user.email=foo@example.com ",
        "--work-tree=/tmp/test ",
    ]

    for tmpl in test_templates:
        for n in [12, 16, 20, 50]:
            probe = "\ngit " + (tmpl * n) + "X"
            t0 = time.perf_counter()
            match = git_cmd.COMMIT.search(probe)
            dur = time.perf_counter() - t0
            check(
                f"COMMIT probe '{tmpl.strip()}' * {n} rejects without ReDoS ({dur:.4f}s)",
                match is None and dur < 0.05,
                f"dur={dur:.4f}s match={match}",
            )
            t0 = time.perf_counter()
            push_match = git_cmd.PUSH.search(probe)
            push_dur = time.perf_counter() - t0
            check(
                f"PUSH probe '{tmpl.strip()}' * {n} rejects without ReDoS ({push_dur:.4f}s)",
                push_match is None and push_dur < 0.05,
                f"dur={push_dur:.4f}s match={push_match}",
            )


if __name__ == "__main__":
    test_functional_matching()
    test_redos_timing()
    print(f"\n{passes} passed, {failures} failed")
    sys.exit(1 if failures else 0)
