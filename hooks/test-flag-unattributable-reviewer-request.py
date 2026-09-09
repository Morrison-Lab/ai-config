#!/usr/bin/env python3
"""Tests for flag-unattributable-reviewer-request.py.

The cases that matter are the NEGATIVE ones. This hook predicts another hook's
discharge, so a false positive tells the reader their correct command is broken
-- and the natural response to that is to distrust the hook, which takes the
real cases with it (README, "A hook that misfires is worse than a missing one").

Run: python3 hooks/test-flag-unattributable-reviewer-request.py [HOOK_PATH]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent
            / "flag-unattributable-reviewer-request.py").resolve()

REQ = ("gh api \"repos/Morrison-Lab/ai-config/pulls/3403/requested_reviewers\" "
       "-X POST -f 'reviewers[]=copilot-pull-request-reviewer[bot]'")

# (name, command, expect_warning)
CASES = [
    # --- the measured incident, and the form that actually discharged --------
    ("the incident: request piped to tail", REQ + " --jq '.number' 2>&1 | tail -3", True),
    ("the bare request that discharged", REQ, False),

    # --- position is the whole rule -----------------------------------------
    # A request LAST after `&&` is creditable: either it ran and its status is
    # the call's, or an earlier command short-circuited it away leaving a
    # failure the discharge withholds on. Both safe, per request_ident.
    ("request last after &&", "cd /tmp && " + REQ, False),
    ("request last after ;", "echo hi; " + REQ, False),
    ("request FIRST, another command after", REQ + " && gh pr view 3403", True),
    ("request first, then a verify read", REQ + "; gh pr view 3403 --json reviews", True),

    # --- a bare redirect preserves the command's own exit status -------------
    # This is the case a naive "is it the only command" rule gets wrong.
    ("request with > /dev/null only", REQ + " > /dev/null", False),

    # --- not a request at all ------------------------------------------------
    ("a GET of the same endpoint piped", 
     "gh api \"repos/o/r/pulls/1/requested_reviewers\" | jq .", False),
    ("an unrelated piped command", "gh pr view 3403 --json reviews | jq .", False),
    ("empty command", "", False),

    # --- robustness ----------------------------------------------------------
    ("non-Bash tool payload", None, False),   # handled specially below
]


def run(command):
    if command is None:
        payload = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}
    else:
        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"hook exited {proc.returncode}: {proc.stderr[:300]}")
    if not proc.stdout.strip():
        return {}
    return json.loads(proc.stdout)


def main() -> int:
    passed = failed = 0
    for name, command, expect in CASES:
        try:
            out = run(command)
        except AssertionError as exc:
            print(f"FAIL: {name} ({exc})")
            failed += 1
            continue
        got = bool(out.get("hookSpecificOutput", {}).get("additionalContext"))
        if got == expect:
            print(f"PASS: {name}")
            passed += 1
        else:
            print(f"FAIL: {name} (expected warn={expect}, got warn={got})")
            failed += 1

    # The hook must never block, whatever it decides.
    out = run(REQ + " | tail -1")
    hso = out.get("hookSpecificOutput", {})
    if "permissionDecision" in hso:
        print("FAIL: hook emitted a permissionDecision; it must only add context")
        failed += 1
    else:
        print("PASS: hook never emits a permissionDecision")
        passed += 1

    # A warning must name the PR, so the reader can tell which request it means.
    out = run(REQ + " && gh pr view 3403")
    ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
    if "3403" in ctx:
        print("PASS: the warning names the PR")
        passed += 1
    else:
        print("FAIL: the warning does not name the PR")
        failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
