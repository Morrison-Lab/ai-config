#!/usr/bin/env python3
"""PreToolUse block: a project-chat post names another session without linking it.

The user's standing rule (2026-10-16, reaffirmed 2026-10-22): every mention of a
session is a link. On 2026-10-22 a reply named "your Mac session" and "the
coordinator" with no link, and the user asked "aren't you supposed to
strengthen the rule?". `no-unlinked-thread-pointer.py` covers "in its thread";
this covers a named session.

Scope: the user-visible reply tools (`mcp__hearthbot__reply`, `post_message`,
`update_message`). Blocks, because the fix is one resend.

What counts:
  - A mention is "Remote Control session", "RC session", "Mac session",
    "Linux session", "cloud session", "local session", "device session",
    "coordinator session", "your ... session", or the word "coordinator".
    "This session" and "a session" are not mentions of another session.
  - A link is `https://claude.ai/code/session_...`, `(#cmsg_...)` or a URL
    carrying `thread=cmsg_...`.
  - The unit is one paragraph or one list item. A mention in a unit with no
    link of its own blocks.
  - Fenced code and inline code spans are removed first.
Fails open on any parse trouble.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(r"(^|__)(reply|post_message|update_message)$")
FENCE = re.compile(
    r"^ {0,3}(```+|~~~+).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.M | re.S)
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
MENTION = re.compile(
    r"\b(?:(?:Remote Control|RC|Mac|Linux|cloud|local|device|coordinator|your)"
    r"(?: \w+)? sessions?|coordinator)\b", re.I)
LINK = re.compile(
    r"claude\.ai/code/session_\w+|\(#cmsg_\w+\)|[?&]thread=cmsg_\w+")
UNIT_BREAK = re.compile(r"\n[ \t]*\n|\n(?=(?:[-*+]|\d+[.)])[ \t])")

REASON = """\
[hook: no-unlinked-session-mention] This post names a session ("{phrase}") \
without a link. The user's standing rule (2026-10-16, reaffirmed 2026-10-22): \
"anytime you mention a session, you must provide a link".
Resend with a link in the same paragraph or list item: \
[session](https://claude.ai/code/session_<id>) for a Claude Code session \
(the id from the status wake or cross-session message, `cse_` becomes \
`session_`), or [thread title](#cmsg_...) for a project thread. Do not type \
an id from memory."""


def unlinked_mention(text: str):
    """The first session mention in a unit with no link, or None."""
    text = FENCE.sub(" ", text.replace("\r\n", "\n"))
    for unit in UNIT_BREAK.split(text):
        unit = INLINE_CODE.sub(" ", unit)
        if LINK.search(unit):
            continue
        m = MENTION.search(unit)
        if m:
            return m.group(0)
    return None


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
    phrase = unlinked_mention(text)
    if not phrase:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(phrase=phrase),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
