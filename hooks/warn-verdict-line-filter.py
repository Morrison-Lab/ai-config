#!/usr/bin/env python3
"""PreToolUse warning: review round comments read through a verdict-line filter.

A Bash command that fetches PR review comments and narrows the comment body to
verdict lines drops non-blocking findings in the body and in the review-data
JSON findings array.
Measured 2026-09-09 on ai-config#3493: two findings carried over unaddressed.
"""

from __future__ import annotations

import json
import re
import sys

RX_FETCH_COMMENTS = re.compile(
    r"issues/\d+/comments|pulls/\d+/comments|--json\s+comments|--json\s+reviews"
)

RX_VERDICT_LINES = re.compile(
    r'split\("(\\n|\n)"\)|test\("[^"]*(?:Verdict|Ready for merge|NOT CLEAN|Reviewed commit)[^"]*"\)|\.\[\d+:\d+\]'
)

NOTE = (
    "this filter prints only the verdict lines of a review round; a round can "
    "be Ready for merge and still carry non-blocking findings in its body and "
    "in the review-data JSON findings array, which this filter drops "
    "(measured 2026-09-09, ai-config#3493, two findings carried over unaddressed); "
    "read the full body of every round since the last one you processed, or parse "
    "the review-data findings array, before reporting the PR's state."
)


def should_warn(command: str) -> bool:
    """True when command matches comment fetch and verdict lines without findings."""
    if not RX_FETCH_COMMENTS.search(command):
        return False
    if not RX_VERDICT_LINES.search(command):
        return False
    if "findings" in command or "review-data" in command:
        return False
    return True


def _emit(note: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": note,
                }
            }
        )
    )


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def main() -> int:
    try:
        payload, _is_dry_run = _read_payload()
        if not payload or not isinstance(payload, dict):
            return 0

        tool_name = payload.get("tool_name")
        if tool_name not in (
            "Bash",
            "bash",
            "run_command",
            "execute_command",
            "terminal",
            "shell",
        ):
            return 0

        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0

        command = (
            tool_input.get("command")
            or tool_input.get("cmd")
            or tool_input.get("CommandLine")
            or ""
        )
        if not isinstance(command, str) or not command.strip():
            return 0

        if should_warn(command):
            _emit(NOTE)
    except Exception:
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
