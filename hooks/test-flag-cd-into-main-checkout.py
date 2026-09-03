#!/usr/bin/env python3
"""Tests for flag-cd-into-main-checkout.py.

The NEGATIVE cases carry the weight. This guard's whole risk is noise: a
worktree-rooted session legitimately `cd`s into other repositories all the
time, and a version that flagged those would be switched off within a day,
taking the real cases with it.

The end-to-end cases at the bottom carry the other half: they run the hook as
a subprocess and read the payload it actually prints. `evaluate()` returning
the right text proves nothing about delivery. The hook used to print that text
to stderr and exit 0, which reaches the debug log and nobody else, so every
case above passed while the guard warned nobody (ai-config#3068). Asserting
`additionalContext` is what tells a surfaced warning from a discarded one.

Run: python3 hooks/test-flag-cd-into-main-checkout.py
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "flag-cd-into-main-checkout.py"
spec = importlib.util.spec_from_file_location("guard", HOOK)
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
    #
    # Every entry here MUST contain an actual `cd`. One of them originally did
    # not --- a bare path with `&& ls` --- so it was a silent duplicate of "no
    # cd at all" and covered nothing. Mutation testing could not find it:
    # mutating the guard cannot make a case fire whose INPUT never reaches the
    # matcher, so a vacuous negative case is invisible to exactly the technique
    # that catches a vacuous positive one.
    ("cd to an UNRELATED repo", "cd /home/u/Documents/GitHub/ai-config && python3 s.py"),
    ("cd deeper inside the worktree", f"cd {WT}/subdir && ls"),
    ("cd to the worktree root itself", f"cd {WT} && ls"),
    ("no cd at all", "git status --short"),
    ("git -C against the repo, the correct form", f"git -C {REPO} status --short"),
    ("the repo path mentioned but not cd'd", f"echo {REPO} && grep x f"),
    ("cd to a sibling worktree", f"cd {REPO}/.claude/worktrees/other && ls"),
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


# The count `check_delivery` contributes to the suite total, so a delivery case
# added without updating it shows up as an arithmetic mismatch rather than
# silently going unreported.
DELIVERY_CASES = 5


def run_hook(command: str, cwd: str) -> tuple[int, str, str]:
    """Run the hook as the harness does and return (rc, stdout, stderr)."""
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": cwd,
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def check_delivery() -> int:
    """The warning must reach the session, not just exist.

    A `PreToolUse` hook exiting 0 delivers only through
    `hookSpecificOutput.additionalContext` on stdout: stderr is shown to the
    debug log alone, and plain stdout is not surfaced. So these cases read the
    printed payload rather than asserting that something was printed.
    """
    failures = 0

    rc, out, err = run_hook(f"cd {REPO} && ls", WT)
    if rc != 0:
        print(f"::error::hook must never block; exited {rc}\n{err}", file=sys.stderr)
        return failures + 1

    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        print(f"::error::hook emitted non-JSON on stdout ({exc}): {out!r}",
              file=sys.stderr)
        return failures + 1

    hso = payload.get("hookSpecificOutput") or {}
    context = hso.get("additionalContext")
    if not context:
        print("::error::warning carries no hookSpecificOutput.additionalContext; "
              "on exit 0 anything else reaches the debug log and nobody else",
              file=sys.stderr)
        failures += 1
    elif "MAIN checkout" not in context:
        print(f"::error::additionalContext is not the warning text: {context!r}",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: warning rides on additionalContext")

    if hso.get("hookEventName") != "PreToolUse":
        print(f"::error::hookEventName must be PreToolUse, got "
              f"{hso.get('hookEventName')!r}", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: hookEventName names PreToolUse")

    # This guard must never make the harness more permissive than it was
    # without it.
    if "permissionDecision" in hso:
        print(f"::error::guard emitted permissionDecision="
              f"{hso['permissionDecision']!r}; it must only ever add context",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: no permissionDecision")

    if not payload.get("systemMessage"):
        print("::error::warning carries no one-line systemMessage", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: one-line systemMessage present")

    # A quiet command must print nothing at all, so an empty stdout stays a
    # reliable signal of silence.
    rc, out, err = run_hook("git status --short", WT)
    if rc != 0 or out.strip():
        print(f"::error::quiet case must print nothing; rc={rc} stdout={out!r}",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: quiet case prints nothing")

    return failures


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

    failures += check_delivery()

    total = len(FIRES) + len(QUIET) + len(NOT_A_WORKTREE) + DELIVERY_CASES
    if failures:
        print(f"::error::{failures} of {total} case(s) failed", file=sys.stderr)
        return 1
    print(f"All {total} flag-cd-into-main-checkout cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
