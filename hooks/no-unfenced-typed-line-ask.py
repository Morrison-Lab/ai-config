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
    in a sentence that asks the user to type, say, reply, paste or enter it,
    or alone on its own line in a message that asks; or
  * a sentence asks the user to type, and the line it gives sits in inline
    backticks or double quotes,

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

FENCE = re.compile(r"^[ \t]*(```|~~~)[^\n]*\n(.*?)^[ \t]*\1[ \t]*$", re.S | re.M)

# Asking the user to type, paste or send a line.
ASK = re.compile(
    r"\b(?:type|typing|paste|reply\s+with|respond\s+with|answer\s+with|send\s+(?:me\s+)?(?:the\s+)?(?:line|word)|"
    r"(?:say|write)\s+(?:the\s+line|this\s+line|exactly))\b"
    # "Say ...", "Reply ...", "Enter ..." only as an imperative, so "the docs say" is not an ask.
    r"|(?:^|[:;]\s*|\b(?:please|just|then)\s+)(?:say|reply|enter)\b",
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
INLINE = re.compile(r"`([^`\n]+)`|\"([^\"\n]{2,})\"|“([^”\n]{2,})”")
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
    return plain and any(n.startswith(f + " ") and KNOWN_LINE.fullmatch(f) for f in fenced)


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
        for m in INLINE.finditer(s):
            line = next(g for g in m.groups() if g)
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
