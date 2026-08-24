#!/usr/bin/env python3
"""Stop-hook guard: catch offering to file/record instead of just doing it.

`report-mistakes-proactively` and the user's standing `cai` both say to file
issues and record learnings *without* asking. The rule is read at load time;
the violation happens at composition time, in the closing paragraph of a long
message, where no rule is being consulted. So re-reading the rule does not
prevent it -- observed three times on 2026-07-29.

Two distinct shapes, both matched below:
  1. a pure offer   -- "worth saving as a memory?"
  2. a bundled one  -- "want me to file the issue and open that PR?", where a
     genuinely discretionary action (the PR) carries an ungated one (the issue)

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

# Offer-shaped, and specifically about filing/recording rather than about
# doing implementation work (which IS the user's call to gate).
PATTERNS = [
    r"want me to (file|open an issue|record|save|capture|note)",
    r"(should|shall) i (file|record|save|capture|memorize)",
    r"say the word and i('ll| will) (file|record|save|capture)",
    r"worth (an issue|filing|a memory|saving|capturing|recording)\b[^.]*\?",
    r"(let me know|tell me) if you('d| would) like me to (file|record|save)",
    r"i (could|can) file (an|a) (issue|follow-?up)[^.]*\?",
]
RX = re.compile("|".join(PATTERNS), re.I)


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


try:
    _lib = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "scripts", "lib"
    )
    if _lib not in sys.path:
        sys.path.insert(0, _lib)
    from fences import strip_code
except Exception:
    _FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
    _CODE_SPAN_RE = re.compile(
        r"(?<!`)(`+)(?!`)(?:[^\n\r]|\r?\n(?![ \t]*\r?\n))*?(?<!`)\1(?!`)"
    )

    def strip_code(text: str) -> str:
        return _CODE_SPAN_RE.sub(" ", _FENCE_RE.sub(" ", text))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    text = last_assistant_text(payload.get("transcript_path") or "")
    if not text:
        return 0

    prose = strip_code(text)
    hit = RX.search(prose)
    if not hit:
        return 0

    # fire at most once per distinct message
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-offer-guard-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"Your message offers to file/record rather than doing it: "
            f"\"{hit.group(0).strip()}\".\n\n"
            "Standing rule (report-mistakes-proactively, plus the user's own "
            "`cai`): file issues and record learnings WITHOUT asking. A "
            "duplicate is cheap; a lost observation is not, and only the user "
            "can say a thing is not worth keeping -- which they can do after "
            "it exists.\n\n"
            "If this is the BUNDLED shape -- a discretionary action (opening a "
            "PR, making a code change) sharing a sentence with an ungated one "
            "(filing, recording) -- split them: do the ungated part now, then "
            "ask about the remainder only.\n\n"
            "Dupe-check first, then file or comment, then cite the identifier "
            "the API actually returned."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
