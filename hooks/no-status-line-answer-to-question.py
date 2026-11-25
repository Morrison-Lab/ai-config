#!/usr/bin/env python3
"""PreToolUse deny: the first reply to a user's question opens with the answer.

Ezra, 2026-11-25 00:46 PST, in a Claude app project thread: "cai: always answer
my questions directly and immediately" (ai-config#6129). He had asked "why
haven't you merged 2196?". The thread's first reply was "Running the clean
check on gha#2196 now, then merging it under gha's standing grant." It never
said why. The answer ("I never looked at it; another thread opened it") needed
no tool call. The rule is shared/workflow/answer-questions-directly.md.

DENIES an `mcp__hearthbot__post_message` when all of these hold:
- the user's latest message asks a question: a sentence ends with "?", or a
  line starts with why, what, did, have, has, is, are, can, how (and a few
  more question words);
- no post_message reply has gone out since that message, so this is the first
  reply to it;
- the reply's first sentence is only a status or plan line: it starts with a
  gerund ("Running", "Checking", "Looking"), or with "I'll", "I will",
  "I'm going to" or "Let me", and holds no answer word (because, yes, no,
  not, never, hadn't, didn't, already and the like).

Two exemptions keep it from firing on true narration:
- A polite request worded as a question ("can you push that?", "could you
  rerun it?", anything with "please") is an instruction, not a question, and
  "Pushing now." is a fine first reply to it.
- Only the first reply after the question is judged. Once one reply has gone
  out, later progress posts are status by design.

A deny is the right form here: the remedy is one clause ("I hadn't looked at
it; checking now."), and a warning arrives after the person already read the
status line. ALLOW_STATUS_FIRST_REPLY=1 overrides, for a gerund that really is
the answer ("Running out of quota stopped it."). Text the user quoted, fenced
or put in a code span does not count, and neither do the reply's own quotes
(remind-encode-user-correction.py's typed_text strips them). Fails open on
parse trouble or a missing helper.
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
_LIB = os.path.join(os.path.dirname(HERE), "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

OVERRIDE = "ALLOW_STATUS_FIRST_REPLY"
POST = "mcp__hearthbot__post_message"

HUMAN_MSG = re.compile(r'<message\b[^>]*\bfrom="human"[^>]*>(.*?)</message>', re.S | re.I)
WAKE = re.compile(r"<(?:wake|message)\b", re.I)
Q_END = re.compile(r"\?(?=\s|$)")
Q_START = re.compile(
    r"^\s*(?:why|what|did|didn't|have|haven't|has|hasn't|is|isn't|are|aren't|can|can't|how"
    r"|when|where|who|which|do|does|doesn't|don't|was|wasn't|were|weren't)\b",
    re.I | re.M)
REQUEST = re.compile(r"^\s*(?:can|could|would|will)\s+you\b|\bplease\b", re.I)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")

# Words that read as an answer: a reason, a yes or no, a negation, a state.
ANSWER = re.compile(
    r"\b(?:because|since|yes|no|not|never|nothing|none|already|hadn'?t|haven'?t|hasn'?t|didn'?t"
    r"|wasn'?t|weren'?t|isn'?t|aren'?t|don'?t|doesn'?t|can'?t|couldn'?t|won'?t|wouldn'?t"
    r"|blocked|failed|due)\b",
    re.I)
LEAD = re.compile(r"^[\W_]*(?:(?:ok(?:ay)?|sure|on it|got it)\b[\s,.!:-]*)?", re.I)
STATUS = re.compile(
    r"^(?:I'?ll|I\s+will|I'?m\s+going\s+to|I\s+am\s+going\s+to|let\s+me|going\s+to"
    r"|(?:now\s+)?(?P<ger>[A-Za-z]+ing))\b",
    re.I)
NOT_GERUNDS = {
    "nothing", "something", "everything", "anything", "thing", "during", "morning",
    "evening", "string", "spring", "king", "ring", "bring", "sing", "wing", "ceiling",
    "pending", "according", "notwithstanding", "missing",
}


def _load(name):
    from sibling import load_sibling
    return load_sibling(__file__, name, required=True)


def human_words(raw, typed_text):
    """What the human typed: the human message bodies of a wake, or the plain prompt."""
    bodies = HUMAN_MSG.findall(raw)
    if bodies:
        raw = "\n".join(html.unescape(b) for b in bodies)
    elif WAKE.search(raw):
        return ""  # a wake with no human message (CI, a coordinator note)
    return typed_text(raw)


def asks_question(text):
    """True when the text asks something that is not a polite request."""
    candidates = [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    asked = [s for s in candidates if Q_END.search(s) or Q_START.match(s)]
    return any(not REQUEST.search(s) for s in asked)


def status_first_sentence(text):
    """The reply's first sentence when it is only a status or plan line, else None."""
    first = next((s for s in SENTENCE_END.split(text.strip()) if s.strip()), "")
    if not first or ANSWER.search(first):
        return None
    body = LEAD.sub("", first).lstrip("*_ ")
    m = STATUS.match(body)
    if not m:
        return None
    ger = m.group("ger")
    if ger and ger.lower() in NOT_GERUNDS:
        return None
    return first.strip()


def post_text(block):
    if not isinstance(block, dict) or block.get("type") != "tool_use" or block.get("name") != POST:
        return None
    return str((block.get("input") or {}).get("text") or "")


def owed(path, human_text, typed_text):
    """True when the latest human message asks a question and no post has replied yet."""
    pending = False
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except Exception:
                continue
            if not isinstance(m, dict) or m.get("isSidechain"):
                continue
            role = m.get("type") or m.get("role")
            if role == "user":
                raw = human_text(m)
                if raw is not None and raw.strip():
                    words = human_words(raw, typed_text)
                    if words.strip():
                        pending = asks_question(words)
            elif role == "assistant" and pending:
                blocks = (m.get("message") or {}).get("content") or []
                for b in blocks if isinstance(blocks, list) else []:
                    if post_text(b) is not None:
                        pending = False
    return pending


def denial(payload):
    if os.environ.get(OVERRIDE) or not isinstance(payload, dict):
        return None
    if payload.get("tool_name") != POST:
        return None
    text = str((payload.get("tool_input") or {}).get("text") or "")
    path = payload.get("transcript_path") or ""
    if not text.strip() or not path or not os.path.isfile(path):
        return None
    corr = _load("remind-encode-user-correction.py")
    first = status_first_sentence(corr.typed_text(text))
    if not first:
        return None
    mech = _load("no-user-correction-without-mechanism.py")
    if not owed(path, mech.human_text, corr.typed_text):
        return None
    return (
        "[hook: no-status-line-answer-to-question] The user's latest message asks a question, "
        f'and this first reply opens with a status line instead of the answer: "{first[:160]}". '
        'Ezra, 2026-11-25: "always answer my questions directly and immediately". Put the answer '
        "in the first sentence. When it needs a lookup, first say what you already know "
        "(\"I hadn't looked at it; another thread opened it.\"), then the step. "
        "See shared/workflow/answer-questions-directly.md. "
        f"{OVERRIDE}=1 overrides when the gerund really is the answer."
    )


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
