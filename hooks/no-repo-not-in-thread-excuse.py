#!/usr/bin/env python3
"""PreToolUse: never say a repository isn't in this thread; attach it.

Ezra, 2026-11-12: "cai: never say a repo isn't in a thread; add it". Rule, scope and exemptions:
shared/workflow/no-cant-from-session-excuses.md and this hook's hooks.json "why". A deny because the
shape is lexical (ai-config#4741). `ALLOW_REPO_NOT_IN_THREAD=1` overrides. Fails open on parse trouble.
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
       rf"hasn{APOS}t|haven{APOS}t|has\s+not|have\s+not|can{APOS}t|cannot|can\s+not|couldn{APOS}t|no\s+longer|not)")
MODAL = rf"(?:can{APOS}t|cannot|can\s+not|couldn{APOS}t|unable\s+to|not\s+able\s+to)"
PLACE = rf"(?:the\s+current|this|the|my|our|that|current)\s+(?:project\s+)?(?:thread|session)"
# The place is the thread itself or its repo list: "lds is not in this thread's queue" passes.
TARGET = (rf"\s+(?:{PLACE}(?:{APOS}s\s+(?:github\s+)?(?:repos|repositories|repo\s+scope|repo\s+list|list\s+of\s+repos|scope(?!\s+of\b)))?"
          rf"(?![\w'\u2019])|my\s+(?:repos|repositories)\b|the\s+(?:repos|repositories)\s+(?:attached|available|in|for)\b)")
SUBJ_NEG = re.compile(
    rf"(?:\b{NEG}\s+(?:(?:yet|currently|actually|even|already|really|been)\s+){{0,2}}(?:in|on|within|part\s+of|among|one\s+of|"
    rf"(?:attached|added|checked\s+out|cloned|available|accessible|reachable)(?:\s+(?:to|in|into|from|on|for))?)"
    rf"|\b(?:outside|unavailable\s+(?:in|from|to)|missing\s+from)){TARGET}", re.I)
LOC = re.compile(rf"\b{PLACE}\b|\bmy\s+(?:repos|repositories)\b", re.I)
REPO_LIST = re.compile(
    rf"\b{PLACE}{APOS}s\s+(?:github\s+)?(?:repos|repositories|repo\s+scope|repo\s+list)\b"
    r"(?![\w'\u2019])(?!\s+(?:checkout|clone|directory|folder|tree|root|branch|files?|of)\b)"
    r"|\bmy\s+(?:repos|repositories)\b(?!['\u2019])|\bthe\s+(?:repos|repositories)\s+(?:attached|available|in|on|for)\b", re.I)
LAB_REPOS = (r"ai-config|gha|lds|mlg|mlr|mds|mcs|pds|sds|rme|psw|psc|qwt|qnp|"
             r"ids|dds|vds|ccds|cds|epi\d+|lds-site|mcsg|stats-allowlist|teaching-tools")
NAMED = re.compile(rf"\b[\w-]{{1,39}}/[\w-]{{1,100}}\b(?![/.]\w)|\b(?:{LAB_REPOS})\b", re.I)
REPO_NAME = re.compile(rf"\b(?:repo|repos|repository|repositories)\b|{NAMED.pattern}", re.I)
SUBJECT = re.compile(rf"(?:{REPO_NAME.pattern})[\s`'\"\u2019]*(?:(?:is|are|was|were)\s+)?$", re.I)
DET = r"(?:(?:the|a|an|that|this|any)\s+)?"
TOK = r"`?([\w-]{1,39}(?:/[\w-]{1,100})?)`?"
# The object ends its phrase or a thread place: "I didn't see lds in this thread's PR list" passes.
END = (r"(?=(?:\s+(?:repo|repository|checkout|clone|copy|access|checked\s+out|cloned|attached))?"
       rf"(?:\s*[.,;:!?)](?=\s|$)|\s*$|\s+here\b|\s+(?:in|on|from|to|into|within){TARGET}))")
ACCESS = r"(?:read\s+)?access\s+to\s+"
OBJECT = re.compile(
    rf"\b{NEG}\s+(?:\w+\s+){{0,2}}?(?:have|has|include|includes|see)\s+(?:{ACCESS})?{DET}{TOK}{END}"
    rf"|\b{MODAL}\s+(?:\w+\s+)?(?:reach|access|clone|see)\s+(?:to\s+|into\s+)?{DET}{TOK}{END}"
    rf"|(?:\b(?:has|have)\s+no|\bthere(?:{APOS}s|\s+is|\s+are)\s+no)\s+"
    rf"(?:{ACCESS}{DET}{TOK}|(?:checkout|clone|copy)\s+of\s+{DET}{TOK}"
    rf"|{DET}{TOK}(?=\s+(?:checkout|clone|copy|access|repo|repository)\b)){END}"
    rf"|\black\w*\s+{ACCESS}{DET}{TOK}{END}", re.I)
LIST_NEG = re.compile(
    rf"\b{NEG}\s+(?:\w+\s+){{0,2}}?(?:see|find)\s+{DET}{TOK}\s+(?:in|among|on)\s+(?:{REPO_LIST.pattern})"
    rf"|(?:{REPO_LIST.pattern})\s+(?:{NEG})\s+(?:include|includes|have|has|list)\s+{DET}{TOK}", re.I)
# "I attached it", "I added it" and "ran add_repo" report the fix; "the attached patch", a request, a negation does not.
ATTACH_VERB = re.compile(
    rf"(?<!the\s)(?<!\ba\s)(?<!an\s)(?<!repos\s)(?<!repositories\s)\battach(?:ed|ing)\b"
    rf"(?=\s+(?:both\s+|the\s+)?(?:it|them|repo|repository|{NAMED.pattern})(?!\s+(?:is|was|would|will|should|needs?|requires?)\b)|\s*(?:[.,;]|$)|\s+now\b)"
    rf"|\badded\s+[\w/-]{{1,140}}\s+to\s+{PLACE}|\badded\s+(?:it|them)\b(?!\s+(?:to|in)\s+(?!{PLACE}))"
    r"|\b(?:ran|called|used|invoked|tried)\s+(?:the\s+)?add_repo\b|\badd_repo\s+(?:attached|added|cloned)\b", re.I)
NOT_YET = re.compile(rf"\b(?:{NEG}|never|nobody|nothing|no\s+one|once|when|until|unless|of|without|will|would|could|should|must|needs?|if|to|please|can|{APOS}ll)\s+(?:\w+\s+){{0,2}}$", re.I)
FAIL = r"(?:refused|denied|declined|failed|rejected|errored|returned\s+(?:an?\s+)?(?:error|[45]\d\d))"
TRIED = re.compile(
    r"\b(?:add_repo|attach|attaching)\b(?:\s+(?!has\b|had\b|would\b|will\b|may\b|might\b|could\b)\S+){0,2}?"
    rf"\s+(?:was\s+|itself\s+)?{FAIL}\b|\b(?:attach|add_repo)\b[^.;]{{0,80}}?\b(?:got|received)\s+[\"'\u2018\u201c]"
    rf"|\b(?:tried|attempted)\s+(?:to\s+)?(?:attach|run\s+add_repo|add_repo)\b[^.;]{{0,80}}?\bbut\s+(?:it\s+|that\s+)?(?:was\s+)?{FAIL}", re.I)

REASON = (
    '[hook: no-repo-not-in-thread-excuse] "{sentence}" says a repository is not in this '
    "thread or session. Ezra, 2026-11-12: \"never say a repo isn't in a thread; add it\". Call "
    'mcp__claude-code-remote__add_repo (ToolSearch "select:mcp__claude-code-remote__add_repo"), clone it, '
    "do the work, and report it in the past tense. If add_repo itself refuses, say so in the same sentence "
    "and quote its reason. shared/workflow/no-cant-from-session-excuses.md. "
    "Set ALLOW_REPO_NOT_IN_THREAD=1 only when the user asked for this wording."
)


def message_text(tool_input: dict) -> str:
    parts = [tool_input.get(k) for k in ("text", "question", "reason")]
    for opt in tool_input.get("options") or []:
        if isinstance(opt, dict):
            parts += [opt.get("label"), opt.get("consequence")]
    return "\n".join(p for p in parts if isinstance(p, str))


def names_repo(sentence: str) -> bool:
    for m in SUBJ_NEG.finditer(sentence):
        window = sentence[max(0, m.start() - 200):m.start()]
        subj = SUBJECT.search(window)
        # "The fix for lds isn't in" and "Updating lds is not in" name lds as an object, not the subject.
        if subj and not re.search(r"\b(?:for|to|on|in|of|with|from|about|by|\w+ing)\s+(?:[\w-]+\s+){0,2}$", window[:subj.start()], re.I):
            return True
    for rx in (OBJECT, LIST_NEG):
        obj = rx.search(sentence)
        if obj and any(g and REPO_NAME.search(g) for g in obj.groups()):
            return True
    return False


def plain(sentence: str) -> str:
    """Read [text](url), **bold** and `code` as their text."""
    sentence = re.sub(r"\[([^\]\[]{0,300})\]\([^)\s]{0,500}\)", r"\1", sentence)
    return re.sub(r"https?://[^\s)]*|\*\*|`", "", sentence)


def attaches(sentence: str) -> bool:
    return bool(TRIED.search(sentence) or any(
        not NOT_YET.search(sentence[max(0, m.start() - 40):m.start()]) for m in ATTACH_VERB.finditer(sentence)))


def is_excuse(sentence: str) -> bool:
    return bool(LOC.search(sentence)) and not attaches(sentence) and names_repo(sentence)


def excuse(text: str):
    """The first sentence that calls a repo out of this thread's reach, or None."""
    sentences = [plain(x) for x in re.split(r"(?<=[.!?])\s+|\n+", text)]
    for i, sentence in enumerate(sentences):
        # "X wasn't in this thread's repos. I attached it." reports the fix in the next sentence.
        if is_excuse(sentence) and not (i + 1 < len(sentences) and attaches(sentences[i + 1])):
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
