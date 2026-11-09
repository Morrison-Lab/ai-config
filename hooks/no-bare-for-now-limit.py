#!/usr/bin/env python3
"""PreToolUse: a limit reported "for now" must say for how long.

ai-config#5160. Ezra, 2026-11-09: "used up for now" -- when you say things like
this, tell me for how long. A user-visible message that reports a quota, rate
limit, budget or tool as used up, exhausted, paused, blocked or unavailable
"for now" must also carry a reset time or a duration.

Scope: the user-visible hearthbot tools (post_message, request_decision, reply,
update_message, edit_message), in every session. Denies a sentence that pairs a
limit word with "for now" and holds no time, duration or reset in that same
sentence. A deny is possible because the failing shape is lexical; a reminder
would be read past (ai-config#4741). The denial text also carries the companion
rule (coordinator, 2026-11-09): never estimate a rate-limit reset time, read it from
`gh api rate_limit` and quote it in PST. Whether a quoted time was read or guessed
is not decidable from text, so that half is carried by the denial text, not a deny.
`ALLOW_BARE_FOR_NOW=1` overrides. Fails
open on any parse trouble.
"""
import json
import os
import re
import sys

OVERRIDE = "ALLOW_BARE_FOR_NOW"
TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|request_decision)$")

LIMIT = re.compile(
    r"\b(?:used\s+up|exhausted|out\s+of|paused|blocked|unavailable|down|capped|"
    r"rate[- ]limited|over\s+(?:the\s+)?(?:limit|quota)|quota|limit)\b", re.I)
FOR_NOW = re.compile(r"\bfor\s+now\b", re.I)
HAS_TIME = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*(?:s|sec|secs|seconds?|m|min|mins|minutes?|h|hr|hrs|hours?|"
    r"d|days?|weeks?)\b"
    r"|\b\d{1,2}:\d{2}\b|\b\d{4}-\d{2}-\d{2}\b|\b(?:utc|pst|pdt|pacific)\b|\bresets?\b|\buntil\b|\btill\b"
    r"|\b(?:an?|one|two|three|few|several)\s+(?:hours?|minutes?|days?|weeks?)\b)",
    re.I)

REASON = (
    '[hook: no-bare-for-now-limit] "{sentence}" reports a limit or outage "for now" with '
    "no duration (ai-config#5160, Ezra 2026-11-09). Say for how long: a reset time in PST "
    'or a duration ("until 16:00 PST", "for about 2 hours"). Never estimate a '
    "GitHub rate-limit reset: read the reset field of `gh api rate_limit` and convert it to "
    "PST. If it is unknown, say that it is unknown and when you will recheck. "
    "Set ALLOW_BARE_FOR_NOW=1 only when the user asked for the bare form."
)


def user_text(tool_input: dict) -> str:
    parts = [tool_input.get("text"), tool_input.get("question")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def bare_for_now(text: str):
    """The first sentence with a limit word and 'for now' but no time, or None."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if (FOR_NOW.search(sentence) and LIMIT.search(sentence)
                and not HAS_TIME.search(sentence)):
            return " ".join(sentence.split())
    return None


def denial(payload: dict):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    if not TOOL.search(str(payload.get("tool_name") or "")):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    sentence = bare_for_now(user_text(tool_input))
    return REASON.format(sentence=sentence[:120]) if sentence else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    reason = denial(payload)
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
