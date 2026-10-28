#!/usr/bin/env python3
"""UserPromptSubmit reminder: hedged wording is a draft to improve on.

Ezra (2026-10-28, ai-config#4813): "something like" and similar phrasing in an
instruction means he is open to suggestions; the wording is a draft, not text
to copy. Even unhedged, his instructions are never to be followed blindly:
check them against the goal and say so when something better exists.
AGENTS.md "Don't take anyone's word for it" and "Proactively suggest better
alternatives" are the canonical rules; this hook only prompts them when the
prompt contains a hedge, because a hedge is the explicit invitation.

Injects, never blocks. Fails OPEN and SILENT: any parse trouble prints nothing.
Fires on every prompt with a hedge (the reminder is cheap and each prompt's
wording is its own).
"""
import json
import re
import sys

HEDGE_RE = re.compile(
    r"""(
      \bsomething\s+like\b
    | \balong\s+the\s+lines\b
    | \bsomething\s+to\s+that\s+effect\b
    | \bor\s+similar\b
    | \bor\s+something\b
    | \bmaybe\b
    | \bperhaps\b
    | \be\.g\.
    | \bfor\s+example\b
    | \bfor\s+instance\b
    | \broughly\b
    | \bsort\s+of\b
    | \bkind\s+of\s+like\b
    | \bwording\s+like\b
    | \bsomething\s+similar\b
    )""",
    re.I | re.X,
)
FENCE = re.compile(r"```.*?```", re.S)
QUOTED = re.compile(r"^\s*>.*$", re.M)
TICKED = re.compile(r"`[^`\n]*`")
REMINDER_BLOCK = re.compile(r"<system-reminder>.*?</system-reminder>", re.S | re.I)
MIN_CHARS = 25


def hedge(text):
    prose = TICKED.sub(" ", QUOTED.sub(" ", FENCE.sub(" ", REMINDER_BLOCK.sub(" ", text))))
    if len(prose.strip()) < MIN_CHARS:
        return None
    m = HEDGE_RE.search(prose)
    return " ".join(m.group(0).split()) if m else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        prompt = payload.get("prompt") if isinstance(payload, dict) else None
        found = hedge(prompt) if isinstance(prompt, str) else None
    except Exception:
        return 0
    if found:
        print(
            f'Hedged-wording reminder: the prompt says "{found}".\n'
            "That wording (and any draft text, example or phrasing in the "
            "message) is a suggestion to improve on, not text to copy "
            "verbatim or relay as the fix. Work out the goal, check the "
            "wording against it, and use or propose something better. Even "
            "unhedged instructions are never followed blindly."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
