#!/usr/bin/env python3
"""Tests for flag-chained-push.py.

Mirrors `test-flag-cd-into-main-checkout.py`'s shape: a lexical FIRES/QUIET
split for `evaluate()`, then an end-to-end delivery check that runs the hook
as a subprocess and reads the payload it actually prints -- `evaluate()`
returning the right text proves nothing about whether the warning reaches the
session (ai-config#3068 recorded exactly that gap for a sibling hook).

Run: python3 hooks/test-flag-chained-push.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "flag-chained-push.py"
spec = importlib.util.spec_from_file_location("guard", HOOK)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

FIRES = [
    ("chained after a commit with &&",
     'git add -A && git commit -m "x" && git push'),
    ("chained after a plain command with ;",
     "git status; git push"),
    ("chained after a command with ||",
     "git status || git push"),
    ("piped onward",
     "git push origin HEAD | tee push.log"),
    ("fd-duplication redirect (the digit-as-token shape)",
     "git push origin HEAD 2>&1"),
    ("fd-duplication redirect piped onward",
     "git push origin HEAD 2>&1 | tee push.log"),
    ("plain output redirect",
     "git push origin HEAD > push.log"),
    ("append redirect",
     "git push origin HEAD >> push.log"),
    ("bash &> shorthand",
     "git push origin HEAD &> push.log"),
    ("chained before, with -C",
     "cd /repo && git -C /repo push origin HEAD"),
    ("chained before, across a newline",
     "git fetch origin\ngit push"),
    ("chained after, with a preceding pipeline unrelated to the push",
     "echo hi | cat; git push"),
]

QUIET = [
    ("bare git push", "git push origin HEAD"),
    ("bare git push with the safe force form, alone",
     "git push --force-with-lease --force-if-includes"),
    ("bare git -C push, alone", "git -C /repo push origin HEAD"),
    ("push mentioned inside a double-quoted string",
     'git commit -m "push it live"'),
    ("push mentioned inside a single-quoted string",
     "git commit -m 'remember to push later'"),
    ("git push inside a heredoc body",
     "cat <<'EOF'\ngit push origin main\nEOF"),
    ("no push at all", "git status --short && git log -1"),
    ("push followed by && but nothing before or after IT specifically",
     "git push && echo done"),
]


DELIVERY_CASES = 7


def run_hook(command: str, antigravity: bool = False):
    """Run the hook as the harness does and return (rc, stdout, stderr)."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    env = {k: v for k, v in os.environ.items() if k != "ANTIGRAVITY_AGENT"}
    if antigravity:
        env["ANTIGRAVITY_AGENT"] = "1"
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def check_delivery():
    """The warning must reach the session, not just exist in `evaluate()`.

    Returns `(failures, ran)`, with `ran` incremented BEFORE each check so
    the count is meaningful on both the passing and failing path -- `main`
    refuses a run whose count differs from `DELIVERY_CASES`, so a deleted
    check cannot silently shrink what the suite claims to cover.
    """
    failures = 0
    ran = 0

    rc, out, err = run_hook("git status && git push")
    ran += 1
    if rc != 0:
        print(f"::error::hook must never block; exited {rc}\n{err}", file=sys.stderr)
        return failures + 1, ran

    ran += 1
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        print(f"::error::hook emitted non-JSON on stdout ({exc}): {out!r}",
              file=sys.stderr)
        return failures + 1, ran

    hso = payload.get("hookSpecificOutput") or {}
    context = hso.get("additionalContext")
    ran += 1
    if not context:
        print("::error::warning carries no hookSpecificOutput.additionalContext",
              file=sys.stderr)
        failures += 1
    elif "git push" not in context:
        print(f"::error::additionalContext is not the warning text: {context!r}",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: warning rides on additionalContext")

    ran += 1
    if hso.get("hookEventName") != "PreToolUse":
        print(f"::error::hookEventName must be PreToolUse, got "
              f"{hso.get('hookEventName')!r}", file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: hookEventName names PreToolUse")

    # This guard must never make the harness more permissive than it was
    # without it.
    ran += 1
    if "permissionDecision" in hso:
        print(f"::error::guard emitted permissionDecision="
              f"{hso['permissionDecision']!r}; it must only ever add context",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: no permissionDecision")

    # A quiet command must print nothing at all.
    rc, out, err = run_hook("git push origin HEAD")
    ran += 1
    if rc != 0 or out.strip():
        print(f"::error::quiet case must print nothing; rc={rc} stdout={out!r}",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: quiet case prints nothing")

    # Antigravity's adapter prints `additionalContext` and every collected
    # `systemMessage` separately, so a payload carrying both would warn
    # twice there.
    rc, out, err = run_hook("git status && git push", antigravity=True)
    ran += 1
    try:
        ag = json.loads(out) if rc == 0 else {}
    except json.JSONDecodeError:
        ag = {}
    ag_context = (ag.get("hookSpecificOutput") or {}).get("additionalContext")
    if not ag_context:
        print(f"::error::ANTIGRAVITY_AGENT output must carry additionalContext; "
              f"rc={rc} stdout={out!r}", file=sys.stderr)
        failures += 1
    elif "systemMessage" in ag:
        print("::error::ANTIGRAVITY_AGENT output must not carry systemMessage",
              file=sys.stderr)
        failures += 1
    else:
        print("OK   delivers: under ANTIGRAVITY_AGENT, context only")

    return failures, ran


def main() -> int:
    failures = 0

    for label, command in FIRES:
        if guard.evaluate(command) is None:
            print(f"::error::expected a warning: {label}\n    {command!r}",
                  file=sys.stderr)
            failures += 1
        else:
            print(f"OK   fires: {label}")

    for label, command in QUIET:
        result = guard.evaluate(command)
        if result is not None:
            print(f"::error::expected silence: {label}\n    {command!r}\n{result}",
                  file=sys.stderr)
            failures += 1
        else:
            print(f"OK   quiet: {label}")

    # The message must name the alternative, or it teaches nothing.
    message = guard.evaluate("git status && git push")
    for needed in ("no-clobbering-push.py", "own Bash call",
                   "check-before-pushing.md"):
        if needed not in message:
            print(f"::error::warning text omits {needed!r}", file=sys.stderr)
            failures += 1

    delivery_failures, delivery_ran = check_delivery()
    failures += delivery_failures
    if delivery_ran != DELIVERY_CASES:
        print(f"::error::check_delivery ran {delivery_ran} case(s), but "
              f"DELIVERY_CASES says {DELIVERY_CASES}", file=sys.stderr)
        failures += 1

    total = len(FIRES) + len(QUIET) + DELIVERY_CASES
    if failures:
        print(f"::error::{failures} of {total} case(s) failed", file=sys.stderr)
        return 1
    print(f"All {total} flag-chained-push cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
