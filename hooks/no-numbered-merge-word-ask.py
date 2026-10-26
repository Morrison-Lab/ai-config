#!/usr/bin/env python3
"""PreToolUse: do not ask the user to type a merge word that names a PR.

ai-config#4698. Ezra, 2026-10-23: "don't make me name each one; mwc them all!"
A bare `mwc` from the user is the merge grant for every ready PR in the
thread's scope, so a message asking him to type `mwc 4699` (or
`mwc owner/repo#4699`, or one word per PR) makes him do hand work the grant
already covers. This is the user-facing counterpart of the merge guards in
no-unauthorized-merge.py, which accept a bare grant.

Blocks (deny) a user-visible reply tool call (mcp__hearthbot__reply,
post_message, update_message) whose text asks for `mwc` followed by a number
or a reference. Inline code is NOT ignored: the ask almost always sits in a
code span. The denial points at the plain word. Fails open on parse trouble.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")

# "mwc 4699", "mwc #4699", "mwc owner/repo#4699", "mwc PR 4699", "/mwc 4699".
NUMBERED = re.compile(
    r"\bmwc\b[`'\"*\s]{0,3}(?:(?:for|on|pr|pull|merge)\s+){0,2}"
    r"(?:[\w.-]+/[\w.-]+)?#?\d+\b",
    re.I,
)

REASON = (
    "[hook: no-numbered-merge-word-ask] This message asks the user to type a merge word that "
    'names a PR ("{phrase}"). A bare `mwc` from the user already covers every ready PR in the '
    "thread's scope (Ezra, 2026-10-23: \"don't make me name each one; mwc them all!\"). "
    "Ask for plain `mwc` instead, and list the ready PRs as links above the ask. "
    "ai-config#4698."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not REPLY_TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    text = tool_input.get("text") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return 0
    match = NUMBERED.search(text)
    if not match:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(phrase=" ".join(match.group(0).split())),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
