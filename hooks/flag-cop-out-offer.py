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
        with open(path, errors="ignore") as fh:
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
                elif m.get("type") in {"PLANNER_RESPONSE", "GENERIC"} or m.get("source") == "MODEL":
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    texts = last_visible_texts(payload.get("transcript_path") or "")
    if not texts:
        return 0
    phrase = next((p for p in (find_offer(t) for t in texts) if p), None)
    if not phrase:
        return 0

    # `last_visible_texts` returns at most one string, so the sentinel hashes
    # exactly what earlier revisions hashed and the once-per-distinct-message
    # behaviour is unchanged.
    key = hashlib.sha256("|".join(texts).encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-copout-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    # A warn-only Stop hook must emit `systemMessage` on stdout: stderr alone
    # can be discarded, so a guard that writes only there is indistinguishable
    # from one that never fired. That is the failure this hook is about --
    # something that looks like it is working and delivers nothing.
    print(json.dumps({"systemMessage": (
        f"Your reply closes on an offer to do work: \"{phrase}\". "
        "Was that action already authorized? If so, do it and report in the "
        "past tense -- an unanswered offer leaves no branch, no PR, no issue."
    )}))

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
