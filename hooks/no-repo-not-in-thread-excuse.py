#!/usr/bin/env python3
"""PreToolUse: never say a repository isn't in this thread; attach it.

Ezra, 2026-11-12 02:27 UTC (mds optimization thread): "cai: never say a repo
isn't in a thread; add it". The thread had told the coordinator "ai-config
isn't in this thread's repos, so could you route that as an issue?" when
`mcp__claude-code-remote__add_repo` would have attached it in one call. This
repeats the 2026-11-04 excuse ("not in this session's repo scope") that
shared/workflow/no-cant-from-session-excuses.md already forbids in prose.

Scope: every message a session sends to a person or another session
(hearthbot post_message, reply, update_message, edit_message,
request_decision, message_coordinator, message_thread), in every session.
Denies a sentence that says a repository is not in, not part of, not attached
to, not one of, or outside this thread's or session's repos or scope. A deny,
not a reminder, because the failing shape is lexical (ai-config#4741).

A sentence that also says the attach was refused, denied, declined or failed
passes: that reports a tried route, which the excuses fragment allows.
`ALLOW_REPO_NOT_IN_THREAD=1` overrides. Fails open on any parse trouble.
"""
import json
import os
import re
import sys

OVERRIDE = "ALLOW_REPO_NOT_IN_THREAD"
TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|"
    r"request_decision|message_coordinator|message_thread)$")

APOS = r"(?:'|’)"
NEG = rf"(?:isn{APOS}t|is\s+not|aren{APOS}t|are\s+not|wasn{APOS}t|was\s+not|not)"
WHERE = (rf"(?:this|the|my|that|our)\s+(?:thread|session){APOS}?s?"
         r"(?:\s+(?:github\s+)?(?:repo|repos|repository|repositories|scope|repo\s+scope))?")
EXCUSE = re.compile(
    rf"\b{NEG}\s+(?:\w+\s+){{0,2}}?(?:in|part\s+of|attached\s+to|among|one\s+of|within|available\s+in)\s+{WHERE}"
    rf"|\boutside\s+(?:of\s+)?{WHERE}",
    re.I)
REPO_WORD = re.compile(r"\b(?:repo|repos|repository|repositories|scope)\b", re.I)
TRIED = re.compile(r"\b(?:refused|denied|declined|failed|rejected)\b|\badd_repo\b.*\b(?:error|fail)", re.I)

REASON = (
    '[hook: no-repo-not-in-thread-excuse] "{sentence}" says a repository is not in this '
    "thread or session. Ezra, 2026-11-12: \"never say a repo isn't in a thread; add it\". "
    "Call mcp__claude-code-remote__add_repo (load it with ToolSearch "
    '"select:mcp__claude-code-remote__add_repo"), clone it, do the work, and report it in '
    "the past tense. If add_repo itself refuses, quote its reason in the same sentence. "
    "shared/workflow/no-cant-from-session-excuses.md. "
    "Set ALLOW_REPO_NOT_IN_THREAD=1 only when the user asked for this wording."
)


def message_text(tool_input: dict) -> str:
    parts = [tool_input.get("text"), tool_input.get("question")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def excuse(text: str):
    """The first sentence that calls a repo out of this thread's reach, or None."""
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", text):
        if (EXCUSE.search(sentence) and REPO_WORD.search(sentence)
                and not TRIED.search(sentence)):
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
    sentence = excuse(message_text(tool_input))
    return REASON.format(sentence=sentence[:160]) if sentence else None


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
