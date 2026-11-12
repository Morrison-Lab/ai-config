#!/usr/bin/env python3
"""PreToolUse: never say a repository isn't in this thread; attach it.

Ezra, 2026-11-12: "cai: never say a repo isn't in a thread; add it" (see
no-cant-from-session-excuses.md). Denies a hearthbot sentence that places a
repository out of this thread, session or "here": the thread's repo list, or
a repo word, owner/name or lab repo name as subject of "isn't in" and the
like or object of "doesn't have" or "can't push to". A path or code span
alone does not count. A report that I or we attached the one repository
named passes, as does a reported add_repo or attach refusal or failure.
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
MODAL = rf"(?:can{APOS}t|cannot|can\s+not|couldn{APOS}t|unable\s+to|not\s+able\s+to)"
SUBJ_NEG = re.compile(
    rf"\b{NEG}\s+(?:(?:yet|currently|actually|even|already|really)\s+)?"
    r"(?:(?:in|within)(?=\s+(?:this|the|my|our|that|current|any)\b)|part\s+of|attached|among|one\s+of|"
    r"available|accessible|reachable|checked\s+out|cloned|added)\b|\b(?:outside|unavailable|missing\s+from)\b", re.I)
PLACE = rf"(?:this|the|my|our|that|current)\s+(?:project\s+)?(?:thread|session)"
LOC = re.compile(rf"\b{PLACE}\b|\bmy\s+(?:repos|repositories)\b|\bhere\b", re.I)
REPO_LIST = re.compile(
    rf"\b{PLACE}{APOS}s\s+(?:github\s+)?(?:repos|repositories|repo\s+scope|repo\s+list)\b"
    r"(?![\w'\u2019])(?!\s+(?:checkout|clone|directory|folder|tree|root|branch|files?|of)\b)"
    r"|\bmy\s+(?:repos|repositories)\b(?!['\u2019])"
    r"|\bthe\s+(?:repos|repositories)\s+(?:attached|available|in|on|for)\b",
    re.I)
LIST_NEG = re.compile(
    rf"(?:\b{NEG}\s+(?:\w+\s+){{0,2}}?(?:in|on|one\s+of|part\s+of|among|within|available|attached|added|see)"
    rf"|\b(?:outside|missing\s+from))\s+(?:\S+\s+){{0,4}}?(?:{REPO_LIST.pattern})"
    rf"|(?:{REPO_LIST.pattern})\s+(?:{NEG})\s+(?:include|includes|have|has|list)\b", re.I)
LAB_REPOS = (r"ai-config|gha|lds|mlg|mlr|mds|mcs|pds|sds|rme|psw|psc|qwt|qnp|"
             r"ids|dds|vds|ccds|cds|epi\d+|lds-site|mcsg|stats-allowlist|teaching-tools")
NAMED = re.compile(rf"\b[\w-]{{1,39}}/[\w-]{{1,100}}\b(?![/.]\w)|\b(?:{LAB_REPOS})\b", re.I)
REPO_NAME = re.compile(rf"\b(?:repo|repos|repository|repositories)\b|{NAMED.pattern}", re.I)
SUBJECT = re.compile(rf"(?:{REPO_NAME.pattern})[\s`'\"\u2019]*(?:(?:is|are|was|were)\s+)?$", re.I)
# The object must end its phrase: "I don't have the lds preview URL" passes.
DET = r"(?:(?:the|a|an|that|this|any)\s+)?"
TOK = r"`?([\w-]{1,39}(?:/[\w-]{1,100})?)`?"
END = r"(?=\s*(?:[.,;:!?)]|$|(?:in|on|from|here|to|into|within|checked|cloned|attached|repo|repository)\b))"
ACCESS = r"(?:(?:write|push|read)\s+)?access\s+to\s+"
OBJECT = re.compile(
    rf"\b{NEG}\s+(?:\w+\s+){{0,2}}?(?:have|has|include|includes|see)\s+(?:{ACCESS})?{DET}{TOK}{END}"
    # Action verbs need a can't: "I did not push to lds in this session" passes.
    rf"|\b{MODAL}\s+(?:\w+\s+)?(?:reach|access|push|edit|write|commit|clone|modify|open\s+a\s+PR\s+(?:on|in|against))"
    rf"\s+(?:to\s+|into\s+)?{DET}{TOK}{END}"
    rf"|(?:\b(?:has|have)\s+no|\bthere(?:{APOS}s|\s+is|\s+are)\s+no)\s+"
    rf"(?:{ACCESS}{DET}{TOK}|(?:checkout|clone|copy)\s+of\s+{DET}{TOK}"
    rf"|{DET}{TOK}\s+(?:checkout|clone|copy|access|repo|repository)\b)"
    rf"|\black\w*\s+{ACCESS}{DET}{TOK}",
    re.I)
ATTACHED = re.compile(
    rf"\b(?:I|we)\s+(?:have\s+|{APOS}ve\s+|just\s+|then\s+)?(?:added|attached|cloned)\s+(?:(?:the|a|an)\s+)?`?([\w/-]+)", re.I)
FAIL = r"(?:refused|denied|declined|failed|rejected|errored|returned\s+(?:an?\s+)?(?:error|[45]\d\d))"
TRIED = re.compile(
    r"\b(?:add_repo|attach|attaching)\b(?:\s+(?!has\b|had\b|would\b|will\b|may\b|might\b|could\b)\S+){0,2}?"
    rf"\s+(?:was\s+|itself\s+)?{FAIL}\b", re.I)

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
    parts = [tool_input.get(k) for k in ("text", "question", "reason")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def names_repo(sentence: str) -> bool:
    if LIST_NEG.search(sentence):
        return True
    for m in SUBJ_NEG.finditer(sentence):
        window = sentence[max(0, m.start() - 200):m.start()]
        subj = SUBJECT.search(window)
        # "The fix for lds isn't in" names lds as an object, not the subject.
        if subj and not re.search(r"\b(?:for|to|on|in|of|with|from|about|by)\s+$", window[:subj.start()], re.I):
            return True
    obj = OBJECT.search(sentence)
    if not obj:
        return False
    return any(g and REPO_NAME.search(g) for g in obj.groups())


def is_excuse(sentence: str) -> bool:
    if not LOC.search(sentence):
        return False
    att = ATTACHED.search(sentence)
    named = {m.group(0).lower() for m in NAMED.finditer(sentence)}
    obj = att and att.group(1).lower()
    if obj == "it" and len(named) == 1:
        obj = next(iter(named))
    if obj and REPO_NAME.search(obj) and named <= {obj}:
        return False
    if TRIED.search(sentence):
        return False
    return names_repo(sentence)


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
