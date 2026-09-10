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

# A second shape the PATTERNS above cannot see: the offer phrased as a
# DECLARATIVE PREFERENCE rather than a question, referring to the artifact by
# anaphora ("a ninth") rather than by name. It reads as deference instead of a
# request, so it survives self-review, and no pattern above matches it.
# Requires filing/recording vocabulary in the same message, so an unrelated
# deferral ("I'd rather you decide which merge strategy") does not fire.
DEFER = [
    r"i'?d rather (you|we) (tell|decide|say|choose|pick)",
    r"i'?(ll| will) leave (it|that|this|the|that) ?(call|decision)? ?(to|with) you",
    r"your call whether",
]
RX_DEFER = re.compile("|".join(DEFER), re.I)

# Filing/recording domain, deliberately broader than PATTERNS' verb list so an
# anaphoric reference still lands as long as the message names the domain
# somewhere.
DOMAIN = re.compile(
    r"\b(issues?|filed|filing|(tracking|tracker) issue|follow-?ups?)\b",
    re.I,
)


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
        """Strip fenced code blocks and inline backtick code spans."""
        return _CODE_SPAN_RE.sub(" ", _FENCE_RE.sub(" ", text))


_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]*")


def _defer_hit(prose):
    """A deferral only counts when the filing vocabulary is in the SAME sentence.

    A whole-message conjunction fires on any long reply that defers about one
    thing and happens to mention an issue elsewhere, which blocks a legitimate
    turn (ai-config#3520 review round 1).
    """
    for sentence in _SENTENCE_RE.findall(prose):
        if RX_DEFER.search(sentence) and DOMAIN.search(sentence):
            return RX_DEFER.search(sentence)
    return None


def _seen_once(text):
    """True when this exact message already produced output (idempotence)."""
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-offer-warn-{key}")
    if os.path.exists(sentinel):
        return True
    try:
        open(sentinel, "w").close()
    except Exception:
        pass
    return False


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
        # The DEFER arm WARNS rather than blocks, and the reason is precision
        # rather than the undecidable-authorization argument
        # flag-cop-out-offer.py makes -- that hook matches reliably and warns
        # because the right RESPONSE is undecidable, which is a different
        # problem. Here the DETECTION is the uncertain half: scored against
        # ten probes (three real deferrals, seven ordinary sentences) this
        # arm was 3/3 and 0/7, but ten hand-written probes are not evidence
        # of a rate. Warning keeps a misfire cheap while the sample grows.
        defer = _defer_hit(prose)
        if defer and not _seen_once(text):
            print(json.dumps({"systemMessage": (
                "[hook: no-offer-to-file] This reply defers a filing decision "
                f"back to the user ({defer.group(0)!r}) in a sentence that also "
                "names filing or tracking.\n"
                "report-mistakes-proactively: file a valid finding without asking, "
                "and note that how many you have already filed is not an input.\n"
                "Warning only -- disregard if this deferral is not about filing."
            )}))
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
