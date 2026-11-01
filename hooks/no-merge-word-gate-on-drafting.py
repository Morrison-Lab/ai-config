#!/usr/bin/env python3
"""Stop-hook guard: a merge word gates merging, never drafting or opening a PR.

THE SLIP THIS FILLS (ai-config#4866)
------------------------------------
After merging one lab PR, an agent ended its turn with queued work and said
the next PRs "need a fresh mwc". Only the merge needs Ezra's word. Drafting,
pushing and opening a PR need none, so the sentence blamed a gate that does not
exist and left the work unstarted.

`no-announced-start-without-starting.py` misses it: the sentence has a
conditional cue ("need ... mwc"), which that guard treats as a real blocker.

WHAT IS MATCHED
---------------
A closing sentence that names the merge word (mwc, merge word) AND says work
needs, waits on or is pending it, AND names work that is not the merge itself
(next, later, remaining or further PRs, drafting, opening, continuing).

WHAT IS NOT MATCHED
-------------------
- A sentence about merging: "I'll merge them after mwc", "the merge needs mwc".
- A negation: "drafting needs no merge word".
- Code spans and fences.

Blocks once per distinct message.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

MWC_RX = re.compile(r"\b(?:mwc|merge[- ]word)\b", re.I)
GATE_RX = re.compile(
    r"\b(?:needs?|requires?|waiting (?:for|on)|waits? (?:for|on)|awaits?|"
    r"awaiting|until|after|once|pending|gated (?:on|by))\b",
    re.I,
)
WORK_RX = re.compile(
    r"\b(?:(?:next|later|remaining|further|following|other|stacked|more) "
    r"(?:\w+ ){0,2}(?:PRs?|pull requests?|batch(?:es)?|sections?|exercises?|labs?)|"
    r"draft(?:ing|s)?|open(?:ing)? (?:\w+ ){0,2}(?:PRs?|pull requests?)|"
    r"continu(?:e|ing)|push(?:ing)?|writ(?:e|ing))\b",
    re.I,
)
# The merge itself is the legitimate thing to gate on the word.
MERGE_RX = re.compile(r"\bmerg(?:e|es|ed|ing)\b(?![- ]word)", re.I)
NEGATION_RX = re.compile(r"\b(?:no|never|without|neither|nor)\b|n't|\b(?:do|does|need) not\b", re.I)

CLAUSE_SPLIT_RX = re.compile(r"[,:]\s+|\s+but\s+", re.I)
SENTENCE_SPLIT_RX =re.compile(r"(?<=[.!?;])\s+|\n")
TAIL_SENTENCES = 4
STOPPING_POINT_RX = re.compile(r"\*\*Stopping Point\*\*.*\Z", re.S | re.I)

try:
    _lib = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
    )
    if _lib not in sys.path:
        sys.path.insert(0, _lib)
    from fences import strip_code
except Exception:
    _FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
    _CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)[^\n\r]*?(?<!`)\1(?!`)")

    def strip_code(text: str) -> str:
        """Strip fenced code blocks and inline code spans."""
        return _CODE_SPAN_RE.sub(" ", _FENCE_RE.sub(" ", text))


def last_assistant_text(path):
    """The final user-visible assistant prose in the transcript."""
    last_text = ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("type") == "assistant" or m.get("role") == "assistant":
                    blocks = (m.get("message") or {}).get("content") or m.get("content") or []
                    if isinstance(blocks, list):
                        txt = "".join(
                            b.get("text", "")
                            for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        if txt.strip():
                            last_text = txt
                    elif isinstance(blocks, str) and blocks.strip():
                        last_text = blocks
                elif m.get("source") == "MODEL" and m.get("type") == "PLANNER_RESPONSE":
                    content = m.get("content")
                    if isinstance(content, str) and content.strip():
                        last_text = content
    except Exception:
        return ""
    return last_text


def tail_of(prose):
    """Closing sentences, both above and inside a Stopping Point block."""
    trimmed = STOPPING_POINT_RX.sub(" ", prose)
    out = []
    for text in (trimmed, prose):
        sents = [s for s in SENTENCE_SPLIT_RX.split(text) if s.strip()]
        out.extend(sents[-TAIL_SENTENCES:])
    return out


def offending_sentence(prose):
    """The last sentence that gates non-merge work on a merge word, or None."""
    for sentence in reversed(tail_of(prose)):
        for clause in reversed(CLAUSE_SPLIT_RX.split(sentence)):
            if not MWC_RX.search(clause) or not GATE_RX.search(clause):
                continue
            if not WORK_RX.search(clause) or NEGATION_RX.search(clause):
                continue
            # A clause about the merge itself may gate on the word, but a
            # merge named in an earlier clause ("After merging this one, the
            # next PRs need mwc") does not excuse a later clause.
            if MERGE_RX.search(clause):
                continue
            return sentence.strip()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    text = last_assistant_text(payload.get("transcript_path") or "")
    if not text:
        return 0
    sentence = offending_sentence(strip_code(text))
    if not sentence:
        return 0
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-mwc-gate-drafting-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w", encoding="utf-8").close()
    except Exception:
        pass
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "Your reply says work waits on a merge word, and the work "
                    "is not the merge:\n\n"
                    f"In: {sentence}\n\n"
                    "A merge word (mwc) gates merging only. Drafting, "
                    "pushing and opening a PR need none, and a stacked PR can "
                    "be opened before its base merges. Do the work now and "
                    "ask for the word only at the merge, in one line "
                    "(ai-config#4866)."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
