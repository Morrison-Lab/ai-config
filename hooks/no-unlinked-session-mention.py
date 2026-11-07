#!/usr/bin/env python3
"""PreToolUse block: a project-chat post names another session without linking it.

The user's standing rule (2026-10-16, reaffirmed 2026-10-22): every mention of a
session is a link. On 2026-10-22 a reply named "your Mac session" and "the
coordinator" with no link, and the user asked "aren't you supposed to
strengthen the rule?". `no-unlinked-thread-pointer.py` covers "in its thread";
this covers a named session.

Scope: the user-visible reply tools (`mcp__hearthbot__reply`, `post_message`,
`update_message`, `edit_message`). An edit is a post the user reads, so it is
held to the same rule: on 2026-11-03 an edit named "the thread that owns that
runner" with no link and passed, and the user said "always hyperlink when you
mention other threads". Blocks, because the fix is one resend.

What counts:
  - A mention is "Remote Control session", "RC session", "Mac session",
    "Linux session", "cloud session", "local session", "device session",
    "coordinator session", "your ... session", or the word "coordinator".
    The same prefixes before "chat" count too ("the ab12-03 chat", "your Mac
    chat"), as do "that chat" and "other chat" (ai-config#4878).
    "This session", "a session", "this chat" and "the project chat" are not
    mentions of another session.
  - A link is `https://claude.ai/code/session_...`, `(#cmsg_...)` or a URL
    carrying `thread=cmsg_...`.
  - A bare "session" or "thread" counts when the word before it points at
    another session: "the", "that", "those", "other", "another", "my",
    "our", "their", "its", "previous", "earlier", "prior", "parent",
    "child", "sibling", or a host id such as "ab12-03" ("the session",
    "that thread", "the ab12-03 session"). Any other word before it, as in
    "the R session", "a training session" or "the support thread", names
    nothing to link, so it is not a mention.
  - The unit is one paragraph or one list item. A mention in a unit with no
    link of its own blocks.
  - Fenced code and inline code spans are removed first.
Fails open on any parse trouble.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(
    r"(^|__)(reply|post_message|update_message|edit_message)$")
FENCE = re.compile(
    r"^ {0,3}(```+|~~~+).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.M | re.S)
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
MENTION = re.compile(
    r"\b(?:(?:Remote Control|RC|Mac|Linux|cloud|local|device|coordinator|your)"
    r"(?: \w+){0,2} sessions?|coordinator"
    # ai-config#4878: a Remote Control session called a "chat".
    r"|(?:Remote Control|RC|Mac|Linux|cloud|local|device|your|[a-z]+\d+-\d+)"
    r"(?: \w+){0,2} chats?|(?:that|those|other) chats?)\b", re.I)
# ai-config (Ezra, 2026-11-02, "always link to the session"): any other
# session or thread, however it is named ("the ab12-03 session", "the runner
# thread", "that session"). The word before it decides: a determiner that
# names this session or an unspecific one is not a mention.
GENERIC = re.compile(r"(?<![\w-])([\w-]+) (sessions?|threads?)\b", re.I)
POINTING = {"the", "that", "those", "other", "another", "my", "our", "their",
            "its", "previous", "earlier", "prior", "parent", "child",
            "sibling"}
HOST_ID = re.compile(r"[a-z]+\d+-\d+", re.I)
# ai-config#5058 (Ezra, 2026-11-07, "always hyperlink; don't make me ask"):
# a descriptive name between a pointing word and "thread" ("the runner
# thread", "the CI thread") names a project thread. These words name a
# technical or forge thread instead and stay exempt.
NAMED_THREAD = re.compile(
    r"(?<![\w-])(?:the|that|those|other|another|my|our|their|its|your)"
    r" ([\w-]+) threads?\b", re.I)
TECHNICAL_THREAD = {
    "main", "worker", "review", "support", "comment", "email", "forum",
    "discussion", "reply", "background", "conversation", "os", "kernel", "gui",
    "ui", "io", "gpu", "cpu", "python", "r", "julia", "java", "jvm", "event",
    "render", "download", "upload", "polling", "daemon"}
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
`session_`), or [thread title](#cmsg_...) for a project thread (find its \
title and id with `list_threads`). Do not type an id from memory.
If the phrase is not a Claude Code session or project thread (an R, database \
or debugger session, an OS thread), put it in backticks and resend."""


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
        for g in GENERIC.finditer(unit):
            before = g.group(1)
            if before.lower() in POINTING or HOST_ID.fullmatch(before):
                return g.group(0)
        for n in NAMED_THREAD.finditer(unit):
            if n.group(1).lower() not in TECHNICAL_THREAD:
                return n.group(0)
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
