#!/usr/bin/env python3
"""UserPromptSubmit: the user's plain-English merge word is an mwc grant.

ai-config#4698. Ezra, 2026-10-23: a typed "merge when ready" was not
recognized as a merge word, so he had to retype "mwc". `skills/mwc/SKILL.md`
listed `/mwc`, the bare word `mwc`, "merge when confident", "merge at will"
and "maw", and a model reading that list does not generalize it. This hook
makes the recognition mechanical: when the user's message is a merge
instruction in plain English, it injects the instruction to treat it as a bare
`mwc` (`mwc all`) and run `enable-mwc`, with the same gates `mwc` has.

It only ADDS context and never grants anything itself: the merge guards
(no-unauthorized-merge.py, enforce-mwc-review-gate.py) still decide. Text the
user did not type (code, quotes, system reminders, pasted content) is ignored,
and a question ("should I merge?") is not a grant.

Fails OPEN and SILENT on any parse trouble.
"""
import json
import re
import sys

# A whole short message that is only a merge instruction.
WHOLE = re.compile(
    r"^\W*(?:/?mwc|/?maw|merge(?:\s+(?:it|them\s+all|all))?"
    r"|go\s+ahead\s+(?:and\s+)?merge(?:\s+(?:it|them|them\s+all))?"
    r"|(?:please\s+)?merge\s+(?:when|once|as\s+soon\s+as)\s+(?:ready|clean|green|confident|they(?:'re| are) ready)"
    r"|merge\s+when\s+ready|mwc\s+(?:them\s+)?all|mwc\s+them)\W*$",
    re.I,
)
# A merge instruction inside a longer message.
INLINE = re.compile(
    r"\b(?:merge\s+when\s+(?:ready|clean|green)|merge\s+them\s+all|mwc\s+(?:them\s+)?all)\b",
    re.I,
)
QUESTION = re.compile(r"\?\s*$")
QUESTION_SENTENCE = re.compile(r"[^.!?\n]*\?")

NOT_TYPED = [
    re.compile(r"^ {0,3}(```|~~~).*?^ {0,3}\1[^\n]*$", re.MULTILINE | re.DOTALL),
    re.compile(r"<(system-reminder|pasted_content)\b[^>]*>.*?</\1>", re.DOTALL),
    re.compile(r"^\s*>.*$", re.MULTILINE),
    re.compile(r'`[^`\n]*`|"[^"\n]*"'),
]

REMINDER = (
    "[hook: remind-plain-english-merge-word] The user's message (\"{quote}\") is a merge word "
    "in plain English. Treat it as a bare `mwc` (`mwc all`): run `ai-session.sh enable-mwc` "
    "and `check-mwc` per skills/mwc/SKILL.md, then merge every in-scope PR that is fully "
    "clean. Do not ask them to retype `mwc` or to name PR numbers. The gates still run on each "
    "PR (fully-clean, current head, stale base); a PR that fails them waits, and you say which. "
    "If the words were not a merge instruction (a question, quoted text), ignore this."
)


def typed(text: str) -> str:
    text = text.replace(chr(0x2019), "'")
    for pattern in NOT_TYPED:
        text = pattern.sub(" ", text)
    return text.strip()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str):
        return 0
    text = typed(prompt)
    if not text or QUESTION.search(text):
        return 0
    match = WHOLE.match(text) or INLINE.search(text)
    if not match:
        return 0
    # An inline match inside a sentence that ends in a question mark is not an instruction.
    if QUESTION_SENTENCE.match(text, match.end()):
        return 0
    print(REMINDER.format(quote=" ".join(match.group(0).split())[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
