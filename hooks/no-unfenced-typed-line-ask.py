#!/usr/bin/env python3
"""PreToolUse: a line the user must type goes in a fenced code block.

ai-config#5667. Ezra, 2026-11-15 01:38Z, in a project thread that had asked
him to type an approval line: "always give me the line with a copy button".
The Claude app shows a copy button on a fenced code block, not on inline code
or quoted text.

Denies a user-visible reply tool call (mcp__hearthbot__reply, post_message,
update_message, edit_message) when, outside fenced code blocks,

  * a known typed line (`mwc <repo> ...`, `approve push of ...`,
    `approve editing ...`, `retry <repo>#<n>`, `merge anyway <pr>`) appears
    in a sentence that asks the user to type, say, reply, paste or enter it
    (the verb as an imperative or request, so "the return type of" is not one),
    or alone on its own line in a message that asks; or
  * a sentence asks the user to type, and the verb's own object ("type `X`",
    "reply with `X`", "type this line: `X`") sits in inline backticks or
    double quotes,

and that same line is not also given in a fenced code block in the message.
A negated ask ("no need to type anything") is left alone. Plain single-word
merge words in prose ("a bare `mwc`") are left alone unless a sentence asks
the user to type them. ALLOW_UNFENCED_TYPED_LINE=1 overrides. Fails open on
parse trouble. shared/workflow/lab-operating-rules.md.
"""
import json
import os
import re
import sys

REPLY_TOOL = re.compile(r"^mcp__hearthbot__(?:reply|post_message|update_message|edit_message)$")

FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n(.*?)^[ \t]*\1[ \t]*$", re.S | re.M)

# Asking the user to type a line: the verb only as an imperative or request,
# so "the return type of" or "the docs say" is not an ask.
VERB = r"(?:type|paste|enter|say|reply|respond|send)"
ASK = re.compile(
    r"(?:^|[:;,]\s*|\b(?:please|just|then|to|can\s+you|you\s+(?:can|should|need\s+to|must))\s+)"
    + VERB + r"\b",
    re.I)
# An inline line counts only as the verb's own object: "type `X`",
# "reply with `X`", "type this line: `X`". "paste the log from `debug.log`" does not.
OBJECT = re.compile(
    r"\b" + VERB + r"\s+(?:with\s+|exactly\s+|(?:this|the\s+following|the)(?:\s+line|\s+command)?\s*:?\s*)?"
    r"(?:`(?P<a>[^`\n]+)`|\"(?P<b>[^\"\n]{2,})\"|\u201c(?P<c>[^\u201d\n]{2,})\u201d)",
    re.I)
NEGATED = re.compile(
    r"\b(?:don'?t|do\s+not|no\s+need\s+to|needn'?t|never|without|not\s+need\s+to|nothing\s+to)\b"
    r"[^.!?\n]{0,30}\b(?:type|typing|paste|reply|send)\b",
    re.I)

# Lines that only have a use when the user types them verbatim.
KNOWN_LINE = re.compile(
    r"\b(?:mwc\s+(?:[\w.-]+\s+)?#?\d+(?:\s+[0-9a-f]{7,40})?"
    r"|approve\s+push\s+of\s+[^\n`\"]+"
    r"|approve\s+editing\s+[^\n`\"]+"
    r"|retry\s+[\w.-]+#\d+"
    r"|merge\s+anyway\s+#?[\w.-]*\d+)",
    re.I)
# A bare merge word or retry is a typed line only inside an asking sentence,
# and never covers a longer fenced line.
BARE_LINE = re.compile(r"\b" + VERB + r"\s+[`\"]?(?P<w>mwc|retry\s+#\d+)\b", re.I)
# A sentence reporting a line already typed is not an ask for it.
REPORTED = re.compile(r"\b(?:typed|said|sent|gave|wrote|answered|replied)\b", re.I)
SENT = re.compile(r"(?<=[.!?])\s+|\n+")

REASON = (
    "[hook: no-unfenced-typed-line-ask] This message asks the user to type a line that is not "
    "in a fenced code block: {line!r}. Ezra, 2026-11-15: \"always give me the line with a copy "
    "button\". The app shows a copy button only on a fenced code block, so put each line he must "
    "type on its own, alone in a ``` block, and keep the sentence around it plain. "
    "shared/workflow/lab-operating-rules.md; ai-config#5667. ALLOW_UNFENCED_TYPED_LINE=1 overrides."
)


def norm(s):
    return " ".join(s.split()).strip(" .,:;").lower()


def split_fences(text):
    fenced = [norm(line) for m in FENCE.finditer(text) for line in m.group(2).splitlines() if line.strip()]
    return FENCE.sub("\n", text), fenced


def covered(line, fenced, plain=False):
    n = norm(line)
    if n in fenced:
        return True
    # A plain-text match runs to the end of its line, so a whole fenced typed
    # line that starts it ("approve push of X" in "approve push of X in this
    # thread") covers it. A fragment such as a fenced "mwc" covers nothing.
    return plain and any(n.startswith(f) and KNOWN_LINE.fullmatch(f) and WORD_END.match(n[len(f):])
                         for f in fenced)


# What may follow a covering fenced line in a plain-text match: end, space or
# punctuation, but not more of a path or name ("approve push of x," is covered
# by a fenced "approve push of x"; "mwc lds 25" does not cover "mwc lds 2508").
WORD_END = re.compile(r"$|[^\w./#-]")


def offending_line(text):
    prose, fenced = split_fences(text)
    sentences = [s for s in SENT.split(prose) if s.strip()]
    asking = [s for s in sentences if ASK.search(s) and not NEGATED.search(s)]
    if not asking:
        return None
    # A known typed line counts when its own sentence asks for it, or when it
    # stands alone on a line ("Type this:" then the line), not when a status
    # sentence elsewhere in the message mentions it.
    alone = [s for s in sentences if KNOWN_LINE.fullmatch(norm(s)) and not REPORTED.search(s)]
    for s in asking + alone:
        for m in KNOWN_LINE.finditer(s):
            if not covered(m.group(0), fenced, plain=True):
                return m.group(0).strip()
    for s in asking:
        for m in BARE_LINE.finditer(s):
            # A fenced full line that starts with the bare word covers it.
            word = norm(m.group("w"))
            if not any(f == word or f.startswith(word + " ") for f in fenced):
                return m.group("w").strip()
    for s in asking:
        for m in OBJECT.finditer(s):
            line = m.group("a") or m.group("b") or m.group("c")
            if not covered(line, fenced):
                return line.strip()
    return None


def main() -> int:
    if os.environ.get("ALLOW_UNFENCED_TYPED_LINE") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if not REPLY_TOOL.search(str(payload.get("tool_name") or "")):
        return 0
    tool_input = payload.get("tool_input")
    text = tool_input.get("text") if isinstance(tool_input, dict) else None
    if not isinstance(text, str):
        return 0
    line = offending_line(text)
    if line:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(line=line)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
