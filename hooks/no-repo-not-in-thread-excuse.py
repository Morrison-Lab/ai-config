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

A sentence is denied when it holds all three of:
  * a negated presence or access ("isn't in", "not one of", "doesn't have",
    "can't reach", "don't include", "outside");
  * a thread or session as the place ("this thread", "the session's repos",
    "my repos", "attached here");
  * a repository: a list of the thread's repos ("this thread's repos"), or a
    repo word or repo-like name (a hyphenated name, owner/name, a code span or a
    lab repo name) before the negation or as the object of have, include,
    access or reach.
A sentence that reports an attach (added, attached, cloned) passes, and so does
one that says add_repo or the attach was refused, denied, declined or failed.

A deny, not a reminder, because the failing shape is lexical (ai-config#4741).
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
NEG = (rf"(?:isn{APOS}t|is\s+not|aren{APOS}t|are\s+not|wasn{APOS}t|was\s+not|"
       rf"don{APOS}t|doesn{APOS}t|didn{APOS}t|do\s+not|does\s+not|did\s+not|"
       rf"can{APOS}t|cannot|can\s+not|couldn{APOS}t|no\s+longer|not)")
PRESENCE = (r"(?:in|part\s+of|attached|among|one\s+of|within|available|include|"
            r"includes|have|has|access|reach|checked\s+out|cloned|on)")
NEG_PRESENCE = re.compile(rf"\b{NEG}\s+(?:\w+\s+){{0,3}}?{PRESENCE}\b|\boutside\b", re.I)
PLACE = rf"(?:this|the|my|our|that|current)\s+(?:thread|session)"
LOC = re.compile(
    rf"\b{PLACE}\b|\bmy\s+(?:repos|repositories)\b"
    r"|\b(?:attached|checked\s+out|cloned|available)\s+here\b",
    re.I)
REPO_LIST = re.compile(
    rf"\b{PLACE}{APOS}s\s+(?:github\s+)?(?:repo|repos|repository|repositories)"
    r"(?:\s+scope)?\b(?!\s+(?:checkout|clone|directory|tree|root|branch|files?)\b)"
    r"|\bmy\s+(?:repos|repositories)\b"
    r"|\bthe\s+(?:repos|repositories)\s+(?:attached|available|in|on|for)\b",
    re.I)
LAB_REPOS = (r"ai-config|gha|macros|lds|mlg|mlr|mds|mcs|pds|sds|rme|psw|psc|qwt|qnp|"
             r"ids|dds|vds|ccds|cds|epi\d+|lds-site|mcsg|stats-allowlist|teaching-tools")
REPO_NAME = re.compile(
    rf"\b(?:repo|repos|repository|repositories)\b|`[^`]+`|\b[\w.-]+/[\w.-]+\b"
    rf"|\b[a-z0-9]+(?:-[a-z0-9]+)+\b|\b(?:{LAB_REPOS})\b",
    re.I)
OBJECT = re.compile(
    rf"\b{NEG}\s+(?:\w+\s+){{0,2}}?(?:have|has|include|includes|access|reach)\s+"
    r"(?:access\s+to\s+)?(?:the\s+)?(\S+)",
    re.I)
ATTACHED = re.compile(
    rf"\b(?:I|we)\s+(?:have\s+|{APOS}ve\s+|just\s+|then\s+)?(?:added|attached|cloned)\b", re.I)
FAIL = r"(?:refus\w*|denied|declin\w*|fail\w*|reject\w*)"
TRIED = re.compile(
    rf"\b(?:add_repo|attach\w*)\b[^.!?]*\b{FAIL}\b|\b{FAIL}\b[^.!?]*\b(?:add_repo|attach\w*)\b",
    re.I)

REASON = (
    '[hook: no-repo-not-in-thread-excuse] "{sentence}" says a repository is not in this '
    "thread or session. Ezra, 2026-11-12: \"never say a repo isn't in a thread; add it\". "
    "Call mcp__claude-code-remote__add_repo (load it with ToolSearch "
    '"select:mcp__claude-code-remote__add_repo"), clone it, do the work, and report it in '
    "the past tense. If add_repo itself refuses, say so in the same sentence and quote "
    "its reason. shared/workflow/no-cant-from-session-excuses.md. "
    "Set ALLOW_REPO_NOT_IN_THREAD=1 only when the user asked for this wording."
)


def message_text(tool_input: dict) -> str:
    parts = [tool_input.get("text"), tool_input.get("question")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def names_repo(sentence: str, neg: re.Match) -> bool:
    if REPO_LIST.search(sentence):
        return True
    if REPO_NAME.search(sentence[:neg.start()]):
        return True
    obj = OBJECT.search(sentence)
    return bool(obj and REPO_NAME.search(obj.group(1)))


def is_excuse(sentence: str) -> bool:
    neg = NEG_PRESENCE.search(sentence)
    if not neg or not LOC.search(sentence):
        return False
    if ATTACHED.search(sentence) or TRIED.search(sentence):
        return False
    return names_repo(sentence, neg)


def excuse(text: str):
    """The first sentence that calls a repo out of this thread's reach, or None."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if is_excuse(sentence):
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
