#!/usr/bin/env python3
"""Whether the user has paused this session (ai-config#3911).

A session is paused while the user's most recent prompt is a pause command:
`pause` typed bare (optionally followed by a short note, such as
"pause, back after lunch"), or the `/pause` skill.
Any later prompt from the user ends the pause, so there is no marker file to
create or clean up, and a session in the cloud needs no Bash call to pause.

Stop hooks read this through `agent_notice.stop_notice`, and the Stop hooks
that block directly call `is_paused` themselves. While paused they stop
demanding work (push this commit, file that issue, write a stopping point),
since doing it would start the new work the pause was there to prevent.
Hooks that only refuse an action (the merge and push guards) do not read it:
a refusal never forces work, so a pause has no reason to switch it off.
"""
from __future__ import annotations

import json
import re

# A bare "pause" prompt, with at most a short note after it.
_BARE = re.compile(r"\A\s*/?(?:ai-config:)?pause\b[\s,.:;!-]*(?P<rest>.*)\Z", re.I | re.S)
# The same command invoked as a skill, as Claude Code records a slash command.
_SLASH = re.compile(r"<command-name>\s*/?(?:ai-config:)?pause\s*</command-name>", re.I)
MAX_NOTE = 80


def is_pause_command(prompt: str) -> bool:
    """True for a prompt that pauses the session."""
    if _SLASH.search(prompt):
        return True
    match = _BARE.match(prompt)
    return bool(match) and len(match.group("rest").strip()) <= MAX_NOTE


def _prompt_text(entry: dict) -> str | None:
    """The text of a prompt the user typed, or None for any other entry."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return None
    if entry.get("isCompactSummary") or "toolUseResult" in entry:
        return None
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return None
    text = "\n".join(
        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
    )
    return text or None


def latest_prompt(transcript_path: str) -> str | None:
    """The most recent prompt the user typed in this transcript."""
    latest = None
    with open(transcript_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                text = _prompt_text(entry)
                if text is not None:
                    latest = text
    return latest


def is_paused(payload: dict | None) -> bool:
    """True while the user's most recent prompt in this session is a pause command."""
    path = (payload or {}).get("transcript_path") or (payload or {}).get("transcriptPath")
    if not isinstance(path, str) or not path.strip():
        return False
    try:
        prompt = latest_prompt(path.strip())
    except OSError:
        return False  # no transcript to read: hooks behave as unpaused
    return prompt is not None and is_pause_command(prompt)
