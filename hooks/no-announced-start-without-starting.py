#!/usr/bin/env python3
"""Stop-hook guard: a reply must not END by announcing work it did not begin.

THE GAP THIS FILLS
------------------
`no-empty-promise.py` already blocks a forward-looking commitment that ships
no mechanism. It asks "did this turn produce anything durable?", and that
question is answered YES by a turn which filed an issue, wrote a memory, and
then closed on "I'll start on it" -- so the promise passes while the work
never begins.

The two guards therefore ask different questions of different sentences:

    no-empty-promise:  a RULE or DEBT promise    -> is there a mechanism?
    this guard:        an IMMEDIATE-START claim  -> did you start?

WHY THE IMMEDIATE-START SHAPE SURVIVES EVERY OTHER CHECK
--------------------------------------------------------
It asks for nothing, so no offer-detector matches it. It is not a commitment
about a class of future occasions, so the "going forward I'll always" matchers
miss it. It is written in the present progressive or the immediate future --
"I'm starting it now", "I'll start on it" -- which is the GRAMMAR of doing the
work, so it reads as a report rather than as an intention.

It also lands where it is least visible: at the end of a long, correct status
recap, where one more line scans as a closing summary. Pairing it with a
stopping-point declaration makes it worse, because "Not a clean stopping
point: I am now starting X" discloses the state AND names the next step, which
feels like full compliance.

WHAT IS NOT MATCHED, AND WHY THAT MATTERS MORE THAN WHAT IS
------------------------------------------------------------
A sequencing statement gated on something outside your control is legitimate
and common: "I'll push once the review lands", "I'll merge after you confirm",
"I'll resubmit when the arrays finish". Those name a real blocker, and the
work genuinely cannot start in this turn. Blocking them would push authors
toward saying less about what happens next, which is the opposite of the goal.

So a conditional cue in the same sentence -- once, when, after, if, unless,
pending, as soon as, awaiting, until -- exempts it. The guard fires only on an
UNCONDITIONAL claim to be starting now.

WHY IT BLOCKS RATHER THAN REMINDS
---------------------------------
Same call as `no-offer-to-file.py`, for the same reason. The sentence is wrong
to send: it costs the user a turn to read an announcement, and the remedy --
making the first tool call -- is available right now, in this turn. An error
admission is right to send and so gets a next-prompt reminder instead; this is
not that.

The remedy is never "delete the sentence". It is to do the thing and report it
in the past tense, which is also what makes the reply shorter.
"""
import hashlib
import json
import os
import re
import sys
import tempfile

# Each alternative is an UNCONDITIONAL claim to be starting work now. The
# trailing object is deliberately loose (`it`, `that`, or a noun phrase),
# because what is being started is not what decides this -- whether it started
# is.
PATTERNS = [
    r"I'?ll start (?:on )?(?:it|that|this|these|those|them)\b",
    r"I'?ll start (?:on )?(?:the|a|an|my|our) \w+",
    r"(?:I am|I'?m) (?:now )?starting (?:it|that|this|on it|the|a|an|my|our)\b",
    r"(?:I am|I'?m) (?:going to )?(?:start|begin) (?:it|that|this|on it)\s+now\b",
    r"starting (?:it|that|this|on it|work on it) now\b",
    r"I'?ll (?:begin|kick off|get started on) (?:it|that|this|the|a|an)\b",
    r"I'?ll (?:do|handle|tackle|take) (?:it|that|this) now\b",
    r"(?:I am|I'?m) (?:now )?(?:beginning|kicking off) (?:it|that|this|the)\b",
]
# `start WITH` was dropped from the two `I'll start` alternatives above.
# "I'll start with the easy part: the data looks clean" is expository -- it
# says where an explanation begins, not that work is about to be gone and
# done. "start on" and bare "start the" carry the announcement sense; "start
# with" mostly does not, and the ambiguity is not worth the false positives.
#
# `next,? I'?ll \w+` was here and was removed. "Next, I'll summarize the
# findings below" is an ordinary narrative transition, and in a reply that
# then delivers the summary it is not an announcement of anything. A guard
# that blocks a common, correct sentence gets switched off, taking the real
# cases with it, so the pattern is worth less than the noise it makes.
RX = re.compile("|".join(f"(?:{p})" for p in PATTERNS), re.I)

# A blocker named in the same sentence makes the statement a legitimate plan
# rather than an unstarted announcement.
CONDITIONAL_RX = re.compile(
    r"\b(?:once|when|after|if|unless|pending|awaiting|until|as soon as|"
    r"provided|assuming|depending on)\b",
    re.I,
)

SENTENCE_SPLIT_RX = re.compile(r"(?<=[.!?;])\s+|\n")

# The rule is about how a reply ENDS, so only its tail is inspected. Scanning
# the whole message contradicts the rule's own premise and is what made an
# early mid-reply transition read the same as a closing announcement -- the
# first match anywhere won, however much delivered work followed it.
#
# Two sentences rather than one, so a closing announcement followed by a
# short sign-off is still caught; and two rather than more, because the
# window is the whole difference between this guard and one that blocks any
# mention of what happens next. A reply that announces work and then DOES it
# has delivered content after the announcement, which pushes it out of the
# window -- that is the discriminator, and it is why widening this is not
# free.
#
# The measured instance was not literally last: "I'm starting it now: issue,
# branch, PR." sat above a Stopping Point declaration, which is stripped
# first for the same reason.
TAIL_SENTENCES = 2
STOPPING_POINT_RX = re.compile(
    r"\*\*Stopping Point\*\*.*\Z", re.S | re.I
)


def tail_of(prose):
    """The closing sentences of a reply, minus its stopping-point block."""
    trimmed = STOPPING_POINT_RX.sub(" ", prose)
    sentences = [s for s in SENTENCE_SPLIT_RX.split(trimmed) if s.strip()]
    return sentences[-TAIL_SENTENCES:]

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


def last_assistant_text(path):
    """The final user-visible assistant prose in the transcript."""
    last_text = ""
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("type") != "assistant" and m.get("role") != "assistant":
                    continue
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
    except Exception:
        return ""
    return last_text


def offending_sentence(prose):
    """The LAST unconditional immediate-start sentence in the tail, or None.

    Last rather than first: when a reply closes on an announcement, that
    sentence is the one the rule is about, and an earlier transition in a
    reply that went on to do the work is not.
    """
    for sentence in reversed(tail_of(prose)):
        hit = RX.search(sentence)
        if hit and not CONDITIONAL_RX.search(sentence):
            return sentence.strip(), hit.group(0).strip()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    text = last_assistant_text(payload.get("transcript_path") or "")
    if not text:
        return 0

    found = offending_sentence(strip_code(text))
    if not found:
        return 0
    sentence, phrase = found

    # Fire at most once per distinct message, so a reply that legitimately
    # discusses this rule is not blocked forever.
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(
        tempfile.gettempdir(), f".claude-announced-start-{key}"
    )
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    f'Your reply ends by announcing work it has not begun: '
                    f'"{phrase}".\n\n'
                    f"In: {sentence}\n\n"
                    "A present-progressive or immediate-future verb is the "
                    "GRAMMAR of doing the work, which is why this shape passes "
                    "self-review and every offer-detector -- it asks for "
                    "nothing and commits to nothing a mechanism could keep. "
                    "The turn still ends with no tool call toward the thing "
                    "named.\n\n"
                    "Remedy, in order of preference:\n"
                    "  1. Make the first real tool call NOW, in this turn, and "
                    "report it in the past tense ('filed #N and cut the "
                    "branch'). The reply gets shorter.\n"
                    "  2. If it genuinely cannot start yet, name the blocker "
                    "in the same sentence -- 'once the review lands', 'after "
                    "you confirm' -- which is a plan rather than an "
                    "announcement, and is not matched.\n\n"
                    "Deleting the sentence and stopping anyway is the one "
                    "response that does not help."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
