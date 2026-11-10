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
# Gerunds that describe a state of mind, not work in progress.
_STATIVE = (
    r"(?:realiz|think|wonder|hop|feel|guess|assum|doubt|worr|forget|"
    r"understand|see|know|believ|suspect)ing"
)
# Verbs that announce work after "Next, I'll / I'm" (ai-config#5071). The rule
# is a POSITIVE list: only these verbs, in base or gerund form, start an
# announcement. An exclusion list ("anything except not, never, leave ...")
# is an open class, and each patch moved the hole from one word to the next
# (#5052, #5068). A positive list fails toward a missed announcement, which the
# other patterns and the two-sentence tail window partly cover, instead of a
# false block on every declining or stative sentence. To block a new
# announcing verb, add it here.
_WORK_VERBS = (
    "open file fix add run push merge review create write check build test "
    "update delete remove move rename implement draft post send start begin "
    "investigate read search grep fetch pull clone install deploy ship commit "
    "rebase resolve address patch refactor rewrite reproduce verify confirm "
    "retry rerun trigger dispatch subscribe request summarize explain record "
    "save document list look dig continue proceed finish wire land "
    "publish release tag triage close reopen cancel restart "
    "analyze analyse inspect debug trace diff compare compile "
    "format lint render regenerate generate port migrate sync revert "
    "backport squash upload download"
).split()
# Doubled final consonant in the gerund (run -> running).
_DOUBLE_FINAL = {
    "run", "rerun", "commit", "ship", "plan", "wrap", "drop", "cut", "split",
    "put", "set", "get", "begin", "grep", "tag", "dig", "debug", "format",
    "cancel",
}


def _gerund(verb):
    if verb in _DOUBLE_FINAL:
        return verb + verb[-1] + "ing"
    if verb.endswith("e") and not verb.endswith("ee"):
        return verb[:-1] + "ing"
    return verb + "ing"


# Verbs that also decline or stop work ("leave this alone", "pass on it",
# "stop here"), so only a collocation with an object announces work.
_OBJECT_VERBS = r"(?:pass(?:ing)?|leav(?:e|ing)|stop(?:ping)?|skip(?:ping)?|defer(?:ring)?)\s+(?:a|an|the|my|our|--\S+)\b"
_WORK_VERB_RX = (
    r"(?:"
    + "|".join(sorted({v for w in _WORK_VERBS for v in (w, _gerund(w))}))
    + r"|set(?:ting)?\s+up|kick(?:ing)?\s+off|go(?:ing)?\s+(?:ahead|through|over)|"
    r"tak(?:e|ing)\s+a\s+look|" + _OBJECT_VERBS + r")\b"
)
# "Next, I'm about to / poised to / committed to <verb>" is the same claim.
_LEAD_IN = (
    r"(?:(?:about|going|set|ready|due|poised|prepared|slated|scheduled|"
    r"committed|planning|preparing|aiming|all\s+set)\s+to\s+)?"
)

PATTERNS = [
    r"I'?ll start (?:on )?(?:it|that|this|these|those|them)\b",
    r"I'?ll start (?:on )?(?:the|a|an|my|our) \w+",
    r"(?:I am|I'?m) (?:now )?starting (?:it|that|this|on it|the|a|an|my|our)\b",
    r"(?:I am|I'?m) (?:going to )?(?:start|begin) (?:it|that|this|on it)\s+now\b",
    r"starting (?:it|that|this|on it|work on it) now\b",
    # The verbless form as a WHOLE sentence:
    # "Starting now.", "**Starting now.**", "Starting right now...".
    # Only emphasis markers may lead,
    # and only emphasis, `.`, `!` or an ellipsis may follow.
    # So these are not matched:
    # an expository "Starting now, the rule covers every repo",
    # "Starting now: X takes effect", a "## Starting now" heading,
    # and a "Starting now; ..." fragment.
    # Plan-bearing variants ("Starting now with the caches") are out of scope:
    # past `now` they are indistinguishable from exposition.
    # Like every pattern here, it is judged inside the two-sentence tail window,
    # so "Starting now." followed by one delivered sentence still blocks.
    # Measured 2026-10-08: "Starting now. I'll delete the caches first,
    # then move the two folders to D:" matched none of the alternatives above.
    r"^[\s*_]*(?:starting|beginning) (?:right )?(?:now|immediately)[\s*_.!\u2026]*$",
    r"I'?ll (?:begin|kick off|get started on) (?:it|that|this|the|a|an)\b",
    r"I'?ll (?:do|handle|tackle|take) (?:it|that|this) now\b",
    r"(?:I am|I'?m) (?:now )?(?:beginning|kicking off) (?:it|that|this|the)\b",
    r"(?:continuing|continue with)\s+(?:gia|gii|the\s+next|next\s+task|next\s+issue|phase\s+\d)\b",
    r"(?:I am|I'?m)\s+(?:now\s+)?continuing\s+(?:with\s+)?(?:gia|gii|the\s+next|next\s+task|next\s+issue|phase\s+\d)\b",
    # ai-config#5050: "Next I'm opening the first workflow PR", sent as a
    # closing post_message with no tool call after it. A sentence-leading
    # "Next" plus a first-person verb is an announcement; the two-sentence
    # tail window and the conditional exemption keep a mid-reply "Next, I'll
    # summarize below." that goes on to deliver from matching.
    # Only a verb on the positive list _WORK_VERBS may follow "Next, I'm /
    # I'll" (ai-config#5071), after an optional "about to / poised to / ..."
    # lead-in. Declining and stative sentences ("Next, I'll leave this alone",
    # "Next, I'm uncertain", "Next, I'll not touch it") are not listed, so
    # they pass without being enumerated.
    r"^[\s*_>-]*next(?: up)?,?:?\s+(?:I am|I'?m|I'?ll|I will)\s+(?:now\s+)?" + _LEAD_IN + r"(?=" + _WORK_VERB_RX + r")[a-z]+",
    r"(?:I am|I'?m)\s+now\s+(?!" + _STATIVE + r")[a-z]+ing\s+(?:it|that|this|the|a|an|my|our|them)\b",
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
    r"provided|assuming|depending on|blocked|blocker|blocking|waiting|"
    r"wait for)\b",
    re.I,
)

# There is no exemption for a sentence-leading "Next, I'll <verb>: ..." that
# appears to deliver content after a colon. Every proxy tried for "delivers"
# (a colon, an expository-verb list, a word count) was satisfied by padding
# that delivers nothing (agy and Claude reviews on #5052). The cost of the
# false positive is one block per distinct message, answered by rewording or
# doing the work, so an ungameable rule beats a gameable exemption.

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
# first for the same reason. But inspect candidates from both the trimmed tail
# (above stopping point) and the raw tail (to catch unstarted work announced
# inside the stopping point detail text).
TAIL_SENTENCES = 2
STOPPING_POINT_RX = re.compile(
    r"\*\*Stopping Point\*\*.*\Z", re.S | re.I
)


def tail_of(prose):
    """The closing sentences of a reply, covering both trimmed prose and stopping-point text."""
    trimmed = STOPPING_POINT_RX.sub(" ", prose)
    trimmed_sentences = [s for s in SENTENCE_SPLIT_RX.split(trimmed) if s.strip()]
    raw_sentences = [s for s in SENTENCE_SPLIT_RX.split(prose) if s.strip()]
    candidates = []
    if trimmed_sentences:
        candidates.extend(trimmed_sentences[-TAIL_SENTENCES:])
    if raw_sentences:
        candidates.extend(raw_sentences[-TAIL_SENTENCES:])
    return candidates

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


REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message)$", re.I)


def _post_message_text(block):
    """The text a project-thread reply sends: a hearthbot post_message call.

    In Claude Projects threads the user-facing message is not a text block but
    the `text` input of `mcp__hearthbot__post_message` (ai-config#5050), so a
    reader of text blocks alone never sees it.
    """
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return None
    # The user-visible reply tools, as the sibling hooks define them
    # (require-stopping-point.py, no-offer-to-file.py, no-self-thread-link.py).
    if not REPLY_TOOL_RX.search(str(block.get("name") or "")):
        return None
    text = (block.get("input") or {}).get("text")
    return text if isinstance(text, str) and text.strip() else None


def _is_work_call(block):
    """A tool call that is work, not the harness's own reply or end-of-turn call."""
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return False
    name = str(block.get("name") or "")
    # A reply tool call is never work, even with empty text (agy review on #5052).
    return not (name.startswith("mcp__hearthbot__") or REPLY_TOOL_RX.search(name))


def last_assistant_text(path):
    """The final user-visible assistant prose in the transcript.

    A reply-tool input (post_message and its siblings) wins over plain text
    blocks, because in a Projects thread plain text is not delivered, so a
    trailing log note must not hide the announcement that was sent. A work
    tool call (anything but a hearthbot or reply call) after either clears
    both, because the announcement was then followed by work.
    """
    last_text = ""
    last_posted = ""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                # Claude Code transcript format: type == "assistant" or role == "assistant"
                if m.get("type") == "assistant" or m.get("role") == "assistant":
                    blocks = (m.get("message") or {}).get("content") or m.get("content") or []
                    if isinstance(blocks, list):
                        parts = []
                        for b in blocks:
                            posted = _post_message_text(b)
                            if posted:
                                last_posted = posted
                            elif _is_work_call(b):
                                last_text, last_posted, parts = "", "", []
                            elif isinstance(b, dict) and b.get("type") == "text":
                                parts.append(b.get("text", ""))
                        txt = "".join(parts)
                        if txt.strip():
                            last_text = txt
                    elif isinstance(blocks, str) and blocks.strip():
                        last_text = blocks
                # Google Antigravity transcript format: source == "MODEL" and type == "PLANNER_RESPONSE"
                elif m.get("source") == "MODEL" and m.get("type") == "PLANNER_RESPONSE":
                    content = m.get("content")
                    if isinstance(content, str) and content.strip():
                        last_text = content
                    elif isinstance(content, list):
                        txt = "".join(
                            b.get("text", "")
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        if txt.strip():
                            last_text = txt
    except Exception:
        return ""
    return last_posted or last_text


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
        open(sentinel, "w", encoding="utf-8").close()
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
