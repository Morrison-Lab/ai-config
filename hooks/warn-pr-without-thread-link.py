#!/usr/bin/env python3
"""PreToolUse warn: a project-chat reply links a PR but not the thread that owns it.

ai-config#4565. The user's rule (`shared/writing/link-forge-artifacts.md`,
"Link a PR's project thread too", directive 2026-10-14) is that a message
naming a PR links both the PR and the project thread it belongs to. The
coordinator mentioned a PR in a project-chat post without the thread link
anyway, and the user asked why (2026-10-16). The miss happens at composition
time, so the rule alone did not fire; the condition is decidable at the
moment of sending, from the text of one reply tool call.

Scope: the user-visible reply tools (`mcp__hearthbot__reply`, `post_message`,
`update_message`) and nothing else. Warns, never blocks: a missing link is
cheap to add by resending, and a blocked reply costs the user a turn.

What counts, so the warning stays rare enough to be read:
  - A PR mention is a `github.com/<owner>/<repo>/pull/<N>` URL, in a link or
    bare. A bare `#N` cannot be told from an issue or an ordinal by text
    alone (warn-bare-forge-reference.py covers the unlinked number), so it is
    out of scope here.
  - A thread link is `(#cmsg_...)`, the in-app form, or a URL carrying
    `thread=cmsg_...`, the form used outside the app.
  - The unit is one paragraph or one list item. Each unit that names a PR
    must hold a thread link of its own, so a bulleted status list of three
    PRs with one link at the bottom still warns for the other two.
  - Fenced code and inline code spans are removed first: a PR URL quoted as
    code is not a mention.
  - Nothing can be derived about whether a thread exists for the PR ("wherever
    a thread exists and is relevant"), so the note says to ignore it for a PR
    with no thread.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(r"(^|__)(reply|post_message|update_message)$")
# A fence runs to its closing fence, or to the end of the text when unclosed.
FENCE = re.compile(
    r"^ {0,3}(```+|~~~+).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.M | re.S)
# A code span closes on a backtick run of the same length, across lines.
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
PR_URL = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(\d+)\b")
THREAD_LINK = re.compile(r"\(#cmsg_\w+\)|[?&]thread=cmsg_\w+")
# A blank line ends a paragraph; a list marker starts a new item.
UNIT_BREAK = re.compile(r"\n[ \t]*\n|\n(?=[ \t]*(?:[-*+]|\d+[.)])[ \t])")

NOTE = """\
[hook: warn-pr-without-thread-link] This reply names {prs} without \
linking the project thread that owns it. The user's rule: a message that \
names a PR links both the PR and its thread, written \
[thread title](#cmsg_...) in the app (shared/writing/link-forge-artifacts.md, \
"Link a PR's project thread too").
Resend with the thread link beside each PR. Get the thread id from \
list_thread_sessions, project memory, or the PR's attribution block; do not \
type an id from memory. If a listed PR has no thread, ignore this note."""


def strip_code(text: str) -> str:
    return INLINE_CODE.sub(" ", FENCE.sub(" ", text))


def unlinked_prs(text: str) -> list[str]:
    seen: list[str] = []
    for unit in UNIT_BREAK.split(strip_code(text)):
        if THREAD_LINK.search(unit):
            continue
        for match in PR_URL.finditer(unit):
            ref = f"{match.group(1)}#{match.group(2)}"
            if ref not in seen:
                seen.append(ref)
    return seen


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
    prs = unlinked_prs(text)
    if not prs:
        return 0
    shown = ", ".join(f"`{p}`" for p in prs[:5])
    if len(prs) > 5:
        shown += f" and {len(prs) - 5} more"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(prs=shown),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
