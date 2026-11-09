#!/usr/bin/env python3
"""Stop-hook guard: a turn answered the user without trying anything, and never searched the tool list.

THE MEASURED CASE (2026-11-09, Data 571 runner thread, ai-config#5136)
Ezra asked a runner to switch its own permission mode.  It replied "I can't, only
you control that" without looking at its tools, though it had a mode-switch tool.
A phrase regex for "I can't" failed six review rounds on ai-config#5137 (idioms,
reflexives, literal senses), so this hook decides from the transcript's STRUCTURE.

WHAT IT CHECKS (no phrase match anywhere)
Since the user's last real message, the turn made no tool call except the reply
tool itself (post_message and the like), and no ToolSearch.  Such a turn answered
without trying anything or looking at its tools; a refusal that skipped the tool
list always has this shape.  Plain answers to questions have it too, so the notice
is a prompt to look, not an accusation.

WHY A WARNING, AND ITS COST
Whether a tool exists is not decidable from the transcript.  The stop is interrupted
once per message (agent_notice.stop_notice), so a false hit costs one extra turn.
Turns with any other tool call (a read, a search, an edit) never fire.

transcript-shapes-skip: antigravity -- Antigravity sessions have no deferred-tool search, so the ToolSearch condition cannot hold there.

See shared/workflow/check-tools-before-saying-cant.md.  Fails OPEN.
"""
import json
import os
import re
import sys

_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
from agent_notice import stop_notice  # noqa: E402

REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message|no_reply_needed)$", re.I)


def _blocks(msg):
    blocks = (msg.get("message") or {}).get("content") or msg.get("content") or []
    return blocks if isinstance(blocks, list) else []


def reply_only_turn(path):
    """(True when the turn replied and made no other tool call, the reply text)."""
    other = replied = False
    reply = ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("type") == "user" or m.get("role") == "user":
                    content = _blocks(m)
                    if not any(isinstance(b, dict) and b.get("type") == "tool_result"
                               for b in content):
                        other = replied = False
                        reply = ""
                    continue
                if not (m.get("type") == "assistant" or m.get("role") == "assistant"):
                    continue
                for b in _blocks(m):
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    if REPLY_TOOL_RX.search(b.get("name") or ""):
                        replied = True
                        inp = b.get("input")
                        t = inp.get("text") if isinstance(inp, dict) else None
                        if isinstance(t, str) and t.strip():
                            reply = t
                    else:
                        other = True
    except Exception:
        return False, ""
    return replied and not other, reply


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        flagged, _reply = reply_only_turn(payload.get("transcript_path") or "")
    except Exception:
        return 0
    if not flagged:
        return 0
    # Once-per-message dedup is stop_notice's, scoped by session and turn.  A sentinel keyed
    # on the reply text would suppress unrelated sessions that reply alike (review of #5141).
    print(stop_notice(
        payload,
        "This turn replied without making any tool call or searching for tools. If the "
        "reply declines an action, or says only the user can do it, check your visible "
        "tool list and call ToolSearch with the action's keywords first (deferred tools "
        "are not in the list, e.g. mcp__ccd_session_mgmt__set_session_permission_mode), "
        "and use the tool if one fits (Ezra, 2026-11-09: \"never forget to check your "
        "available tools\"). If it only answers a question, ignore this. "
        "See shared/workflow/check-tools-before-saying-cant.md.",
        "flag-reply-without-tool-search",
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
