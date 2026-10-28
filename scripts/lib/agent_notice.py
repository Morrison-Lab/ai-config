#!/usr/bin/env python3
"""Hook output that reaches the agent, not only the user (ai-config#4796).

Claude Code shows a hook's `systemMessage` to the user and never to the model,
so a hook whose only output is `systemMessage` cannot change what the agent
does next. Measured on 2026-10-27 in a lds session: `require-stopping-point.py`
fired on several replies and the agent never saw one warning, so the user had
to ask "session done?" and then "why didn't you say so before?", exactly as in
#4308.

`stop_notice` is for Stop / SubagentStop hooks. It blocks the stop with the
message as the `reason`, which the model reads and acts on, at most once per
hook per turn, and never while `stop_hook_active` is set, so a hook can never
hold a session in a loop (the concern behind #4322). When it does not block it
falls back to `systemMessage`, so the user still sees the note.

`context_notice` is for PreToolUse, PostToolUse, UserPromptSubmit and
SessionStart hooks. It puts the message in `hookSpecificOutput.additionalContext`,
which the model reads, without denying the tool call, and keeps `systemMessage`
for the user.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile

_LIB = os.path.dirname(os.path.realpath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

try:
    from turn_id import extract_turn_id
except Exception:  # broken install: fall back to a per-message key
    def extract_turn_id(payload: dict) -> str:  # noqa: D103
        return ""


def _session_id(payload: dict) -> str:
    return str(
        payload.get("session_id")
        or payload.get("sessionId")
        or os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("SESSION_ID")
        or ""
    )


def _first_block_this_turn(payload: dict, hook: str, message: str) -> bool:
    """True the first time `hook` asks to block in this session's current turn."""
    turn = extract_turn_id(payload) or hashlib.sha256(message.encode()).hexdigest()
    transcript = str(payload.get("transcript_path") or payload.get("transcriptPath") or "")
    key = hashlib.sha256(
        f"{_session_id(payload)}:{transcript}:{turn}:{hook}".encode()
    ).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-agent-notice-{key}")
    if os.path.exists(sentinel):
        return False
    try:
        open(sentinel, "w", encoding="utf-8").close()
    except OSError:
        return False  # cannot record the block, so do not risk repeating it
    return True


def stop_notice(payload: dict, message: str, hook: str) -> str:
    """JSON for a Stop hook: block once per turn so the agent sees `message`."""
    if not payload.get("stop_hook_active") and _first_block_this_turn(payload, hook, message):
        return json.dumps({"decision": "block", "reason": message, "systemMessage": message})
    return json.dumps({"systemMessage": message})


def context_notice(message: str, event: str = "PreToolUse") -> str:
    """JSON for a non-Stop hook: add `message` to the model's context, allow the action."""
    return json.dumps({
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": message},
        "systemMessage": message,
    })
