#!/usr/bin/env python3
"""PreToolUse: do not ask the user to type a merge word in another thread without reading it.

ai-config#5013. On 2026-11-05 a thread asked Ezra twice to type `mwc` in
another thread ("HW 3 edits") for lds#1868, a PR that thread owned. He had
already typed it there at 22:04Z, and the coordinator had to correct the asking
thread.

Whether the other thread already holds a merge word is a question a read
answers, so the condition is decidable from the transcript:

    the reply asks for a merge word (`mwc`, "merge word", "go-ahead") IN another
    thread -- a `#cmsg_` link or "in the ... thread" within the same sentence
    AND no hearthbot read of a thread (read_thread, read_messages_by_id,
    read_project_chat, list_threads) ran since the last user turn

Denies a user-visible reply tool call (post_message, reply, update_message,
edit_message). The denial says to read the owning thread first: when a merge
word is already there, say the PR waits on its owner and ask nothing.
Fails open on any parse trouble, including a missing transcript.
"""
import json
import os
import re
import sys

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

REPLY_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")
THREAD_READ_TOOL = re.compile(
    r"^mcp__hearthbot__(?:read_thread|read_messages_by_id|read_project_chat|list_threads)$"
)

ASK = re.compile(
    r"\b(?:type|say|send|post|reply with|write|give|add)\b[^.!?\n]{0,60}?"
    r"(?:\bmwc\b|\bmerge words?\b|\bgo-?ahead\b)",
    re.I,
)
# "in [HW 3 edits](#cmsg_...)", "in the HW 3 edits thread", "in that thread".
OTHER_THREAD = re.compile(
    r"\bin\s+(?:the\s+|that\s+|this\s+)?(?:\[[^\]]*\]\(#cmsg_[^)]*\)|[^.!?\n]{0,60}?\bthread\b)",
    re.I,
)

REASON = (
    "[hook: no-mwc-ask-in-other-thread-unread] This message asks the user to type a merge word "
    'in another thread ("{phrase}") and nothing since the last user turn read a thread. '
    "He may have typed it there already: on 2026-11-05 a thread asked twice for an `mwc` he had "
    "typed at 22:04Z (lds#1868). Read the owning thread first (hearthbot read_thread, or "
    "read_messages_by_id). If a merge word is there, say the PR waits on its owner and ask "
    "nothing. ai-config#5013."
)


def _is_user_turn(entry):
    try:
        from transcript_meta import is_real_user_turn

        return is_real_user_turn(entry)
    except Exception:
        return entry.get("type") == "user" and not entry.get("isMeta")


def read_a_thread_this_turn(path):
    """True when a hearthbot thread read ran since the last real user turn."""
    seen = False
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            if _is_user_turn(entry):
                seen = False
            blocks = (entry.get("message") or {}).get("content") or entry.get("content")
            for block in blocks if isinstance(blocks, list) else []:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and THREAD_READ_TOOL.match(str(block.get("name") or ""))
                ):
                    seen = True
    return seen


def find_ask(text):
    """The first sentence that asks for a merge word in another thread, or None."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        ask = ASK.search(sentence)
        if ask and OTHER_THREAD.search(sentence[ask.start():]):
            return " ".join(sentence.split())[:120]
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not REPLY_TOOL.match(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    text = tool_input.get("text") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return 0
    phrase = find_ask(text)
    if not phrase:
        return 0
    path = payload.get("transcript_path")
    try:
        if isinstance(path, str) and read_a_thread_this_turn(path):
            return 0
    except OSError:
        return 0
    if not isinstance(path, str):
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
