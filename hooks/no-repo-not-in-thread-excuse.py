#!/usr/bin/env python3
"""PreToolUse: never say a repository isn't in this thread; attach it.

Ezra, 2026-11-12: "cai: never say a repo isn't in a thread; add it". An mds
thread told the coordinator "ai-config isn't in this thread's repos" when
add_repo would have attached it (see no-cant-from-session-excuses.md).

Scope: hearthbot messages to a person or session, in every session. Denies a
sentence with a negated presence or access ("isn't in", "doesn't have",
"can't reach", "outside", "has no X checkout"), a thread or session as the
place, and a repository: the thread's repo list, or a repo word, owner/name
or lab repo name as the subject just before the negation or as its object.
A path (scripts/x.py) or code span (`pytest`) alone does not count. A report
that I or we attached the one repository named passes, as does one saying
add_repo or the attach was refused, failed or returned an error.

A deny because the shape is lexical (ai-config#4741).
`ALLOW_REPO_NOT_IN_THREAD=1` overrides. Fails open on any parse trouble.
"""
import json
import os
import re
import sys

OVERRIDE = "ALLOW_REPO_NOT_IN_THREAD"
TOOL = re.compile(
    r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message|request_decision|message_coordinator|message_thread)$")

APOS = r"(?:'|\u2019)"
NEG = (rf"(?:isn{APOS}t|is\s+not|aren{APOS}t|are\s+not|wasn{APOS}t|was\s+not|"
       rf"don{APOS}t|doesn{APOS}t|didn{APOS}t|do\s+not|does\s+not|did\s+not|"
       rf"can{APOS}t|cannot|can\s+not|couldn{APOS}t|no\s+longer|not)")
PRESENCE = (r"(?:in|part\s+of|attached|among|one\s+of|within|available|include|"
            r"includes|have|has|access|accessible|reach|reachable|checked\s+out|cloned|added|push|edit|"
            r"write|commit|see|on)")
NEG_PRESENCE = re.compile(
    rf"\b{NEG}\s+(?:\w+\s+){{0,3}}?{PRESENCE}\b|\b(?:outside|unavailable|lacks?)\b"
    rf"|\b(?:has|have)\s+no\b|\bthere(?:{APOS}s|\s+is|\s+are)\s+no\b",
    re.I)
PLACE = rf"(?:this|the|my|our|that|current)\s+(?:thread|session)"
LOC = re.compile(rf"\b{PLACE}\b|\bmy\s+(?:repos|repositories)\b"
                 r"|\b(?:attached|checked\s+out|cloned|available)\s+here\b", re.I)
REPO_LIST = re.compile(
    rf"\b{PLACE}{APOS}s\s+(?:github\s+)?(?:repos|repositories|repo\s+scope)\b"
    r"(?![\w'\u2019])(?!\s+(?:checkout|clone|directory|folder|tree|root|branch|files?|of)\b)"
    r"|\bmy\s+(?:repos|repositories)\b(?!['\u2019])"
    r"|\bthe\s+(?:repos|repositories)\s+(?:attached|available|in|on|for)\b",
    re.I)
LAB_REPOS = (r"ai-config|gha|macros|lds|mlg|mlr|mds|mcs|pds|sds|rme|psw|psc|qwt|qnp|"
             r"ids|dds|vds|ccds|cds|epi\d+|lds-site|mcsg|stats-allowlist|teaching-tools")
REPO_NAME = re.compile(
    rf"\b(?:repo|repos|repository|repositories)\b|\b[\w-]{{1,39}}/[\w-]{{1,100}}\b(?![/.]\w)"
    rf"|\b(?:{LAB_REPOS})\b", re.I)
SUBJECT = re.compile(rf"(?:{REPO_NAME.pattern})[\s`'\"\u2019]*(?:(?:is|are|was|were)\s+)?$", re.I)
NAMED = re.compile(rf"\b[\w-]{{1,39}}/[\w-]{{1,100}}\b(?![/.]\w)|\b(?:{LAB_REPOS})\b", re.I)
OBJECT = re.compile(
    rf"\b{NEG}\s+(?:\w+\s+){{0,2}}?"
    r"(?:have|has|include|includes|access|reach|push|edit|write|commit)\s+"
    r"(?:access\s+to\s+|to\s+|into\s+)?(?:(?:the|a|an|that|this)\s+)?(\S+)"
    # "has no X" needs a checkout or access word: "we have no gha changes" passes.
    rf"|(?:\b(?:has|have)\s+no|\bthere(?:{APOS}s|\s+is|\s+are)\s+no)\s+"
    r"(?:access\s+to\s+(?:the\s+)?(\S+)|(?:checkout|clone|copy)\s+of\s+(?:the\s+)?(\S+)"
    r"|(?:the\s+)?(\S+)\s+(?:checkout|clone|copy|access|repo|repository)\b)"
    r"|\black\w*\s+access\s+to\s+(?:the\s+)?(\S+)",
    re.I)
ATTACHED = re.compile(
    rf"\b(?:I|we)\s+(?:have\s+|{APOS}ve\s+|just\s+|then\s+)?(?:added|attached|cloned)\s+(?:(?:the|a|an)\s+)?(\S+)", re.I)
FAIL = r"(?:refused|denied|declined|failed|rejected|returned|errored)"
TRIED = re.compile(
    rf"\b(?:add_repo|attach|attaching)\b[^.!?]*\b{FAIL}\b|\b{FAIL}\b[^.!?]*\b(?:add_repo|attach|attaching)\b",
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
    if SUBJECT.search(sentence[max(0, neg.start() - 200):neg.start()]):
        return True
    obj = OBJECT.search(sentence)
    if not obj:
        return False
    return any(g and REPO_NAME.search(g) for g in obj.groups())


def is_excuse(sentence: str) -> bool:
    neg = NEG_PRESENCE.search(sentence)
    if not neg or not LOC.search(sentence):
        return False
    att = ATTACHED.search(sentence)
    named = {m.group(0).lower() for m in NAMED.finditer(sentence)}
    if att and REPO_NAME.search(att.group(1)) and named <= {att.group(1).lower()}:
        return False
    if TRIED.search(sentence):
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
