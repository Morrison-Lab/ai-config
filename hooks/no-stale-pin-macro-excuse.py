#!/usr/bin/env python3
"""PreToolUse deny: a post or commit excuses skipping a macro because a repo's pin lacks it.

Ezra, 2026-11-20 23:22 PST: never skip a semantic macro (\\ccprod, \\stprod,
\\soprod, \\oprod and the rest) because a repo's pinned `latex-macros` copy
lacks it; bump the pin in the same PR and use the macro. "Inconvenience is
never a valid excuse."

A backstop for the common wordings, not a proof: the rule lives in
skills/use-math-macros/SKILL.md and the adversarial reviewer.

DENIES a user-visible post, a forge comment, issue or PR body, a `gh issue|pr`
--body/--title/--body-file, or a `git commit` -m/-am/-F message where one
sentence, or two adjacent ones, name a macro, name the pin (pin, pinned,
submodule, latex-macros, the macros copy, vendored macros), say it lacks
something (lacks, missing, predates, stale, out of date, does not have/define,
is not in/available/defined) and say the macro was kept out (kept, used, wrote,
left, skipped, stays, raw, until, for now, spelled out; "kept the macro" does
not count). A window that moves the pin (bumped, advanced, synced, updated the
submodule, stacked) with no negation or deferral (not, n't, never, will, 'll,
later) passes, as does a quote of the rule ("no excuse", "never skip").
A heredoc `-F -` message is not read.
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
PIN = re.compile(r"\bpin(?:s|ned)?\b|\bsubmodule\b|\blatex-macros\b|\bmacros\s+copy\b"
                 r"|\bvendored\s+macros\b", re.I)
LACKS = re.compile(
    r"\black(?:s|ing|ed)?\b|\bmissing\b|\bpredates?\b|\bolder\b|\bout\s+of\s+date\b|\bstale\b"
    r"|\b(?:does\s+not|doesn'?t|did\s+not|didn'?t)\s+(?:yet\s+)?(?:have|define|include|contain|ship)\b"
    r"|\b(?:is|was)\s+not\s+(?:yet\s+)?(?:in|available|defined)\b"
    r"|\b(?:isn'?t|wasn'?t)\s+(?:yet\s+)?(?:in|available|defined)\b|\bnot\s+yet\s+in\b"
    r"|\b(?:didn'?t|did\s+not|won'?t|will\s+not|not)\s+bump",
    re.I)
# A keep/use verb aimed at the macro itself ("kept the macro") is the right behaviour, not a skip.
SKIPPED = re.compile(
    r"\b(?:kept|keep(?:s|ing)?|used?|using|wrote|left|leav(?:e|es|ing)|skip(?:s|ped|ping)?"
    r"|stay(?:s|ed)?)\b(?!\s+the\s+macros?\b)"
    r"|\b(?:raw|fallback|fall\s+back|until|for\s+now|spelled\s+out|written\s+out)\b", re.I)
# An affirmative pin move (no negation or deferral in the window), or a quote of the rule.
MOVED = re.compile(
    r"\bbump(?:s|ed|ing)?\b|\badvanc(?:es|ed|ing)\b|\bsync(?:s|ed|ing)?\b|\bmoved\s+(?:it|the\s+pin)\s+forward\b"
    r"|\bupdat(?:es|ed|ing)\s+the\s+(?:pin|submodule)\b|\bstack(?:s|ed|ing)?\b", re.I)
DEFERRED = re.compile(r"n't\b|\bnot\b|\bnever\b|\bwon'?t\b|\bwill\b|'ll\b|\blater\b|\bno\b", re.I)
RULE_QUOTE = re.compile(
    r"\b(?:no|not\s+an?|never\s+an?)\s+(?:valid\s+)?(?:excuse|reason)\b"
    r"|\b(?:never|don'?t|do\s+not)\s+skip\b", re.I)
GIT_COMMIT = re.compile(r"\bgit\s+(?:-[cC]\s+\S+\s+)*commit\b")
FILE_FLAGS = ("-F", "--file", "--body-file")

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


def read_small(path):
    """A message file's text (a commit -F or gh --body-file), or "" for stdin or trouble."""
    if path in ("", "-") or not os.path.isfile(path) or os.path.getsize(path) > 200_000:
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def is_message_flag(token):
    """-m, --message, or a short-flag cluster ending in m (-am)."""
    return token in ("-m", "--message") or (len(token) > 2 and token[0] == "-"
                                             and token[1] != "-" and token.endswith("m"))


def commit_messages(command, cwd):
    if not GIT_COMMIT.search(command) and "--body-file" not in command:
        return ""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ""
    out = []
    for prev, t in zip([""] + tokens, tokens):
        if is_message_flag(prev):
            out.append(t)
        elif prev in FILE_FLAGS:
            out.append(read_small(os.path.join(cwd, t)))
        elif t.startswith(("--message=", "--file=", "--body-file=")):
            value = t.split("=", 1)[1]
            out.append(value if t.startswith("--message=") else read_small(os.path.join(cwd, value)))
    return "\n".join(out)


def excuse(text):
    """The first one- or two-sentence window that excuses a skipped macro by the pin."""
    sentences = [s.strip() for s in SENTENCE.findall(text) if s.strip()]
    for i in range(len(sentences)):
        for window in (sentences[i], " ".join(sentences[i:i + 2])):
            if RULE_QUOTE.search(window) or (MOVED.search(window) and not DEFERRED.search(window)):
                continue
            if MACRO.search(window) and PIN.search(window) and LACKS.search(window) \
                    and SKIPPED.search(window):
                return window
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
        cwd = str(payload.get("cwd") or os.getcwd())
        text = blob.bash_text(command) + "\n" + commit_messages(command, cwd)
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
