#!/usr/bin/env python3
"""PreToolUse guard: a worktree-rooted session `cd`-ing into its own main checkout.

## The incident

A session rooted in `<repo>/.claude/worktrees/<name>` ran, seven times in one
sitting:

    cd /path/to/<repo> && <do work>

`<repo>` is a real, valid, plausible-looking path. It is also the MAIN
checkout, which is on a different branch --- routinely a peer session's branch.
Every one of those calls succeeded:

* a file edit landed in the peer checkout rather than the worktree;
* `actionlint` and a `grep` ran against the peer checkout and reported clean,
  which read as evidence about the session's own branch --- twice;
* a `git checkout` moved the peer checkout off another session's branch;
* a six-site documentation sweep landed on that branch and had to be reverted.

## Why a hook rather than a rule

`memories/git-worktrees.md` already carries this, and the session that made
these seven mistakes had *authored* an addition to that very section hours
earlier. A rule is consulted at read time; this breaks at composition time,
when `cd <repo>` is simply the most natural way to name the repository. So
re-reading the rule never reaches the moment.

Nothing downstream reports it either. The `cd` succeeds, the work succeeds, and
a read against the wrong checkout returns a plausible number rather than an
error --- which is the same shape
[`verify-the-right-artifact.md`](../shared/workflow/verify-the-right-artifact.md)
describes: thorough verification of the wrong object.

## Scope, deliberately narrow

Only the parent repository of the current worktree is flagged. A `cd` into an
*unrelated* repository is frequently correct --- running another repo's checker
is ordinary --- and flagging it would make this noisy enough to switch off.

## Why this warns rather than blocks

Operating on the main checkout is occasionally what someone means: reverting a
stray edit there, or reading a ref that only exists on its branch. Intent is
not observable from the command, so a blocking guard would refuse legitimate
work --- and per
[`deterministic-tools.md`](../shared/principles/deterministic-tools.md) a guard
that refuses legitimate work gets switched off, taking the real cases with it.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys

# `cd` at the start of the command or of any segment (`;`, `&&`, `||`, a
# newline, or a pipe). Quoted and bare targets both.
CD_RE = re.compile(
    r"""(?:^|[;&|\n]|\|\|)\s*cd\s+(?P<q>['"]?)(?P<path>[^'"\s;&|]+)(?P=q)""",
    re.MULTILINE,
)

WORKTREE_MARKER = "/.claude/worktrees/"


def parent_repo_of(cwd: str) -> str | None:
    """Return the repo whose worktree `cwd` is inside, or None."""
    marker = cwd.find(WORKTREE_MARKER)
    if marker == -1:
        return None
    return cwd[:marker]


def cd_targets(command: str, cwd: str) -> list[str]:
    out = []
    for match in CD_RE.finditer(command):
        raw = match.group("path")
        # An unexpanded `$VAR` or `~` needs no special case: it is joined
        # literally, so it cannot equal the repo path, and the equality test
        # below rejects it. An explicit skip here was written first and then
        # removed -- a mutation test showed deleting it changed nothing, which
        # is the definition of a branch that does not earn its place.
        try:
            resolved = os.path.normpath(
                raw if os.path.isabs(raw) else os.path.join(cwd, raw)
            )
        except (ValueError, TypeError):
            continue
        out.append(resolved)
    return out


def evaluate(command: str, cwd: str) -> str | None:
    """Return warning text when the command cd's into the worktree's own repo."""
    repo = parent_repo_of(cwd)
    if not repo:
        return None
    for target in cd_targets(command, cwd):
        if target == repo:
            return (
                "This `cd` targets the MAIN checkout of the repository this "
                f"session has a worktree for:\n\n    cd {repo}\n\n"
                f"Your worktree is {cwd}\n\n"
                "That path is real, valid, and on a DIFFERENT branch --- "
                "routinely a peer session's. Nothing will error: the edit "
                "lands there, and a check run there returns a plausible "
                "result about somebody else's tree.\n\n"
                "Use `git -C <path>` to target a named checkout explicitly, "
                "or drop the `cd` and let the session's own worktree stand.\n\n"
                "See memories/git-worktrees.md, 'In a session rooted in a "
                "worktree, `cd <repo-root>` lands in the MAIN checkout'."
            )
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0

    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    warning = evaluate(command, str(pathlib.Path(cwd)))
    if warning:
        print(warning, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
