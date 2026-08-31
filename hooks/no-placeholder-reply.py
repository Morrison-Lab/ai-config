#!/usr/bin/env python3
"""Stop-hook guard: catch a reply that is nothing but a placeholder.

`CLAUDE.md`'s "Always produce a reply --- never end a turn silently" bans the
exact string `No response requested.` in a Do/Don't pair, with a case record
naming ai-config#1568. The rule was loaded and the lapse happened anyway,
three times in one session on 2026-08-17 -- each time on resuming after a
context-window summary, which is a fourth trigger that section does not name:
the summary reads like a report, so the work it describes feels already
reported.

Per `shared/principles/deterministic-tools.md`, the third occurrence is a
tool. The condition is lexically decidable over one artifact, so it should not
cost model reasoning at all.

WHOLE-MESSAGE anchoring, not substring. This corpus discusses the banned
string constantly -- this docstring does -- so a substring matcher would block
every reply that quotes the rule it enforces.

The line the patterns draw is between a claim about the REQUEST and a claim
about the WORK:

  blocked  "No response requested."   -- says nothing about what happened
  allowed  "Nothing to report."       -- says the work produced no change,
                                         which `CLAUDE.md` explicitly REQUIRES
                                         of a no-change background tick

Fires once per distinct message (sentinel keyed by content hash) so a block
cannot loop. Fails OPEN: a guard that wedges the session costs more than the
lapse it prevents.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Each pattern is matched against the WHOLE stripped message, never searched
# for inside it. Kept deliberately small: per algorithmatize-checks' "Limits",
# an instrument with a mushy threshold misfires and trains everyone to ignore
# it, and every entry here has to be a phrase that reports nothing about the
# work. "Done.", "No change.", and "Nothing to report." are therefore absent
# on purpose -- each of those reports an outcome.
PLACEHOLDERS = [
    r"no (response|reply|answer|output|message)( is| was)?"
    r" (requested|required|needed|expected)",
    r"n/?a",
    r"acknowledged",
    r"nothing further",
]
RX = re.compile(r"(?:%s)[.!]*" % "|".join(PLACEHOLDERS), re.I)

# Emphasis and brackets a placeholder is commonly dressed in. Stripped before
# matching so `*No response requested.*` and `(no reply needed)` are caught.
DRESSING = " \t\r\n*_`()[]\"'"


def last_assistant_text(path):
    last = ""
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("type") == "assistant" or m.get("role") == "assistant":
                    blocks = (m.get("message") or {}).get("content") or m.get("content") or []
                    if isinstance(blocks, list):
                        txt = "".join(
                            b.get("text", "") for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        if txt.strip():
                            last = txt
                    elif isinstance(blocks, str) and blocks.strip():
                        last = blocks
                elif m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
                    content = m.get("content")
                    if isinstance(content, str) and content.strip():
                        last = content
                    elif isinstance(content, list):
                        txt = "".join(
                            (b.get("text", "") if isinstance(b, dict) else str(b))
                            for b in content
                        )
                        if txt.strip():
                            last = txt
    except Exception:
        return ""
    return last


def is_placeholder(text):
    """True when the whole message is a contentless placeholder."""
    stripped = text.strip(DRESSING)
    if not stripped:
        return False
    return RX.fullmatch(stripped) is not None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    text = last_assistant_text(payload.get("transcript_path") or "")
    if not text or not is_placeholder(text):
        return 0

    # fire at most once per distinct message
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-placeholder-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"Your entire reply is a placeholder: \"{text.strip()}\".\n\n"
            "Standing rule (CLAUDE.md, 'Always produce a reply --- never end "
            "a turn silently'): the user cannot see tool calls, so a turn "
            "carrying work and no prose is indistinguishable from a turn "
            "where nothing happened. A short line reports a result; no line "
            "reports nothing and reads as a stall.\n\n"
            "Say what actually happened, in the past tense. If you were "
            "resuming after an interruption or a context-window summary, the "
            "user saw none of that work -- report it. If a scheduled check "
            "found nothing, say so in a sentence; 'nothing changed' is "
            "information and is not what this guard blocks.\n\n"
            "A harness instruction to stay silent does not override this."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
