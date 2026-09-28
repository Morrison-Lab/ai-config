#!/usr/bin/env python3
"""Stop-hook guard: warn on an idea raised as a chat-only FLAG/OFFER, unfiled.

`shared/workflow/report-mistakes-proactively.md`'s "An idea is filed the same
way a mistake is" extends the file-it-immediately rule from mistakes to
ideas -- an improvement, a follow-up, a proposed mechanism, anything with
nothing currently broken. The near-miss that prompted the extension: a
session found `Morrison-Lab/qwt` (the lab's website template) lacked the
`ai-config` plugin declaration, ended its reply with a chat-only
`⚠️ **FLAG**` proposing two ideas (sweep existing repos for the missing
declaration; add a mechanism to propagate template changes into repos
already created from one), and filed neither. The user had to ask "should we
file any of those ideas about templates and repo sweeps?" before they became
ai-config#4035 and #4036.

Every existing filing guard is keyed to a MISTAKE being described, which is
exactly why none of them fired on that reply:
  * `no-unfiled-finding.py` / `flag-unfiled-issue.py` match a defect being
    called worth tracking or still unfiled -- a proposal isn't phrased as a
    defect at all.
  * `flag-cop-out-offer.py` matches an offer's closing PERMISSION-ASKING
    phrasing ("want me to", "say the word") -- a `⚠️ **FLAG**` proposing an
    idea and simply moving on asks no such question, so it never lands in
    that hook's OFFERS list.
This hook is the missing instrument: it is keyed on the `⚠️ **FLAG**` /
`💡 **OFFER**` MARKERS themselves (CLAUDE.md's chat-output-tagging
convention), not on a defect-shaped assertion or a permission-asking close.

WHAT COUNTS AS "PROPOSING WORK"
--------------------------------
A `💡 **OFFER**` is, by CLAUDE.md's own definition, "optional work I can do
if they want it" -- every instance proposes work, so any OFFER block
qualifies without a further vocabulary check.

A `⚠️ **FLAG**` is defined more broadly ("non-blocking heads-up or risk"),
and most flags are not issue-shaped -- a merge-order note, a status update,
a risk with no proposal attached. Gating every FLAG would make this as
disruptive as gating every FLAG in `no-unfiled-finding.py`'s sibling, and
get switched off for it. So a FLAG additionally needs an idea-proposal cue
in its own text (see IDEA_CUE) -- vocabulary for suggesting a new mechanism,
sweep, or follow-up, rather than merely naming a risk.

DISCHARGE
---------
An issue or PR reference anywhere in the message -- a citation of one already
filed (reusing `no-unfiled-finding.py`'s `RX_ALREADY`), a bare issue/PR URL,
or an issue-create / issue-comment / PR-create tool call anywhere in the
turn -- discharges the warning. Matching on presence in the message, not
argument extraction, keeps this a lexical guard rather than a semantic one:
whether the cited issue is the SAME idea the FLAG names is not lexically
decidable, and a false negative here (a citation that turns out to be
unrelated) is the same shape of miss `RX_ALREADY` already accepts everywhere
else in this file's sibling.

WARNS, never blocks. Whether a given FLAG/OFFER is genuinely idea-shaped
is not fully decidable from vocabulary alone -- IDEA_CUE will both miss a
proposal phrased unusually and catch a risk note that happens to share a
word ("consider", "worth") with a real proposal. A block on a guess this
loose would be worse than the omission it exists to catch.

Fails OPEN on any parse trouble or missing sibling, and fires at most once
per distinct message.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))


def _sibling(name):
    """Import a hyphenated sibling module, or None if unavailable."""
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location("_sib", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_unfiled = _sibling("no-unfiled-finding.py")

visible_prose = getattr(_unfiled, "visible_prose", None)
scan = getattr(_unfiled, "scan", None)
RX_ALREADY = getattr(_unfiled, "RX_ALREADY", None)

# The chat-output-tagging markers from CLAUDE.md, each captured with the text
# that follows it up to the next marker (or a bounded window, or the end of
# the message) -- that trailing span is what IDEA_CUE is checked against.
MARKER = re.compile(
    r"(?P<kind>\N{WARNING SIGN}️?\s*\*\*FLAG\*\*|"
    r"\U0001F4A1\s*\*\*OFFER\*\*)"
    r"(?P<body>.{0,400})",
    re.S,
)

# Vocabulary a FLAG needs to read as proposing an idea rather than merely
# naming a risk or a status. Deliberately broad -- this only gates a WARN,
# and a FLAG that trips it and isn't actually idea-shaped costs one line of
# context, not a blocked turn.
IDEA_CUE = re.compile(
    r"\b(could|should|worth (building|adding|doing|a )|"
    r"consider (building|adding)|a mechanism (to|for)|propos\w*|"
    r"sweep\w*|follow-?up|we could|it would (help|let)|"
    r"add(?:ing)? a (check|hook|mechanism)|build\w* a (hook|mechanism|check))\b",
    re.I,
)

RX_ALREADY_URL = re.compile(
    r"https?://\S*/(issues|pull|pulls|merge_requests)/\d+", re.I
)

# An idea can land directly as a PR too, not only an issue -- discharge
# either creation path, anywhere in the turn (not gated to occurring after
# the marker), the same breadth `RX_FILE`-style discharges use elsewhere in
# this corpus.
RX_CREATE = re.compile(
    r"create_issue|gh\s+issue\s+create|gh\s+issue\s+comment|"
    r"issues/\d+/comments|mcp__github__create_issue|"
    r"mcp__github__issue_write|add_issue_comment|"
    r"gh\s+pr\s+create|glab\s+(issue|mr)\s+create|"
    r"mcp__github__create_pull_request",
    re.I,
)


def find_unfiled_idea(text):
    """Return the matched marker text, or None if every FLAG/OFFER is filed."""
    stripped = visible_prose(text) if visible_prose else text
    for m in MARKER.finditer(stripped):
        kind = m.group("kind")
        body = m.group("body") or ""
        is_offer = "OFFER" in kind
        if not is_offer and not IDEA_CUE.search(body):
            continue
        window = kind + body
        if RX_ALREADY.search(window) or RX_ALREADY_URL.search(window):
            continue
        return kind.split("**")[1] if "**" in kind else kind
    return None


def main() -> int:
    if visible_prose is None or scan is None or RX_ALREADY is None:
        return 0  # sibling unavailable; degrade to silence

    try:
        payload = json.load(sys.stdin)
        transcript_path = payload.get("transcript_path") or ""
        _, _, text = scan(transcript_path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0

    label = find_unfiled_idea(text)
    if not label:
        return 0

    # A create call ran ANYWHERE in this turn's transcript -- reread it raw
    # rather than trusting `scan`'s single last-text return, since the idea
    # may be filed by a tool call that ran after the FLAG/OFFER text itself.
    try:
        with open(transcript_path, errors="ignore") as fh:
            raw = fh.read()
    except Exception:
        raw = ""
    if RX_CREATE.search(raw):
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-idea-warn-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    print(json.dumps({"systemMessage": (
        f"Your reply raises an idea in a {label} with no issue or PR filed "
        "for it in this transcript. Per "
        "shared/workflow/report-mistakes-proactively.md's 'An idea is filed "
        "the same way a mistake is', a chat-only FLAG or OFFER is a "
        "heads-up, not a filing -- file it now (dupe-check, then "
        "`gh issue create` / `mcp__github__issue_write`), or say why this "
        "one is passing speculation rather than a concrete, actionable idea."
    )}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
