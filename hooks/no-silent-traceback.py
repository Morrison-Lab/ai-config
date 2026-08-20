#!/usr/bin/env python3
"""PostToolUse warning: Bash succeeded while its output carries a traceback.

Observed 2026-08-19 in a ucdavis/bcs session: a heredoc Python script raised,
but a later `Rscript` line on the next line ran anyway and the call exited 0.
With no `set -e`, the failure is invisible unless the output is read.

Unlike most "I was wrong" cases, the condition is lexically decidable from one
artifact --- the tool result --- with no domain knowledge:

  PostToolUse fired (the harness treated the call as successful), **and**
  combined stdout/stderr contains a line matching
  `^Traceback \\(most recent call last\\):`.

Whole-line anchoring, not substring, so prose quoting the phrase does not
match --- the same whole-line anchoring `no-placeholder-reply.py` uses for its
own quoted-string problem.

WHY THIS WARNS RATHER THAN BLOCKS
---------------------------------
A command that deliberately prints a captured traceback and legitimately
succeeds must cost a line of noise, not a refused tool call. Same shape as
`remind-ums-after-error.py`: inject-only, never block.

Fails OPEN on any parse trouble.
"""
import json
import re
import sys

TRACEBACK = re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE)

NOTE = """\
A Bash call returned success but its output contains a Python traceback
(`Traceback (most recent call last):` at line start).

With no `set -e`, a heredoc or earlier command can fail while a later command
in the same call succeeds, and the call still exits 0. Do not trust the result
until you have read the full output --- the intended edit may not have happened.
"""


def combined_output(tool_response):
    if not isinstance(tool_response, dict):
        return ""
    parts = []
    for key in ("stdout", "stderr"):
        val = tool_response.get(key)
        if isinstance(val, str) and val:
            parts.append(val)
    return "\n".join(parts)


def should_warn(payload):
    if payload.get("tool_name") != "Bash":
        return False
    text = combined_output(payload.get("tool_response"))
    return bool(TRACEBACK.search(text))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"no-silent-traceback: unreadable hook input ({exc})", file=sys.stderr)
        return 0

    if not isinstance(payload, dict):
        return 0

    try:
        warn = should_warn(payload)
    except Exception as exc:
        print(f"no-silent-traceback: could not inspect output ({exc})", file=sys.stderr)
        return 0

    if not warn:
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": NOTE,
        },
        "systemMessage": (
            "Bash succeeded but output contains a Python traceback."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
