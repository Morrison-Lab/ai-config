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
Both `💡 **OFFER**` and `⚠️ **FLAG**` need an idea-proposal cue in their own
text (see IDEA_CUE) -- vocabulary for suggesting a new mechanism, sweep,
follow-up, or improvement, rather than merely naming a risk or offering
routine continuation work. Earlier revisions let every OFFER through
unconditionally, on the reasoning that CLAUDE.md defines one as "optional
work I can do if they want it" -- but that definition covers the ordinary
"want me to merge this now that it's clean?" and "I can push this fix now"
just as much as a genuine proposal, and neither of those is an idea to file.
Gating every FLAG the same way (rather than only the OFFER-shaped ones)
would make this as disruptive as gating every FLAG in
`no-unfiled-finding.py`'s sibling, and get switched off for it.

`could`/`should` are deliberately phrase-bound (`we could`, `it should`,
`could add`, and similar), not bare words, because an earlier draft matched
`could` anywhere and fired on a plain status line like "review could take a
while" -- a time estimate, not a proposal.

DISCHARGE
---------
Turn-scoped, not session-scoped. A citation of an issue/PR already filed
(reusing `no-unfiled-finding.py`'s `RX_ALREADY`) or a bare issue/PR URL
discharges when it sits in the SAME message as the FLAG/OFFER -- checked
against that message's own text, so this half was always turn-scoped.

The creation-call half is turn-scoped by ordering, the same way the sibling
hooks use `scan()`'s `last_file`/`last_say`: an issue-create, issue-comment,
or PR-create call ONLY discharges when it ran at or after the message
carrying the FLAG/OFFER (`_last_create_index()` below, compared against
`scan()`'s own `last_say`). An earlier revision searched the WHOLE transcript
for a creation call, so any unrelated filing anywhere earlier in the session
silenced every later, unrelated idea for the rest of that session -- the
same "shares a call, decides nothing" shape
`shared/workflow/check-before-pushing.md` and this corpus's own
`no-stale-pr-status.py`-adjacent guards warn against, here applied to time
rather than to a shared Bash call. Matching on presence, not argument
extraction, keeps both discharges lexical rather than semantic: whether the
cited issue is the SAME idea the FLAG names is not decidable this way, and a
false negative here (a citation that turns out to be unrelated) is the same
shape of miss `RX_ALREADY` already accepts everywhere else in this file's
sibling.

WARNS, never blocks. Whether a given FLAG/OFFER is genuinely idea-shaped is
not fully decidable from vocabulary alone -- IDEA_CUE will both miss a
proposal phrased unusually and catch a risk note that happens to share a
word ("consider", "worth") with a real proposal. A block on a guess this
loose would be worse than the omission it exists to catch.

LEXICAL LIMITS
--------------
- IDEA_CUE is checked only against the 400 characters immediately following
  a FLAG/OFFER marker (MARKER's `body` group), not the whole message -- a
  cue sitting past that window goes undetected. This is a known limit, not
  desired behaviour: a marker whose proposal is stated more than 400
  characters after the marker itself reads, to this hook, the same as a
  marker with no proposal at all.
- IDEA_CUE's phrase-bound forms (`could`/`should`, the mechanism/sweep/
  follow-up/improvement patterns below) are deliberately narrow rather than
  bare words, for the same reason `could`/`should` are phrase-bound: a bare
  mechanism/sweep/follow-up/propose/improvement word-stem match (no
  surrounding proposal phrase required) fires on ordinary status and
  negated text ("the retry mechanism failed twice", "I already ran a sweep
  and found nothing", "no improvement over the previous run"), none of
  which propose anything.

WHAT THIS HOOK CANNOT SEE, AND WHY THE RULE STILL COVERS IT
-------------------------------------------------------------
This hook is lexical: it can only warn on a FLAG or OFFER that was actually
typed into the reply. It has no way to notice a defect that a session
noticed and never mentioned at all -- a plain prose aside describing another
repo's content in passing, with no marker and no proposal language, is
invisible to a pattern match by construction.
The fragment's own rule is NOT scoped to what got said: it is keyed to
NOTICING a defect, and staying silent about a noticed one is the same
violation as flagging it and leaving it unfiled, not a way to avoid tripping
this hook. See "An idea is filed the same way a mistake is" and its second
dated incident (Morrison-Lab/rme#1209, a defect named in an ANSWER block
with no marker at all) for the case this hook cannot catch. Read this
hook's silence on a given reply as "no marker-shaped idea went unfiled in
that reply", never as "nothing was noticed and left unfiled".

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

# Vocabulary a FLAG or OFFER needs to read as proposing an idea rather than
# merely naming a risk, a status, or routine continuation work. Deliberately
# broad in SHAPE -- this only gates a WARN, and a marker that trips it and
# isn't actually idea-shaped costs one line of context, not a blocked turn --
# but every alternative below is phrase-bound to a proposal form rather than
# a bare word, because a bare word fires on ordinary status and negated text.
#
# `could`/`should` are phrase-bound (a subject pronoun or "it"/"this"/"that"
# right before, or a build/file/track-shaped verb right after), not bare
# words -- a bare `\bcould\b` fired on an ordinary time estimate like "review
# could take a while", which names a risk, not a proposal.
#
# `mechanism`, `improvement`, `propose`, `sweep`, and `follow-up` are
# phrase-bound the same way, for the identical reason: an earlier revision
# matched each as a bare word (`\bmechanisms?\b`, `\bimprovements?\b`,
# `\bpropos\w*`, `\bsweep\w*`, `\bfollow-?up\b`) and fired on "the retry
# mechanism in the deploy script failed twice this run", "I already ran a
# sweep of the repo for TODOs and found three, all pre-existing", and "no
# improvement over the previous run" -- a status report, a completed and
# unproductive sweep, and a negated result, none of them proposals.
#
# The `worth ...` alternative below deliberately has NO bare `\ba\b` branch:
# an earlier revision's `worth\s+(?:...|a\b)` matched "isn't worth a redo",
# "worth a shot re-running", and "isn't worth a rewrite" -- every one of
# those a dismissal, not a proposal. `worth an improvement` is its own,
# separately phrase-bound alternative rather than folded into that list.
IDEA_CUE = re.compile(
    r"\b(?:we|you|i|it|this|that)\s+(?:could|should)\b|"
    r"\b(?:could|should)\s+(?:add|build|extend|automate|file|create|propose|sweep|track)\b|"
    r"\bworth\s+(?:building|adding|doing|tracking|filing|an\s+issue)\b|"
    r"\bworth\s+an?\s+improvement\b|"
    r"\bconsider\s+(?:building|adding)\b|"
    r"\ba\s+mechanism\s+(?:to|for)\b|"
    r"\b(?:add(?:ing)?|build(?:ing)?|create(?:ing)?)\b(?:\s+\S+){0,3}\s+mechanisms?\b|"
    r"\bpropos(?:e|ing)\b|"
    r"\ba\s+sweep\s+for\b|"
    r"\b(?:file|open)\s+a\s+follow-?up\b|"
    r"\ba\s+follow-?up\s+(?:issue|item)\b|"
    r"\bit\s+would\s+(?:help|let)\b|"
    r"\badd(?:ing)?\s+a\s+(?:check|hook)\b|"
    r"\bbuild\w*\s+a\s+(?:hook|check)\b|"
    r"\bissue-worthy\b",
    re.I,
)

RX_ALREADY_URL = re.compile(
    r"https?://\S*/(issues|pull|pulls|merge_requests)/\d+", re.I
)

# An idea can land directly as a PR too, not only an issue -- discharge
# either creation path, when it runs AT OR AFTER the flagged message (see
# `_last_create_index()` and its use in `main()`), the same breadth
# `RX_FILE`-style discharges use elsewhere in this corpus, turn-scoped rather
# than session-scoped.
RX_CREATE = re.compile(
    r"create_issue|gh\s+issue\s+create|gh\s+issue\s+comment|"
    r"issues/\d+/comments|mcp__github__create_issue|"
    r"mcp__github__issue_write|add_issue_comment|"
    r"gh\s+pr\s+create|glab\s+(issue|mr)\s+create|"
    r"mcp__github__create_pull_request",
    re.I,
)


def find_unfiled_idea(text):
    """Return the matched marker text (e.g. "FLAG" or "OFFER"), or None if
    no marker proposes an idea, or every one that does is already filed.
    """
    stripped = visible_prose(text) if visible_prose else text
    for m in MARKER.finditer(stripped):
        kind = m.group("kind")
        body = m.group("body") or ""
        if not IDEA_CUE.search(body):
            continue
        window = kind + body
        if RX_ALREADY.search(window) or RX_ALREADY_URL.search(window):
            continue
        return "OFFER" if "OFFER" in kind else "FLAG"
    return None


def _last_create_index(path):
    """Index of the last transcript line carrying a tool_use block matching
    RX_CREATE, or -1 if none. Walked separately from `scan()` because that
    sibling function's own `last_file` tracks its own issue-only RX_FILE,
    not this hook's broader RX_CREATE (which also discharges on a PR-create
    call) -- so its index cannot be reused directly for this comparison.
    """
    last = -1
    i = 0
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                i += 1
                try:
                    m = json.loads(line)
                except Exception:
                    continue
                blocks = (m.get("message") or {}).get("content") or m.get("content") or []
                if not isinstance(blocks, list):
                    continue
                for b in blocks:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    blob = (b.get("name") or "") + " " + json.dumps(b.get("input") or {})
                    if RX_CREATE.search(blob):
                        last = i
    except Exception:
        pass
    return last


def main() -> int:
    if visible_prose is None or scan is None or RX_ALREADY is None:
        return 0  # sibling unavailable; degrade to silence

    try:
        payload = json.load(sys.stdin)
        transcript_path = payload.get("transcript_path") or ""
        _, last_say, text = scan(transcript_path)
    except Exception:
        return 0  # fail open

    if not text:
        return 0

    label = find_unfiled_idea(text)
    if not label:
        return 0

    # Turn-scoped: a create call only discharges when it ran AT OR AFTER the
    # message carrying the FLAG/OFFER, the same `last_file`/`last_say`
    # ordering the sibling hooks use. `>=`, not `>`: a single JSONL line can
    # hold both the FLAG/OFFER text and the filing tool_use in the same
    # content array (one turn, no intervening message), in which case
    # `_last_create_index()` and `scan()`'s `last_say` return the SAME index
    # -- a strict `>` would treat that same-message filing as not yet having
    # happened, which contradicts this comment's own "AT OR AFTER" and the
    # module docstring's DISCHARGE section. An earlier revision searched the
    # whole transcript instead of comparing indices at all, so an unrelated
    # filing anywhere earlier in the session silenced every later, unrelated
    # idea for the rest of that session.
    last_create = _last_create_index(transcript_path)
    if last_create >= last_say:
        return 0

    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    sentinel = os.path.join(tempfile.gettempdir(), f".claude-idea-warn-{key}")
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    article = "an" if label == "OFFER" else "a"
    print(json.dumps({"systemMessage": (
        f"Your reply raises an idea in {article} {label} block with no "
        "issue or PR filed for it in this transcript. Per "
        "shared/workflow/report-mistakes-proactively.md's 'An idea is filed "
        "the same way a mistake is', a chat-only FLAG or OFFER is a "
        "heads-up, not a filing -- file it now (dupe-check, then "
        "`gh issue create` / `mcp__github__issue_write`), or say why this "
        "one is passing speculation rather than a concrete, actionable idea."
    )}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
