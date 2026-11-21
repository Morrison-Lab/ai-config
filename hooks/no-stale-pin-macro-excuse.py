#!/usr/bin/env python3
"""PreToolUse deny: a post or commit excuses skipping a macro because a repo's pin lacks it.

Ezra, 2026-11-20 23:22 PST: never skip a semantic macro (\\ccprod, \\stprod,
\\soprod, \\oprod and the rest) because a repo's pinned `latex-macros` copy
lacks it; bump the pin in the same PR and use the macro. "Inconvenience is
never a valid excuse."

DENIES a user-visible post, a forge comment, issue or PR body, a `gh issue|pr`
--body/--title in Bash, or a `git commit -m` message with a sentence that names
a macro, names the pin (pin, pinned, submodule, latex-macros, the macros copy),
says it lacks something (lacks, missing, predates, does not have/define/include,
is not in, not yet in) and says the macro was left out (kept, left, skipped,
stays, raw, instead, fallback, until). A sentence that bumps the pin (bump,
bumped, advance) or states the rule (never, don't, do not) passes.
Reuses strings(), bash_text() and TOOL from hooks/no-notes-blob-link.py.
ALLOW_STALE_PIN_MACRO=1 overrides for a sentence quoting someone else.
Fails open on parse trouble or a missing helper.
"""
import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path

OVERRIDE = "ALLOW_STALE_PIN_MACRO"
SENTENCE = re.compile(r"[^.!?\n]+[.!?]*")
MACRO = re.compile(r"\bmacros?\b|\\[A-Za-z]{2,}")
PIN = re.compile(r"\bpin(?:s|ned)?\b|\bsubmodule\b|\blatex-macros\b|\bmacros\s+copy\b", re.I)
LACKS = re.compile(
    r"\black(?:s|ing|ed)?\b|\bmissing\b|\bpredates?\b|\bolder\b"
    r"|\b(?:does\s+not|doesn'?t|did\s+not|didn'?t)\s+(?:have|define|include|contain|ship)\b"
    r"|\b(?:is|was)\s+not\s+(?:yet\s+)?in\b|\b(?:isn'?t|wasn'?t)\s+(?:yet\s+)?in\b|\bnot\s+yet\s+in\b",
    re.I)
SKIPPED = re.compile(
    r"\b(?:kept|keep(?:s|ing)?|left|leav(?:e|es|ing)|skip(?:s|ped|ping)?|stay(?:s|ed)?"
    r"|raw|instead|fallback|fall\s+back|until|for\s+now)\b", re.I)
EXEMPT = re.compile(r"\bbump(?:s|ed|ing)?\b|\badvanc(?:e|es|ed|ing)\b|\bnever\b|\bdon'?t\b|\bdo\s+not\b",
                    re.I)
GIT_COMMIT = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?commit\b")

REASON = (
    "[hook: no-stale-pin-macro-excuse] \"{sentence}\" keeps a raw expression because a repo's "
    "pinned macros copy lacks the macro. Ezra, 2026-11-20: never skip a semantic macro for that "
    "reason; \"inconvenience is never a valid excuse.\" Bump the repo's latex-macros pin in the "
    "same PR (or stack on the Morrison-Lab/macros PR that adds the macro) and use the macro. "
    "See skills/use-math-macros/SKILL.md."
)


def load_blob_link():
    path = Path(__file__).resolve().parent / "no-notes-blob-link.py"
    spec = importlib.util.spec_from_file_location("_nspme_blob_link", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def commit_messages(command):
    if not GIT_COMMIT.search(command):
        return ""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ""
    out = [t for prev, t in zip([""] + tokens, tokens) if prev in ("-m", "--message")]
    out += [t.split("=", 1)[1] for t in tokens if t.startswith("--message=")]
    return "\n".join(out)


def excuse(text):
    for sentence in SENTENCE.findall(text):
        if EXEMPT.search(sentence):
            continue
        if MACRO.search(sentence) and PIN.search(sentence) and LACKS.search(sentence) \
                and SKIPPED.search(sentence):
            return sentence.strip()
    return None


def denial(payload):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    blob = load_blob_link()
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        text = blob.bash_text(command) + "\n" + commit_messages(command)
    elif blob.TOOL.search(tool):
        text = "\n".join(blob.strings(tool_input))
    else:
        return None
    hit = excuse(text)
    return REASON.format(sentence=hit[:200]) if hit else None


def main():
    try:
        payload = json.load(sys.stdin)
        reason = denial(payload)
    except Exception:
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
