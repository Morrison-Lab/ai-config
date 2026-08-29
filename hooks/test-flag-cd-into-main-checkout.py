#!/usr/bin/env python3
"""Tests for flag-cd-into-main-checkout.py.

The NEGATIVE cases carry the weight. This guard's whole risk is noise: a
worktree-rooted session legitimately `cd`s into other repositories all the
time, and a version that flagged those would be switched off within a day,
taking the real cases with it.

Run: python3 hooks/test-flag-cd-into-main-checkout.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "guard", HERE / "flag-cd-into-main-checkout.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

REPO = "/home/u/Documents/GitHub/gha"
WT = f"{REPO}/.claude/worktrees/feature-x"

FIRES = [
    ("bare cd to the repo root", f"cd {REPO}"),
    ("cd then work", f"cd {REPO} && git status --short"),
    ("cd with a trailing slash", f"cd {REPO}/ && ls"),
    ("cd on a later segment", f"echo hi; cd {REPO} && grep -r foo ."),
    ("cd after a newline", f"set -e\ncd {REPO}\nactionlint"),
    ("quoted target", f'cd "{REPO}" && python3 x.py'),
    ("single-quoted target", f"cd '{REPO}' && python3 x.py"),
    ("relative path climbing out", "cd ../../.. && git status"),
    ("cd inside a pipeline segment", f"true | cd {REPO}"),
]

QUIET = [
    # The reason this guard is narrow: these are all ordinary.
    ("cd to an UNRELATED repo", "cd /home/u/Documents/GitHub/ai-config && python3 s.py"),
    ("cd deeper inside the worktree", f"cd {WT}/subdir && ls"),
    ("cd to the worktree root itself", f"cd {WT} && ls"),
    ("no cd at all", "git status --short"),
    ("git -C against the repo, the correct form", f"git -C {REPO} status --short"),
    ("the repo path mentioned but not cd'd", f"echo {REPO} && grep x f"),
    ("cd to a sibling worktree", f"{REPO}/.claude/worktrees/other && ls"),
    # These two stay quiet because an unexpanded target joins literally and so
    # cannot equal the repo path. They document that behaviour rather than
    # discriminating: no mutation of the guard makes either one fire.
    ("unexpanded variable target", "cd $REPO && ls"),
    ("home-relative target", "cd ~/somewhere && ls"),
    ("a path merely PREFIXED by the repo", f"cd {REPO}-scratch && ls"),
]

# A session not in a worktree must never fire, whatever it cd's to.
NOT_A_WORKTREE = [
    ("plain checkout cd's anywhere", f"cd {REPO} && ls", REPO),
    ("plain checkout cd's elsewhere", "cd /tmp && ls", "/home/u/somewhere"),
]


def main() -> int:
    failures = 0

    for label, command in FIRES:
        if guard.evaluate(command, WT) is None:
            print(f"::error::expected a warning: {label}\n    {command}", file=sys.stderr)
            failures += 1
        else:
            print(f"OK   fires: {label}")

    for label, command in QUIET:
        result = guard.evaluate(command, WT)
        if result is not None:
            print(f"::error::expected silence: {label}\n    {command}\n{result}",
                  file=sys.stderr)
            failures += 1
        else:
            print(f"OK   quiet: {label}")

    for label, command, cwd in NOT_A_WORKTREE:
        if guard.evaluate(command, cwd) is not None:
            print(f"::error::expected silence outside a worktree: {label}", file=sys.stderr)
            failures += 1
        else:
            print(f"OK   quiet outside a worktree: {label}")

    # The message must name the alternative, or it teaches nothing.
    message = guard.evaluate(f"cd {REPO} && ls", WT)
    for needed in ("git -C", "MAIN checkout", "git-worktrees.md"):
        if needed not in message:
            print(f"::error::warning text omits {needed!r}", file=sys.stderr)
            failures += 1

    total = len(FIRES) + len(QUIET) + len(NOT_A_WORKTREE)
    if failures:
        print(f"::error::{failures} of {total} case(s) failed", file=sys.stderr)
        return 1
    print(f"All {total} flag-cd-into-main-checkout cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
