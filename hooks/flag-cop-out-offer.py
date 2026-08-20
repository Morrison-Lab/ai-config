#!/usr/bin/env python3
"""Stop-hook guard: flag a reply that ENDS by offering to do work.

A cop-out offer converts work you have already been authorized to do back into
a request for permission -- "say the word and I'll push", "want me to kick off
the re-run?". It reads as courtesy and delivers nothing: the work does not
happen, the user spends a turn, and the offer leaves no artifact behind.

See `shared/workflow/no-cop-out-offers.md` for the rule and the case record.

Per `shared/principles/deterministic-tools.md`, a rule is consulted at read
time and broken at composition time, so the prose alone does not reach the
moment it breaks. This is the instrument.

WARNS, never blocks. Whether the underlying action was already authorized is
NOT lexically decidable -- asking before a merge or a force-push is correct,
and those sentences look identical. So the hook can only surface the phrase
and make the author answer the authorization question; deciding it for them
would refuse legitimate caution.

TAIL-ANCHORED, not whole-message and not substring. Two reasons:

  * This corpus quotes these phrases constantly -- this docstring does -- so a
    substring matcher would fire on every reply discussing the rule.
  * The failure mode is specifically a recap that CLOSES on an offer. An offer
    mid-message, followed by more substance, is usually a real question posed
    in passing.

Fires once per distinct message (sentinel keyed by content hash).
Fails OPEN.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Matched against the LAST few lines of the reply only.
OFFERS = [
    r"say the word",
    r"(just )?let me know (if|when|whether|either)",
    r"(do you |would you )?want me to\b",
    r"would you like me to\b",
    r"shall i\b",
    r"should i (go ahead|proceed)",
    r"i can .{0,60}\bif you('d| would) (like|prefer)",
    r"happy to .{0,40}\bif you\b",
    r"i'?d be glad to\b",
    r"unless you'?d rather",
    r"if that works for you",
    r"(ready|standing by) to .{0,40}\bwhen you('re| are)\b",
    r"once you confirm",
]
RX = re.compile("|".join(OFFERS), re.I)

# How much of the tail to inspect. An offer is the closing move, so a short
# window is the point: it keeps a mid-message aside from firing.
TAIL_CHARS = 400


def last_assistant_text(path):
    last = ""
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("type") != "assistant":
                    continue
                blocks = (m.get("message") or {}).get("content") or []
                txt = "".join(
                    b.get("text", "") for b in blocks
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                if txt.strip():
                    last = txt
    except Exception:
        return ""
    return last


def find_offer(text):
    """Return the matched offer phrase when the reply CLOSES on one."""
    tail = text.strip()[-TAIL_CHARS:]
    m = RX.search(tail)
    return m.group(0) if m else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    text = last_assistant_text(payload.get("transcript_path") or "")
    if not text:
        return 0
    phrase = find_offer(text)
    if not phrase:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-copout-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    sys.stderr.write(
        f"[hook: flag-cop-out-offer] Your reply closes on an offer: "
        f"\"{phrase}\".\n\n"
        "Ask one question: was that action ALREADY AUTHORIZED? A standing "
        "instruction (pr-on-claim opens the PR, issue-first files the issue), "
        "a daytb/away grant, or the user having asked for the outcome earlier "
        "all count.\n\n"
        "If yes, this is avoidance wearing courtesy. Do the work and report "
        "it in the past tense. An unwanted action is cheap to revert; an "
        "unanswered offer leaves no branch, no PR, no issue -- nothing "
        "another session could find.\n\n"
        "If no -- the action is destructive, irreversible, or outward-facing "
        "and genuinely unauthorized -- then asking is correct. Drop the offer "
        "wording and ask plainly.\n\n"
        "See shared/workflow/no-cop-out-offers.md.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
