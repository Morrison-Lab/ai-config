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

Interrupts the stop at most once per turn (agent_notice.stop_notice), and
never wedges it, so the agent reads the warning (ai-config#4796); it never
decides for the agent. Whether the underlying action was already authorized is
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

It also flags OPTIONAL work left as a closing remark ("optional", "I can also
fix ...", "as a follow-up") when no issue was filed or linked in the same turn
(ai-config#4962): optional items are filed as issues, and done at once when
they are important or quick. A link to an issue in the reply, an issue_write
create call, or a `gh issue create` after the last user message counts as filed.

Fires once per distinct message (sentinel keyed by content hash).
Fails OPEN.
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
from sibling import load_sibling  # noqa: E402 -- ai-config#2018
from transcript_meta import is_real_user_turn as _is_user_turn  # noqa: E402 -- ai-config#4983

# Matched against the LAST few lines of the reply only.
OFFERS = [
    r"say the word",
    r"(just )?let me know (if|when|whether|either)",
    r"(do you |would you )?want me to\b",
    r"would you like me to\b",
    r"shall i\b",
    r"should i (go ahead|proceed)",
    r"i can .{0,60}\bif you(('d| would) (like|prefer)| want)\b",
    r"happy to .{0,40}\bif you\b",
    r"i'?d be glad to\b",
    r"unless you'?d rather",
    r"if that works for you",
    r"(ready|standing by) to .{0,40}\bwhen you('re| are)\b",
    r"once you confirm",
]
RX = re.compile("|".join(OFFERS), re.I)

# Optional work left as a closing remark instead of a filed issue
# (ai-config#4962; Ezra, 2026-11-04: "always at least file optional items as
# issues, and do them immediately if they are important and/or quick").
# Matched against the same tail windows as OFFERS.
# Every entry is phrase-bound: a bare "optional" fires on "this parameter is
# optional" in ordinary technical prose, and "could also X" / "I can X" fire on
# routine suggestions (review of #4979). Conditional offers ("I can X if you
# want") belong to OFFERS above.
OPTIONAL_WORK = [
    r"\boptional (work|items?|fix(es)?|nits?|follow-?ups?|cleanups?|improvements?)\b",
    r"\b(items?|fix(es)?|nits?|cleanups?|follow-?ups?)\b[^.;?!:\n]{0,30}\b(is|are) optional\b",
    r"\b(could|can|will|would|should|'ll|plan to)\b[^.;?!:\n]{0,40}\bas a (small |separate )?follow-?up\b",
    # The span starts at the NEAREST "nits" before the verb (it cannot contain
    # another one) and may cross "and"/"or"/"nor" joining nouns ("no nits or
    # issues remain"). Clause breaks are looked for only outside the span, in
    # find_optional (review of #4979, rounds 9-11).
    r"\bnits?\b(?:(?!\bnits?\b)[^.;?!:,\n]){0,60}?\b(left|remain|unfiled|not fixed)\b",
]
OPTIONAL_RX = re.compile("|".join(OPTIONAL_WORK), re.I)

# A sentence that says nothing is outstanding ("no further nits are left",
# "there aren't any nits left", "all nits were fixed") is a completion report,
# whatever the distance between the negation and the matched phrase. Checked
# per sentence instead of by regex adjacency (review of #4979, rounds 3-5).
DONE_RX = re.compile(
    r"\b(aren't|isn't|are not|is not|there's not|there is not|there are not)\s+(any|a)\b"
    r"|\ball\b[^.;?!:\n]*\b(fixed|addressed|done|resolved)\b",
    re.I,
)

# A bare negation counts only when it can be about the matched phrase: after
# it ("nits remain: none"), or at most NEG_REACH words before it ("no further
# outstanding nits remain"). "no one" negates a person, never a nit, and a
# negation further back is a different thought, so the run-on "No one
# complained still two nits remain unfiled" is not a completion report
# (ai-config#4988).
NEG_RX = re.compile(r"\b(?:no(?!\s+one\b)|none|zero|nothing)\b", re.I)
NEG_REACH = 3


# A clause ends at . ; ? ! : , or a newline, or at a contrast word ("but",
# "however", ...), so "no nits remain in A, but two nits remain in B" and
# "No one complained, two nits remain though" are each two clauses (review of
# #4979, rounds 5-8). Splitting at every comma errs toward warning on a list
# such as "no bugs, nits, or issues remain"; one extra once-per-message notice
# is the cheaper mistake than a silent miss.
BREAK_RX = re.compile(
    r"[.;?!:,\n]|\s*\b(?:but|however|though|although|while|whereas|yet|and|or|nor|so)\b",
    re.I,
)


def _sentence_around(window, start, end):
    """The clause holding window[start:end]."""
    breaks = list(BREAK_RX.finditer(window))
    left = max((b.end() for b in breaks if b.end() <= start), default=0)
    right = min((b.start() for b in breaks if b.start() >= end), default=len(window))
    return window[left:right]


def _is_completion_report(window, start, end):
    """True when the clause around window[start:end] says nothing is outstanding."""
    clause = _sentence_around(window, start, end)
    if DONE_RX.search(clause):
        return True
    offset = max(window.find(clause), 0)
    rel_start = start - offset
    for neg in NEG_RX.finditer(clause):
        if neg.end() > rel_start:
            return True  # a negation after the phrase starts: as before
        if len(clause[neg.end():rel_start].split()) <= NEG_REACH:
            return True
    return False


# A message carrying a FLAG or OFFER marker belongs to flag-idea-without-issue.py,
# which already files ideas proposed that way; this hook leaves it alone so one
# message does not trip two independently maintained matchers (review of #4979).
MARKER_RX = re.compile(r"\*\*(FLAG|OFFER)\*\*")

HERE = os.path.dirname(os.path.realpath(__file__))


def _sibling(name):
    """Import a hyphenated sibling module, or None (scripts/lib/sibling.py)."""
    return load_sibling(__file__, name)


# Evidence that an issue was filed or linked in the same turn: reuse the
# discharge patterns flag-idea-without-issue.py and no-unfiled-finding.py
# already own, rather than keeping a narrower copy here.
_idea = _sibling("flag-idea-without-issue.py")
_unfiled = _sibling("no-unfiled-finding.py")
RX_CREATE = getattr(_idea, "RX_CREATE", None)
RX_ALREADY_URL = getattr(_idea, "RX_ALREADY_URL", None)
RX_ALREADY = getattr(_unfiled, "RX_ALREADY", None)

# How much of the tail to inspect. An offer is the closing move, so a short
# window is the point: it keeps a mid-message aside from firing.
TAIL_CHARS = 400


# In a project-thread session every user-visible sentence is the `text` input
# of an `mcp__hearthbot__reply` tool call, never an assistant text block --
# that tool's own description says "This is the ONLY way to message the user
# in a thread - your normal text output is not shown". So a
# reader that only walks `type == "text"` blocks is blind to the whole reply,
# which is exactly where a closing offer lives. Measured 2026-09-19: this hook
# did not fire on a cop-out offer whose phrase is in OFFERS, sits well inside
# TAIL_CHARS, and would have matched had the text been reachable.
REPLY_TOOL_RX = re.compile(r"(^|__)(reply|post_message|update_message)$", re.I)


def _blocks(msg):
    blocks = (msg.get("message") or {}).get("content") or msg.get("content") or []
    return blocks if isinstance(blocks, list) else []


def _reply_payload(block):
    """The user-visible text of a reply-tool call, or '' for any other block."""
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return ""
    if not REPLY_TOOL_RX.search(block.get("name") or ""):
        return ""
    inp = block.get("input")
    if not isinstance(inp, dict):
        return ""
    txt = inp.get("text")
    return txt if isinstance(txt, str) else ""


def last_visible_texts(path):
    """The last message as the user actually read it.

    A transcript carrying any reply-tool call is a project-thread session,
    where a plain text block is never delivered -- so the reply payload is
    the only channel, and checking the text block too would warn about a
    sentence nobody saw. A transcript with no reply-tool call anywhere is an
    ordinary CLI session, where the text block is the delivered channel.

    Returns a one-element list, or an empty one when neither channel spoke.
    """
    last_text = ""
    last_reply = ""
    saw_reply_tool = False
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if m.get("type") == "assistant" or m.get("role") == "assistant":
                    blocks = _blocks(m)
                    if blocks:
                        txt = "".join(
                            b.get("text", "") for b in blocks
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                        if txt.strip():
                            last_text = txt
                        for b in blocks:
                            if isinstance(b, dict) and b.get(
                                "type"
                            ) == "tool_use" and REPLY_TOOL_RX.search(
                                b.get("name") or ""
                            ):
                                saw_reply_tool = True
                            payload = _reply_payload(b)
                            if payload.strip():
                                last_reply = payload
                    else:
                        raw = (m.get("message") or {}).get("content") or m.get("content")
                        if isinstance(raw, str) and raw.strip():
                            last_text = raw
                elif m.get("type") == "PLANNER_RESPONSE":
                    content = m.get("content")
                    if isinstance(content, str) and content.strip():
                        last_text = content
                    elif isinstance(content, list):
                        txt = "".join(
                            (b.get("text", "") if isinstance(b, dict) else str(b))
                            for b in content
                        )
                        if txt.strip():
                            last_text = txt
    except Exception:
        return []
    # The reply tool having been *called* is what identifies the harness, not
    # whether its payload was non-empty -- so a thread session whose last turn
    # spoke only through an empty or absent reply payload yields nothing here
    # rather than falling back to narration the user never saw.
    chosen = last_reply if saw_reply_tool else last_text
    return [chosen] if chosen.strip() else []


# `flag-session-boundaries` requires every reply to end with a stopping-point
# declaration, and for a non-clean stop it requires the pending work to follow
# that declaration. In a session with several open PRs that block routinely
# runs longer than TAIL_CHARS on its own, which pushed the actual closing move
# out of the window entirely -- so obeying one rule made this hook blind to
# violations of another (ai-config#3694). Cut the declaration off before
# taking the tail, rather than widening the window, which would re-admit the
# mid-message asides the short window exists to exclude.
STOPPING_POINT_RX = re.compile(r"\*\*Stopping Point\*\*", re.I)


def offer_windows(text):
    """The regions of a reply where a closing move can appear.

    Without a stopping-point declaration there is one: the tail.

    With one there are two, and dropping either loses real offers.
    `flag-session-boundaries` puts the pending work AFTER the declaration and
    calls it "the final and most visible element of the reply", so an offer
    can sit there -- and cutting everything from the marker onward would make
    that position permanently safe, which is a worse blind spot than the one
    this fix set out to close. But the declaration itself is long enough to
    push a preceding offer out of a fixed tail, so the pre-marker region
    cannot simply be ignored either.

    So: the tail of the whole reply, which is the ordinary closing move and
    covers an offer sitting at the end of the pending-work section; plus the
    tail of the text BEFORE the declaration, which is the region the
    declaration displaced.

    Both are tails. Handing back the post-marker region whole would let an
    aside buried mid-block fire with paragraphs of unrelated status after it,
    which is the very thing TAIL_CHARS exists to prevent -- the first attempt
    at this did that, and it was caught in review on ai-config#3695.
    """
    body = text.strip()
    matches = list(STOPPING_POINT_RX.finditer(body))
    if not matches:
        return [body[-TAIL_CHARS:]]
    cut = matches[-1].start()
    return [body[-TAIL_CHARS:], body[:cut].strip()[-TAIL_CHARS:]]


def find_offer(text):
    """Return the matched offer phrase when the reply CLOSES on one."""
    for window in offer_windows(text):
        m = RX.search(window)
        if m:
            return m.group(0)
    return None


def find_optional(text):
    """Return the optional-work phrase when the reply closes on one."""
    for window in offer_windows(text):
        m = next((x for x in OPTIONAL_RX.finditer(window)
                  if not _is_completion_report(window, x.start(), x.end())), None)
        if not m:
            continue
        start = window.rfind("\n\n", 0, m.start()) + 1
        end = window.find("\n\n", m.end())
        paragraph = window[start:end if end >= 0 else len(window)]
        if MARKER_RX.search(paragraph):
            continue  # that paragraph is flag-idea-without-issue.py's case
        return m.group(0)
    return None


def filed_issue_this_turn(path, reply_text):
    """True when the reply links an issue or this turn filed one.

    The turn is everything after the last real user message. A reply that
    cites an issue URL counts, because filing and linking are the two halves
    of the rule.
    """
    if RX_CREATE is None or RX_ALREADY is None or RX_ALREADY_URL is None:
        return True  # fail open: the shared discharge patterns are unavailable
    if RX_ALREADY.search(reply_text or "") or RX_ALREADY_URL.search(reply_text or ""):
        return True
    filed = False
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                if _is_user_turn(m):
                    filed = False
                    continue
                for b in _blocks(m):
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    blob = (b.get("name") or "") + " " + json.dumps(b.get("input") or {})
                    if RX_CREATE.search(blob):
                        filed = True
    except Exception:
        return True  # fail open: an unreadable transcript is not evidence of a slip
    return filed


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    texts = last_visible_texts(payload.get("transcript_path") or "")
    if not texts:
        return 0
    phrase = next((p for p in (find_offer(t) for t in texts) if p), None)
    optional = next((p for p in (find_optional(t) for t in texts) if p), None)
    if optional and filed_issue_this_turn(payload.get("transcript_path") or "", texts[0]):
        optional = None
    if not phrase and not optional:
        return 0

    # `last_visible_texts` returns at most one string, so the sentinel hashes
    # exactly what earlier revisions hashed and the once-per-distinct-message
    # behaviour is unchanged.
    key = hashlib.sha256("|".join(texts).encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-copout-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w", encoding="utf-8").close()
    except Exception:
        pass

    # The warning must reach the agent: stderr alone is discarded, and a
    # `systemMessage` reaches only the user, so either makes a guard
    # indistinguishable from one that never fired (ai-config#4796). That is
    # the failure this hook is about -- something that looks like it is
    # working and delivers nothing. stop_notice blocks once per turn, with
    # the warning as the reason the agent reads.
    parts = []
    if phrase:
        parts.append(f"Your reply closes on an offer to do work: \"{phrase}\". "
                     "Was that action already authorized? If so, do it and report in the "
                     "past tense -- an unanswered offer leaves no branch, no PR, no issue.")
    if optional:
        parts.append(f"Your reply leaves optional work as an offer: \"{optional}\", and no "
                     "issue was filed or linked this turn. File each optional item as an "
                     "issue now, and do it immediately if it is important or quick "
                     "(shared/workflow/report-mistakes-proactively.md, \"An idea is filed "
                     "the same way a mistake is\").")
    print(stop_notice(payload, " ".join(parts), "flag-cop-out-offer"))

    sys.stderr.write(
        f"[hook: flag-cop-out-offer] Your reply closes on an offer: "
        f"\"{phrase or optional}\".\n\n"
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
