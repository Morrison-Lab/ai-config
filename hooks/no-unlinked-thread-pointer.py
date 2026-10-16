#!/usr/bin/env python3
"""PreToolUse block: a project-chat post sends the reader to a thread without linking it.

ai-config#4590. On 2026-10-16 the coordinator listed merge words for the user
with "each in its thread" and no thread links, and the user asked "what threads
are those? you're supposed to give them to me". `warn-pr-without-thread-link.py`
(#4565) covers a PR URL with no thread link; this covers the phrase alone,
which names no PR and so slipped past it.

Scope: the user-visible reply tools (`mcp__hearthbot__reply`, `post_message`,
`update_message`). Blocks, because a pointer the reader cannot follow costs the
reader a turn, and the fix is one resend.

What counts:
  - A pointer is "in its thread", "in that thread", "in their threads",
    "in each thread", "in the relevant thread" and the like, with at most one
    word ("own", "PR") before "thread". "In this thread" is not one: it names where the reader already is.
  - A thread link is `(#cmsg_...)`, the in-app form, or a URL carrying
    `thread=cmsg_...`, the form used outside the app.
  - The unit is one paragraph or one list item, as in
    warn-pr-without-thread-link.py. A pointer in a unit with no thread link of
    its own blocks, so a list of three "each in its thread" items with one link
    at the bottom still blocks for the other two.
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
POINTER = re.compile(
    r"\bin (?:its|that|their|each|every|the (?:relevant|respective|matching|right|"
    r"owning|same))(?: \w+)? threads?\b", re.I)
THREAD_LINK = re.compile(r"\(#cmsg_\w+\)|[?&]thread=cmsg_\w+")
UNIT_BREAK = re.compile(r"\n[ \t]*\n|\n(?=(?:[-*+]|\d+[.)])[ \t])")

REASON = """\
[hook: no-unlinked-thread-pointer] This post says "{phrase}" without linking \
the thread it points to. The user cannot follow a pointer they cannot click \
(ai-config#4590, 2026-10-16: "what threads are those? you're supposed to give \
them to me").
Resend with a [thread title](#cmsg_...) link in the same paragraph or list \
item as each pointer. Get the thread id from list_thread_sessions, project \
memory, or the PR's attribution block; do not type an id from memory."""


def unlinked_pointer(text: str):
    """The first pointer phrase in a unit with no thread link, or None."""
    text = FENCE.sub(" ", text.replace("\r\n", "\n"))
    for unit in UNIT_BREAK.split(text):
        unit = INLINE_CODE.sub(" ", unit)
        if THREAD_LINK.search(unit):
            continue
        m = POINTER.search(unit)
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
    phrase = unlinked_pointer(text)
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
