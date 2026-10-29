#!/usr/bin/env python3
"""Stop-hook guard: a reply says a reference book could not be reached, and the
session never searched both places the books live.

THE MEASURED CASE (2026-10-29, Morrison-Lab/lds#1548 thread)
-------------------------------------------------------------
A reply to the user said ESL, Murphy, Bishop and the patsy docs "could not be
reached, so those are unchecked". The session had searched the web only. The
project library (`/mnt/project-files/books/`) held ESL, Murphy (2012), Bishop,
ISLP, ISLR and Smola-Vishwanathan as PDFs, and `Morrison-Lab/mlr` held those
plus Murphy (2022), Geron and Deisenroth. One `pdftotext | grep` over the
library answered the question the reply said it could not. The user had to ask
"did you check mlr?", which was the second time: the same rule was already
standing (Ezra, 2026-10-23: look in the project library AND the mlr repo before
saying a book is unavailable; books missing from either get added to both).

WHAT IT CHECKS
--------------
    the final reply says a book is unreachable / unavailable / unchecked
    AND the transcript shows no tool call that touched the project library
        (`project-files/books`) OR no tool call that touched `mlr`

Both places are required, because the rule names both and a book can be in one
and not the other. The message names which search is missing.

WHY IT WARNS INSTEAD OF DECIDING
--------------------------------
A book may genuinely be in neither place; the rule then says to add it to both
and report that. Whether the book is there is not lexically decidable, so the
hook interrupts the stop once per turn (agent_notice.stop_notice) and leaves
the call to the author. Fails OPEN.

See `shared/workflow/track-useful-resources.md` for the book-library rule.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

_AGENT_NOTICE_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
)
if _AGENT_NOTICE_LIB not in sys.path:
    sys.path.insert(0, _AGENT_NOTICE_LIB)
from agent_notice import stop_notice  # noqa: E402 -- reaches the agent (ai-config#4796)

# A reply sentence about a book that could not be had.
BOOK = (
    r"(?:books?|textbooks?|\bESL\b|\bISL[RP]?\b|\bISLR2?\b|Murphy|Bishop|Hastie|"
    r"Casella|Dobson|Kutner|Smola|Goodfellow|Elements of Statistical Learning|"
    r"Pattern Recognition)"
)
UNREACHED = (
    r"(?:could ?n[o']t|can ?n[o']t|can't|unable to|did ?n[o']t|didn't|failed to|no way to)"
    r"\s+(?:\w+\s+){0,2}?(?:reach|access|find|open|read|get|check|locate|obtain|retrieve|fetch|verify)"
    r"|\bunchecked\b|\bnot checked\b|\bunavailable\b|\bnot available\b|\bnot accessible\b|\bno access\b"
)
SENTENCE_RX = re.compile(
    rf"(?=[^.\n]*{BOOK})(?=[^.\n]*(?:{UNREACHED}))[^.\n]+", re.I
)

LIBRARY_RX = re.compile(r"project-files/books|project-files/?\s|/mnt/project-files", re.I)
MLR_RX = re.compile(r"Morrison-Lab/mlr\b|\"repo\"\s*:\s*\"mlr\"|/mlr\b|\bmlr/books", re.I)

# A line quoting the rule is not a claim that a book is unavailable.
QUOTED_RX = re.compile(r"`[^`]*`")

REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message)$", re.I)


def _blocks(msg):
    blocks = (msg.get("message") or {}).get("content") or msg.get("content") or []
    return blocks if isinstance(blocks, list) else []


def _reply_payload(block):
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return ""
    if not REPLY_TOOL_RX.search(block.get("name") or ""):
        return ""
    inp = block.get("input")
    txt = inp.get("text") if isinstance(inp, dict) else None
    return txt if isinstance(txt, str) else ""


def read_transcript(path):
    """Return (last visible reply text, concatenated tool-call inputs)."""
    last_text = last_reply = ""
    saw_reply_tool = False
    calls = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if not (m.get("type") == "assistant" or m.get("role") == "assistant"):
                    continue
                blocks = _blocks(m)
                txt = "".join(
                    b.get("text", "") for b in blocks
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                if txt.strip():
                    last_text = txt
                for b in blocks:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    if REPLY_TOOL_RX.search(b.get("name") or ""):
                        saw_reply_tool = True
                        payload = _reply_payload(b)
                        if payload.strip():
                            last_reply = payload
                    else:
                        calls.append(json.dumps(b.get("input") or {}))
    except Exception:
        return "", ""
    return (last_reply if saw_reply_tool else last_text), "\n".join(calls)


def find_claim(text):
    """The first sentence saying a book is unreachable, ignoring `quoted` spans."""
    for m in SENTENCE_RX.finditer(QUOTED_RX.sub("", text)):
        return m.group(0).strip()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    text, calls = read_transcript(payload.get("transcript_path") or "")
    claim = find_claim(text) if text else None
    if not claim:
        return 0
    missing = []
    if not LIBRARY_RX.search(calls):
        missing.append("the project library (/mnt/project-files/books/)")
    if not MLR_RX.search(calls):
        missing.append("the Morrison-Lab/mlr repo (its books/ directory)")
    if not missing:
        return 0
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-bookunavail-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w", encoding="utf-8").close()
    except Exception:
        pass
    print(stop_notice(
        payload,
        f"Your reply says a book is unavailable (\"{claim[:120]}\"), but this session "
        f"never searched {' or '.join(missing)}. Search both (pdftotext + grep for the "
        "library; the mlr books/ listing), then revise the reply. A book missing from "
        "either place gets added to both.",
        "flag-book-unavailable-without-library-search",
    ))
    sys.stderr.write(
        "[hook: flag-book-unavailable-without-library-search] "
        f"\"{claim[:120]}\"\nNot yet searched: {', '.join(missing)}.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
