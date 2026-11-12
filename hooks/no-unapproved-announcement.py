#!/usr/bin/env python3
"""PreToolUse guard: no class announcement without the user's approval.

Ezra, 2026-10-27, said twice: never post a class announcement without his
review and approval of its exact text (ai-config#4780, from mlg#228). A post
reaches every student at once and cannot be unsent, so this denies.

It fires on a Bash command that creates or edits a Canvas announcement
(`canvas announcements create`, or any command naming `discussion_topics`
with `is_announcement`), and on a Canvas MCP tool whose name says
announcement plus create, post or update, or whose input sets
`is_announcement`. It allows the call only when the latest message the user
typed approves posting an announcement ("post the announcement", "announcement
approved"). Inside a relayed wake, only the user's own cited or principal
messages count, never a coordinator's note. A script file that posts is not
seen; the writer layer (step 3 of skills/draft-in-ezras-voice) and the
reviewer layer (adversarial-reviewer.md) cover it.

Fails closed when the transcript cannot be read, since the post is the harm;
fails open, saying so on stderr, on any other trouble.
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__))), "scripts", "lib"))
    from transcript_meta import is_real_user_turn, strip_injected_text
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-unapproved-announcement: cannot load transcript_meta ({_exc})",
          file=sys.stderr)
    sys.exit(0)

CLI_CREATE = re.compile(r"\bcanvas\s+announcements?\s+(create|post|update|edit)\b")
API_WRITE = re.compile(r"discussion_topics.*is_announcement|is_announcement"
                       r".*discussion_topics", re.S)
MCP_NAME = re.compile(r"announcement.*(create|post|update|edit)|"
                      r"(create|post|update|edit).*announcement")
APPROVAL = re.compile(
    r"\b(post|publish|send|go ahead and post)\b[^.!?\n]{0,40}\bannouncements?\b"
    r"|\bannouncements?\b[^.!?\n]{0,40}\b(approved|is good to go|ok to post|"
    r"okay to post|post it|send it)\b", re.I)
# A relayed wake carries the user's own words in these elements only.
USER_PARTS = re.compile(
    r"<cited author=\"user\"[^>]*>(.*?)</cited>"
    r"|<message[^>]*trust=\"principal\"[^>]*>(.*?)</message>", re.S)


def is_announcement_write(tool, inp):
    if tool == "Bash":
        cmd = (inp.get("command") or "").lower()
        return bool(CLI_CREATE.search(cmd) or API_WRITE.search(cmd))
    if "canvas" in tool.lower():
        flat = json.dumps(inp).lower()
        return bool(MCP_NAME.search(tool.lower())
                    or re.search(r'"is_announcement": (true|"true"|1)', flat))
    return False


def _turn_text(entry):
    msg = entry.get("message")
    content = msg.get("content") if isinstance(msg, dict) else entry.get("content")
    if isinstance(content, str):
        return strip_injected_text(content)
    return "\n".join(strip_injected_text(b.get("text") or "")
                     for b in content or [] if isinstance(b, dict))


def latest_user_text(path):
    """The latest typed user turn, or None when the transcript is unreadable."""
    try:
        with open(path, encoding="utf-8") as fh:
            entries = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError, TypeError):
        return None
    for entry in reversed(entries):
        if is_real_user_turn(entry):
            text = _turn_text(entry)
            parts = USER_PARTS.findall(text)
            if parts or "<coordinator-relay" in text or "<wake" in text:
                return "\n".join(a or b for a, b in parts)
            return text
    return ""


def evaluate(payload):
    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input")
    if not isinstance(inp, dict) or not is_announcement_write(tool, inp):
        return None
    text = latest_user_text(payload.get("transcript_path") or "")
    if text and APPROVAL.search(text):
        return None
    why = ("the transcript could not be read to find it" if text is None
           else "the user's latest message does not approve posting it")
    return (
        f"Refused: this posts or edits a class announcement, and {why} "
        "(Ezra, 2026-10-27, ai-config#4780: never post an announcement "
        "without his review and approval of its exact text).\n\n"
        "Show the exact text in chat and wait for a message that approves "
        "it, such as \"post the announcement\"; then run this again.")


def main() -> int:
    try:
        reason = evaluate(json.load(sys.stdin))
    except Exception as exc:  # fail open, saying so
        print(f"no-unapproved-announcement: could not check call ({exc})",
              file=sys.stderr)
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
