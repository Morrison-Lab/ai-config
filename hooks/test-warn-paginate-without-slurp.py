#!/usr/bin/env python3
"""Tests for hooks/warn-paginate-without-slurp.py.

Run: python3 hooks/test-warn-paginate-without-slurp.py
"""

import json
import pathlib
import subprocess
import sys

HOOK = pathlib.Path(__file__).resolve().parent / "warn-paginate-without-slurp.py"

failures = []


def run(command, tool="Bash"):
    payload = json.dumps({"tool_name": tool, "tool_input": {"command": command}})
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input=payload, capture_output=True, text=True
    )
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)


def check(name, condition, detail=""):
    if condition:
        print(f"ok   {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def warns(command):
    """True when the hook surfaced a warning the session will actually see.

    Checks the payload SHAPE, not merely that something was printed: a
    warn-only PreToolUse hook has to emit `hookSpecificOutput.additionalContext`
    (a `systemMessage` alongside it is fine), and output in any other shape is
    discarded rather than surfaced.
    """
    out = run(command)
    if out is None:
        return False
    return "additionalContext" in out.get("hookSpecificOutput", {})


# --- the measured case: the exact command shape that produced a false answer
check(
    "warns on --paginate | jq 'last' with no -s",
    warns("gh api repos/O/R/issues/1/comments --paginate | jq -r '[.[] | select(.body)] | last'"),
)
check(
    "warns on gh --jq with an aggregation (a --jq filter can never slurp)",
    warns("gh api repos/O/R/issues/1/comments --paginate --jq '[.[]] | last'"),
)
check("warns on length", warns("gh api x --paginate | jq '. | length'"))
check("warns on max_by", warns("gh api x --paginate | jq '[.[]] | max_by(.n)'"))

# --- correct usages that must stay silent
check(
    "silent when -s is present",
    not warns("gh api repos/O/R/issues/1/comments --paginate | jq -s -r '[.[][]] | last'"),
)
check(
    "silent when the slurp rides in a cluster (-sr)",
    not warns("gh api x --paginate | jq -sr '[.[][]] | last'"),
)
check(
    "silent for a streaming filter with no aggregation",
    not warns("gh api repos/O/R/pulls --paginate --jq '.[].number'"),
)
check("silent without --paginate", not warns("gh api repos/O/R/pulls | jq '[.[]] | last'"))
check("silent for a non-gh command", not warns("cat pages.json | jq '[.[]] | last'"))
check(
    "silent when the filter lives in a file the guard cannot read",
    not warns("gh api x --paginate | jq -f filter.jq"),
)

# --- a slurp flag in a LATER pipe stage must not silence this jq (review of #3557)
check(
    "warns when a later stage carries -s but this jq does not",
    warns("gh api x --paginate | jq 'last' | column -s,"),
)
check(
    "warns when a SECOND jq slurps but the aggregating one does not",
    warns("gh api x --paginate | jq '[.[]] | last' | jq -s '.'"),
)
check(
    "still silent when the aggregating jq itself slurps and a later stage does not",
    not warns("gh api x --paginate | jq -s '[.[][]] | last' | column -t"),
)

# --- scoping
check("silent for a non-Bash tool", run("gh api x --paginate | jq 'last'", tool="Edit") is None)
check("silent on empty input", run("") is None)
check(
    "only the gh segment counts, not a neighbouring one",
    not warns("gh api x --paginate --jq '.[].id' && cat y | jq '[.[]] | last'"),
)

# --- it must never refuse, only warn, and the warning must be surfaced
out = run("gh api x --paginate | jq 'last'")
check(
    "emits additionalContext, the shape a PreToolUse warning is surfaced in",
    "additionalContext" in out["hookSpecificOutput"],
    sorted(out["hookSpecificOutput"]),
)
check("emits a systemMessage the user sees", bool(out.get("systemMessage")), out.get("systemMessage"))
check(
    "names the offending filter in the systemMessage",
    "jq" in out.get("systemMessage", "") or "paginate" in out.get("systemMessage", ""),
    out.get("systemMessage"),
)
check(
    "emits no permissionDecision, so it can never refuse",
    "permissionDecision" not in out["hookSpecificOutput"],
    sorted(out["hookSpecificOutput"]),
)

# --- malformed input fails open
proc = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True)
check("fails open on malformed payload", proc.returncode == 0 and not proc.stdout.strip())

if failures:
    print(f"\n{len(failures)} test(s) failed")
    sys.exit(1)
print("\nall tests passed")
