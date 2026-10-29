#!/usr/bin/env python3
"""PreToolUse block: a thread's reply links the thread it is posted in.

ai-config#4843. The link rules (`shared/writing/link-forge-artifacts.md`) are for
pointing the reader at another thread or session. Threads applied them to
themselves ("This is in [Qualify residual risk](#cmsg_...)", inside that very
thread) and the user asked why (2026-10-29).

A thread session knows its own id: the first wake in its transcript carries
`<thread ts="cmsg_...">`, and the transcript says "You are a Thread Session".
Any other session (the coordinator, a Claude Code session) has no own thread
and is never blocked.

Scope: the user-visible reply tools (`mcp__hearthbot__reply`, `post_message`,
`update_message`). Blocks, because the fix is one resend.

What counts: `(#<own id>)` or a URL carrying `thread=<own id>` in the text,
after fenced code and inline code spans are removed. A link to any other thread is fine. Fails open on
any parse trouble, including an unreadable transcript.
"""
import json
import re
import sys

REPLY_TOOL = re.compile(r"(^|__)(reply|post_message|update_message)$")
FENCE = re.compile(
    r"^ {0,3}(```+|~~~+).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.M | re.S)
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
THREAD_TS =re.compile(r'<thread ts="(cmsg_\w+)"')
THREAD_SESSION = "You are a Thread Session"

REASON = """\
[hook: no-self-thread-link] This reply links the thread it is posted in \
(`{cmsg}`). The link rules are for other threads and sessions; the reader is \
already here (ai-config#4843, 2026-10-29: "threads have started providing \
links to themselves; why?").
Resend without that link, saying "this thread" if you need to refer to it. \
Keep links to other threads."""


def own_thread_id(transcript_path):
    """The id of the thread this session works in, or None for any other session."""
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            head = f.read(200_000)
    except (OSError, TypeError, ValueError):
        return None
    if THREAD_SESSION not in head:
        return None
    m = THREAD_TS.search(head)
    return m.group(1) if m else None


def self_link(text, cmsg):
    text = INLINE_CODE.sub(" ", FENCE.sub(" ", text.replace("\r\n", "\n")))
    return re.search(
        rf"\(#{re.escape(cmsg)}\)|[?&]thread={re.escape(cmsg)}\b", text) is not None


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
    cmsg = own_thread_id(payload.get("transcript_path"))
    if not cmsg or not self_link(text, cmsg):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(cmsg=cmsg),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
