#!/usr/bin/env python3
"""Stop-hook guard: warn on reporting a review "clean" over its own findings.

THE MISTAKE (Morrison-Lab/ai-config#3578)
------------------------------------------
A session read an automated review body for a pull request. The body stated
`**Ready for merge**` under a `### Verdict` heading, and ALSO carried a
`### Findings` section with two entries. The session reported the round to
the user as "Ready for merge" and moved on, reading the verdict line and not
the findings list.

That is backwards. `shared/workflow/fully-clean.md` (and every consuming
repo's own `CLAUDE.md`) says the test is the ABSENCE of findings, not the
presence of a positive verdict line -- a "Ready" verdict above a findings
list loses to the findings. `scripts/check-pr-fully-clean.py` implements
exactly that and scored the same round not-clean.

WHY THIS REUSES check-pr-fully-clean.py'S OWN NOTIONS
-------------------------------------------------------
`no-handrolled-verdict-parse.py`'s whole docstring is the cautionary tale
for hand-rolling a second verdict/findings detector: a bare phrase search
over a review body misreads in BOTH directions (a quoted prior verdict reads
as the real one; a real verdict inside a fenced example reads as a quote).
So this hook does not invent a second "is this body clean" or "does this
body carry findings" heuristic. It imports `scripts/check-pr-fully-clean.py`
by path and calls its own `classify_verdict()` and
`_unresolved_finding_pattern()` directly -- the exact functions that decide
criterion 3/4 for the real instrument, including every hardened edge case
(structured `review-data` payloads, cited/quoted vocabulary, resolved-
findings exemptions, negation). A hazard here is precisely the case
`fully-clean.md`'s "findings win over a clean verdict line" rule describes,
computed by the one place in the corpus that already computes it.

THE MAIN DESIGN RISK, STATED AND HANDLED
-------------------------------------------
This corpus quotes `Ready for merge` and `### Verdict` constantly, including
in the very files that document this rule (this docstring among them). A
hook keyed on the phrase ALONE would fire on every message discussing
reviewing and get switched off. Three independent narrowings, all required
to fire:

  1. A GENUINE hazard body must exist in THIS transcript: a tool_result
     whose ASSOCIATED tool_use command looks like an actual review fetch
     (`remind-ums-on-scrutiny.py`'s own `REVIEW_FETCH` pattern: a GitHub
     `.../pulls/N/reviews`, `.../issues/N/comments`, an MCP
     `get_review_comments`/`get_comments`, or `gh pr view ... --comments`)
     or a previously-saved review body file
     (`no-handrolled-verdict-parse.py`'s `SAVED_BODY` pattern) -- so
     reading this repo's OWN documentation (a `.md` file, a hook's source)
     can never produce a hazard, whatever it quotes.
  2. That body's content, run through the real `classify_verdict()` /
     `_unresolved_finding_pattern()`, must ACTUALLY be a clean-verdict-
     with-live-findings body -- not merely contain the words.
  3. The reply being evaluated must state a clean-claim phrase OUTSIDE any
     fenced code block or inline code span (`scripts/lib/fences.strip_code`)
     -- a backtick-quoted `Ready for merge` while discussing the rule does
     not count.

DISCHARGE
---------
Three outs. The first two are checked in `main()` before the reply is ever
inspected; the third is applied earlier still, during `scan()`, by removing
the hazard from consideration altogether:

  * The reply itself ACKNOWLEDGES findings vocabulary (`finding(s)`, `nit(s)`,
    `unresolved`, `unaddressed`, `non-blocking`, `outstanding`, a Findings-
    family heading, ...). Reporting "Ready for merge, but two findings
    remain" is an honest, qualified report and must never warn.
  * `check-pr-fully-clean.py` has already been run for the hazard's PR (or,
    when no PR number could be attributed to the hazard, ANY invocation in
    this transcript) -- reused directly from `no-handrolled-verdict-parse.py`'s
    `checked_prs()`, the same discharge that hook already uses for the
    identical instrument. Running the real check after reading the body is
    exactly the corrective action this hook exists to prompt, so a session
    that already did it needs no further nudge.

  * A later review fetch of the SAME PR came back genuinely clean, which
    supersedes the earlier hazard. Without this the ordinary loop -- fetch,
    fix, re-fetch clean, report clean -- warned on correct behaviour, and
    that is the corpus's central workflow, so nagging there is what gets a
    guard switched off. Only a CLEAN re-read supersedes: a not-clean one
    leaves the hazard standing, and one whose PR cannot be recovered from
    the command clears nothing.

Only the MOST RECENT hazard in the transcript is consulted, on the reading
that a closing recap characterizes the last review round read, not an
earlier one from deeper in a long session (which the findings-heading
exemption or a manual fix may have already resolved through some other
channel this hook cannot see).

WARN, NEVER BLOCK
-----------------
Authorization and intent are not lexically decidable here (the reply may be
citing the review for a human to read, not asserting it is done), and a
false block on a correct summary is worse than a missed warning. Emits
`systemMessage` only, exactly like `flag-unfiled-issue.py` and
`flag-cop-out-offer.py` -- a `Stop` hook's `reason` is read only alongside
`"decision": "block"`, so a warn-only hook printing `reason` alone reaches
nobody (README, "Writing a warn-only hook: emit `systemMessage`, not
`reason`").

Fails OPEN on any parse or import trouble, and fires at most once per
distinct final message (sentinel keyed by content hash), so it cannot wedge
a session or nag on a babysitting loop that re-reads the same reply.

KNOWN, DELIBERATELY UNFIXED GAP
--------------------------------
The widest spurious-warn surface, listed first because it is the most
likely to fire in ordinary work: when a hazard's PR is known but the
clean-claim sentence names no PR number at all, the correlation guard
cannot exclude it, so an unrelated, un-numbered clean claim later in the
same session warns and cites the hazard's PR. Erring toward warning is
deliberate where either side is unknown, but the three narrower items
below were previously listed as though they were the whole surface, which
understated it (round 8, finding 6).

`_hedge_attaches` reuses `no-stale-pr-status.py`'s clause-separator word
list (`RX_LEADING_SEPARATOR`), which matches a bare `\bso\b` as the
coordinating conjunction ("...that PR #42 is Ready for merge, so it's
ready"). It also matches the identical word inside the idiom "so far"
("...I have verified so far that PR #42 is Ready for merge."), which is
not a clause break at all -- the whole thing is one hedged clause governed
by the earlier "I would say". A third-round adversarial review reproduced
this: that exact sentence should be disqualified as hedged and is not.

Left unfixed rather than chased further, on purpose. The failure direction
is a spurious WARN, not a silent miss -- the safe direction for a warn-only
hook, and the opposite of the two silent-suppression bugs earlier rounds
did fix (a genuinely unhedged claim discharged by an unrelated clause; the
hazard's own PR reference excluded from its correlation window by a
semantic-line-break wrap). Patching this one idiom invites the next one
("as far as", "even so", "insofar as", ...), which is the same
un-winnable word-list chase `detect-review-request.sh`'s own comment
warns about for a different vocabulary problem in this same corpus.

A second, same-category gap in the same direction: `_sentence_start` (the
hedge scan) treats EVERY bare `\n` as a hard break, so a hedge/negation
word sitting on the line immediately BEFORE a genuine mid-sentence wrap is
invisible to it ("I can say PR #42 is not\nReady for merge yet." warns,
though the unwrapped form correctly does not). A fourth-round adversarial
review found this. Left unfixed for the identical reason: the direction is
a spurious warn, and switching the hedge scan to the same wrap-tolerant-
but-list-item-aware regex the PR-correlation fix below now uses would risk
reopening the round-2 "unrelated earlier clause" bug that scan's own
`\n`-always-breaks choice was built to close, for a benefit (one more
narrow wrap case) that costs more caution to verify than it is worth here.

A THIRD gap, found in a fifth review, is in the DANGEROUS direction (a
silent miss, not a spurious warn) and is named explicitly rather than
folded in with the two above. `CORRELATION_SENTENCE_BREAK_RX` breaks when
the line AFTER a wrap carries a list/blockquote/bold-lead marker (so a
marked line containing the clean claim itself is handled), but not when
the marker sits on the line BEFORE the wrap and the claim's own line is
bare continuation text ("**Location:** #99's own file, unrelated\nReady
for merge" does not correlate #99 away). Closing this generally needs a
line-based structural scan (matching each physical line against
`_SECTION_FINDING_ITEM`-shaped patterns independently, the way
check-pr-fully-clean.py itself does over a review body) rather than one
more positional regex alternative. Judged disproportionate to build for a
shape this narrow and this unlike ordinary chat prose -- a bold-labeled
line whose continuation is a semantically unrelated bare sentence -- after
three prior rounds already closed the far more common bullet/blockquote/
bold-lead-on-the-claim's-own-line shapes. If this is ever observed in a
real transcript rather than an adversarial construction, it should be
fixed with that structural scan, not another regex alternative.
"""
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)


def _load(name, path):
    """Import a module from an absolute path, or None if unavailable."""
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# The verdict/findings authority. `classify_verdict` and
# `_unresolved_finding_pattern` are check-pr-fully-clean.py's own,
# already-hardened notions of "this body states CLEAN" and "this body still
# carries an unresolved finding" -- see the module docstring above for why
# these are reused rather than re-derived.
_cpfc = _load(
    "_cpfc_verdict_findings",
    os.path.join(REPO_ROOT, "scripts", "check-pr-fully-clean.py"),
)

# The per-PR "has the real instrument already run" discharge, reused from
# the sibling hook that solved this exact question for the same instrument.
_hrp = _load(
    "_hrp_verdict_findings",
    os.path.join(HERE, "no-handrolled-verdict-parse.py"),
)

# Transcript-record helpers (Claude Code + Antigravity format handling) and
# the review-fetch/review-paste vocabulary, shared with the hook that
# already walks a transcript for the identical "was a review body read"
# question.
_rums = _load(
    "_rums_verdict_findings",
    os.path.join(HERE, "remind-ums-on-scrutiny.py"),
)

# Sentence-boundary detection, reused so the hedge/negation prefix scan
# below never crosses into a PRIOR, unrelated sentence -- a blind character
# window does, and an adversarial review reproduced it: "you should merge
# PR #42 first.\nPR #42: Ready for merge." disqualified the second
# sentence's genuine, unhedged claim because "should" from the FIRST
# sentence fell inside a 50-character window.
_nsp = _load(
    "_nsp_verdict_findings",
    os.path.join(HERE, "no-stale-pr-status.py"),
)

# Code-span/fence stripping, so a backtick-quoted verdict phrase in the
# reply cannot count as the reply STATING it.
strip_code = None
try:
    _lib = os.path.join(REPO_ROOT, "scripts", "lib")
    if _lib not in sys.path:
        sys.path.insert(0, _lib)
    from fences import strip_code  # type: ignore  # noqa: E402
except Exception:
    strip_code = None
if strip_code is None:
    # Reachable only if `scripts/lib/fences.py` -- a checked-in sibling
    # file in this SAME repo -- cannot be imported, which means the
    # checkout itself is broken rather than a normal deployment
    # condition. A KNOWN, DELIBERATELY UNFIXED gap for that case: unlike
    # the real `fences.strip_code` (CommonMark-positional, nested-fence
    # aware), this naive DOTALL regex pairs backtick runs across the
    # whole message regardless of fence length/character, so it can pair
    # an opener from one block with an unrelated closer later on and
    # swallow real prose -- or a genuine clean-claim -- in between.
    # Flagged by a second-round adversarial review; not fixed further
    # because a broken `scripts/lib/fences.py` is itself the primary
    # defect to chase in that scenario, not this fallback's precision.
    _FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.S)
    _CODE_SPAN_RE = re.compile(
        r"(?<!`)(`+)(?!`)(?:[^\n\r]|\r?\n(?![ \t]*\r?\n))*?(?<!`)\1(?!`)"
    )

    def strip_code(text: str) -> str:  # type: ignore[no-redef]
        """Strip fenced code blocks and inline backtick code spans."""
        return _CODE_SPAN_RE.sub(" ", _FENCE_RE.sub(" ", text))

# A tool_use command shaped like an actual review fetch. Reused verbatim
# from remind-ums-on-scrutiny.py so the two hooks cannot disagree about what
# counts as "reading a review".
REVIEW_FETCH = getattr(_rums, "REVIEW_FETCH", None) or re.compile(
    r"get_review_comments|get_reviews|get_comments|"
    r"/pulls/\d+/(comments|reviews)\b|"
    r"/issues/\d+/comments|"
    r"gh\s+pr\s+view\b[^\n]*(--comments|\bcomments\b|\breviews\b)",
    re.I,
)
# The corpus's own marker that a piece of text IS a pasted review body,
# reused from the same sibling.
REVIEW_PASTE = getattr(_rums, "REVIEW_PASTE", None) or re.compile(
    r"\*\*Claude finished|### Verdict", re.I
)
# A body previously saved to a data file and read back, reused from
# no-handrolled-verdict-parse.py's identical clause.
SAVED_BODY = getattr(_hrp, "SAVED_BODY", None) or re.compile(
    r"\S*(?:review|comment|verdict|body)\S*\.(?:json|jsonl|txt)\b", re.I
)

# PR numbers named directly in a Bash command, reused from
# no-handrolled-verdict-parse.py rather than re-deriving the same four
# shapes.
_PR_IN_COMMAND = getattr(_hrp, "PR_IN_COMMAND", None) or []

# PR numbers named in an MCP tool call's JSON input -- the one shape
# `no-handrolled-verdict-parse.py` does not need (it only reads Bash
# commands) but this hook does, since a remote session reads reviews
# through `mcp__github__pull_request_read` rather than `gh`.
PR_NUMBER_JSON = re.compile(
    r'"(?:pull_number|pullNumber|pr_number|prNumber)"\s*:\s*(\d+)', re.I
)

# The verdict-authority's own "this states CLEAN" vocabulary, reused so the
# assistant's OWN claim is measured against the identical phrase list the
# checker uses for a review body -- one definition of "declares clean" in
# the whole corpus, not two.
_FALLBACK_CLEAN = [
    r"\bReady\s+for\s+merge\b",
    r"Verdict:\s*(?:Clean|Approved|Ready)\b",
    r"\bApproved\s+for\s+merge\b",
]
CLEAN_PATTERNS = list(getattr(_cpfc, "VERDICT_CLEAN_PATTERNS", None) or _FALLBACK_CLEAN)
CLEAN_CLAIM_RX = re.compile("|".join(CLEAN_PATTERNS), re.I | re.M)

# check-pr-fully-clean.py never trusts a BARE clean phrase unguarded either:
# `classify_verdict()` requires `_is_marked_pattern()` for its own
# BARE_CLEAN_PATTERNS, and separately disqualifies a match preceded by
# hedging/reported-speech vocabulary (`_PREFIX_DISQUALIFY_RE`, used for its
# resolution-word scan) or a negation (`CLEAN_NEGATION_PREFIX`). This hook
# reuses the SAME disqualifiers rather than a chat-prose-specific
# re-derivation, because the failure they guard against -- "usually says
# something like Ready for merge" reading as an actual claim -- is the
# identical shape, only in conversational prose instead of a review body.
# `_is_marked_pattern` itself is NOT reused: it requires the phrase to sit
# on its own line/heading/bold/bullet, which is how a formatted review
# body states a verdict but not how a chat reply reports one ("Reported to
# the user: Ready for merge." is the incident's own wording, and it is not
# "marked" in that sense) -- adopting it would make the guard silent on the
# exact incident it exists for.
_FALLBACK_PREFIX_DISQUALIFY = re.compile(
    r"(?i)\b(?:should|would|could|might|may|claims?|says?|said|saying|"
    r"seems?|apparently|maybe|perhaps|if|unless|hypothetically)\b"
)
PREFIX_DISQUALIFY_RX = getattr(_cpfc, "_PREFIX_DISQUALIFY_RE", None) or _FALLBACK_PREFIX_DISQUALIFY
_FALLBACK_CLEAN_NEGATION_PREFIX = re.compile(
    r"(?i)\b(?:not|never|no|isn't|aren't|wasn't|cannot|can't)\s+(?:\w+\s+){0,2}$"
)
CLEAN_NEGATION_PREFIX_RX = getattr(_cpfc, "CLEAN_NEGATION_PREFIX", None) or _FALLBACK_CLEAN_NEGATION_PREFIX
# Generic-frequency/example framing ("usually", "typically", "for example")
# is a distinct hedge shape a review body never needs to guard against (a
# reviewer states ITS OWN verdict; it does not generalize about what
# verdicts usually look like) but a chat reply discussing this very rule
# does -- so this one addition is local to this hook rather than borrowed.
#
# NOT `\bthe\s+way\b`: a second-round adversarial review reproduced it
# colliding with the ordinary conversational opener "by the way",
# silently discharging a genuinely-unhedged "By the way, PR #42 is Ready
# for merge." `just how` alone already covers the shape this alternative
# was added for ("that's just how this bot phrases it").
GENERIC_FRAMING_RX = re.compile(
    r"(?i)\b(?:usually|typically|generally|normally|commonly|often|"
    r"for\s+example|e\.g\.|such\s+as|something\s+like|just\s+how)\b"
)
# Two DIFFERENT sentence-boundary regexes, deliberately, mirroring
# no-stale-pr-status.py's own split (its comment above `RX_TRAILING_BREAK`
# explains why one regex cannot serve both directions): a bare `\n` IS a
# boundary when scanning BACKWARD/leading (a list/table row is its own
# independent clause, so a hedge word on an earlier row must not reach
# forward across it) but must NOT be one when scanning FORWARD/trailing,
# because this corpus writes semantic line breaks -- a single sentence
# routinely wraps onto the next line, and a third-round adversarial review
# reproduced `_sentence_end` using the LEADING regex truncating the
# clean-claim's own sentence at a soft wrap, which then excluded the
# hazard PR's own `#N` reference from the PR-correlation window and
# silently discharged a genuine, unacknowledged claim.
# NOT `_nsp.RX_SENTENCE_BREAK` directly, unlike every other reused regex
# in this file. That pattern's punctuation alternative requires
# WHITESPACE (or true string end) after the terminal mark
# (`(?:\s|$)`) to count as a break -- sound for no-stale-pr-status.py's
# own prose, but a sixth review reproduced it going unsound here once
# `_last_break_before` (below) stopped relying on the `endpos`-
# truncation artifact that used to paper over the gap: a period GLUED
# directly onto a following markdown marker with no space ("...this.
# **Ready for merge**") satisfies neither `\s` nor a real `$`, so no
# break registers there at all, and a hedge word from an unrelated
# EARLIER sentence reaches all the way across to a plain, unqualified
# claim. check-pr-fully-clean.py's own `SENTENCE_END` requires no
# separator after the punctuation at all (`r"[.!?]|\n[ \t]*\n"`), which
# is the safe direction for a HEDGE scan specifically: over-breaking only
# narrows the window a hedge word must attach from, which can produce a
# spurious warn at worst, never a silent miss -- the direction that
# matters here. `;` (present in `_nsp`'s class, absent from `_cpfc`'s) and
# a bare `\n` (round 2's own list/row reasoning, which `_cpfc.SENTENCE_END`
# does not carry since it treats only a BLANK line as a break) are both
# kept, so this is a combination of the two authorities rather than a
# straight adoption of either.
SENTENCE_BREAK_RX = re.compile(r"[.!?;]|\n")
TRAILING_SENTENCE_BREAK_RX = getattr(_nsp, "RX_TRAILING_BREAK", None) or re.compile(
    r"[.!?;]|\n[ \t]*\n"
)
# Correlation needs a THIRD variant, not just the two above. Tolerating
# every bare `\n` (the trailing regex, reused as-is for PR correlation
# too) is right for a genuine mid-sentence wrap, but a fourth-round
# adversarial review reproduced it also sweeping in an adjacent, wholly
# UNRELATED bullet: "- Unrelated: #99 was merged separately last night\n-
# Ready for merge" silently discharged a hazard whose own claim carries
# no PR number at all -- the opposite failure direction from everything
# else fixed so far (a silent miss, not a spurious warn), because a
# bullet marker after the newline is exactly the "independent clause"
# signal `SENTENCE_BREAK_RX` already breaks on for the hedge scan, and
# `TRAILING_SENTENCE_BREAK_RX` alone has no way to see it. So: tolerate a
# bare wrap, but still break at a list-item boundary -- and, per a FIFTH
# review, the other line-leading shapes check-pr-fully-clean.py's own
# `_SECTION_FINDING_ITEM` treats as an independent finding item too: a
# blockquote line and a bold-lead line (which also covers `**Location:**`,
# a bold span at line start). The first round only ported the
# bullet/numbered alternative and left the fix half-implemented relative
# to the authority it cited -- a blockquote or bold-lead line carrying an
# unrelated `#N` swept into the window the identical way the bullet case
# did. `re.M` is required here (unlike the bullet alternative) because the
# bold-lead port's negative lookahead (`(?!\s*$)`, "not simply blank to
# the end of THIS line") needs `$` scoped per line, not to the whole
# string -- `_SECTION_FINDING_ITEM` gets this from its own `(?im)` flags.
CORRELATION_SENTENCE_BREAK_RX = re.compile(
    TRAILING_SENTENCE_BREAK_RX.pattern
    + r"|\n[ \t]*(?:[-*+]|\d+[.)])[ \t]"
    # A lookahead, NOT a consuming `\S`: `_last_break_before` filters
    # matches by `.end() <= pos`, so a match that CONSUMES the clean-
    # claim's own first character ends one position too late and is
    # silently dropped exactly when the marker sits immediately before
    # the claim -- the case that matters most. `_SECTION_FINDING_ITEM`'s
    # own `>\s*\S` can get away with consuming it because that pattern is
    # only ever used as a boolean `.search()`, never as a boundary.
    + r"|\n[ \t]*>[ \t]*(?=\S)"
    + r"|\n[ \t]*\*\*(?!\s*$)",
    re.M,
)
# The clause-attachment test: whether nothing between a hedge word and the
# clean-claim match would break the hedge's grammatical scope over it.
# Reused from no-stale-pr-status.py, which built this exact mechanism for
# the identical question about a RETRACTION's scope over the claim it
# negates ("I was wrong, but PR #1689 is fully clean" -- the retraction
# does not reach across the comma+"but"). A second-round adversarial
# review reproduced the sentence-boundary-only guard missing this:
# "You should hold off on #99, but PR #42 is Ready for merge." put
# "should" and the claim in the same SENTENCE (no `.`/`!`/`?`/`\n`
# between them) but in different CLAUSES, and the sentence bound alone
# could not tell them apart.
_ATTACHES = getattr(_nsp, "_attaches", None)
_LEADING_SEPARATOR_RX = getattr(_nsp, "RX_LEADING_SEPARATOR", None)

# The escape valve: the reply itself acknowledges findings vocabulary, so
# reporting "Ready for merge, but two findings remain" never warns. Scoped
# to the WHOLE reply (not just text near the clean-claim match), which is
# the safe direction for a warn-only hook -- a missed warning costs
# nothing further, while narrowing this to "nearby text only" risks the
# opposite failure (an acknowledgment stated in an earlier sentence of the
# same reply no longer discharging a claim it plainly qualifies). The
# documented cost of that breadth is that an ack phrase used for something
# UNRELATED to the hazard elsewhere in a long reply can still discharge --
# see the `before merging` omission below for the one instance of this an
# adversarial review actually reproduced.
_FINDINGS_HEADING_PATTERN = getattr(
    _cpfc, "_FINDINGS_HEADING_PATTERN", r"#+\s*(Actionable\s+|Detailed\s+)?Findings"
)
ACK_RX = re.compile(
    r"\bfindings?\b|\bnits?\b|\bunresolved\b|\bunaddressed\b|"
    r"\bstill\s+needs?\b|\boutstanding\b|\bnon-blocking\b|"
    r"\bissues?\s+(?:remain|found|raised|outstanding)\b|"
    # NOT `\bbefore\s+merging\b`: that phrase is this corpus's own
    # MERGE-ORDER vocabulary (unrelated PRs, "merge #42 before #99"), not
    # a findings acknowledgment, and an adversarial review reproduced it
    # discharging a genuine unacknowledged claim about the hazard PR
    # merely because an earlier, unrelated sentence used it.
    + _FINDINGS_HEADING_PATTERN,
    re.I,
)

# A bare `#N` reference, for correlating a hazard's PR to the reply's own
# PR reference when both are known.
RX_PR_REF = re.compile(r"#(\d{1,6})\b")

_MIN_BODY_LEN = 40


def records(path):
    if _rums is not None:
        yield from _rums.records(path)
        return
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def _blocks(m):
    if _rums is not None:
        return _rums._blocks(m)
    content = (m.get("message") or {}).get("content") or m.get("content")
    blocks = []
    if isinstance(content, str):
        blocks.append({"type": "text", "text": content})
    elif isinstance(content, list):
        for b in content:
            if isinstance(b, dict):
                blocks.append(b)
    return blocks


def _flatten_content(raw, depth=0):
    """Recursively flatten a tool_result content value to text.

    A tool result's `content` is a plain string in some transports and a list of
    content blocks in others -- `no-push-without-self-review.py::_result_text`
    documents the same split. It is also, in some, a single block that was never
    wrapped in a list.

    Every non-string shape must be walked rather than `str()`-ed. `str()` on a
    container yields a Python repr in which each real newline becomes the two
    characters backslash-n, and the imported `classify_verdict` and
    `_unresolved_finding_pattern` both need real newlines to see a heading or a
    marked line. So a `str()`-ed container scores as no verdict and no finding,
    and the hook goes silent on the exact shape it exists for. Round 8 found
    that for the list form; round 9 found the same bug surviving in the
    fallback, for a bare dict and for a doubly-nested sub-block.

    `depth` bounds the recursion so a self-referential structure cannot hang the
    hook. Past the bound the value is dropped rather than `str()`-ed, because a
    dropped value merely misses while a repr can be scanned and misread.
    """
    if depth > 4:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts = [_flatten_content(sub, depth + 1) for sub in raw]
        return "\n".join(p for p in parts if p)
    if isinstance(raw, dict):
        for key in ("text", "content"):
            if key in raw:
                return _flatten_content(raw[key], depth + 1)
        return ""
    return "" if raw is None else str(raw)


def _result_text(block):
    """Return a tool_result block's body as text, whatever shape it arrived in."""
    raw = block.get("content")
    if raw is None:
        raw = block.get("output")
    try:
        return _flatten_content(raw)
    except Exception:
        return ""


def scan(path):
    """Return (hazards, last_text).

    `hazards` is a list of `{"index": i, "pr_refs": set(str)}`, one per
    tool_result in this transcript that is a GENUINE review-body hazard:
    fetched by something REVIEW_FETCH/SAVED_BODY-shaped, carrying the
    corpus's own review-paste marker, and -- per check-pr-fully-clean.py's
    own functions -- stating a clean verdict while still carrying an
    unresolved finding.
    """
    hazards = []
    last_text = ""
    pending = {}  # tool_use_id -> command/blob text

    if _cpfc is None:
        return hazards, last_text

    for i, m in enumerate(records(path)):
        if m.get("isSidechain"):
            continue

        blocks = _blocks(m)
        rec_type = m.get("type") or m.get("role")
        if m.get("source") == "USER_EXPLICIT" or rec_type == "USER_INPUT":
            rec_type = "user"
        elif m.get("source") == "MODEL" or rec_type in {"PLANNER_RESPONSE", "GENERIC"}:
            rec_type = "assistant"

        for b in blocks:
            if not isinstance(b, dict):
                continue
            btype = b.get("type")

            if btype == "tool_use":
                name = b.get("name") or ""
                inp = b.get("input") or {}
                if not isinstance(inp, dict):
                    inp = {}
                blob = f"{name} {json.dumps(inp)}"
                tool_id = b.get("id") or b.get("tool_use_id") or ""
                if tool_id:
                    pending[tool_id] = blob

            elif btype == "tool_result":
                tool_id = b.get("tool_use_id") or b.get("id") or ""
                body_text = _result_text(b)
                if len(body_text) < _MIN_BODY_LEN:
                    continue
                if not REVIEW_PASTE.search(body_text):
                    continue
                cmd_blob = pending.get(tool_id, "")
                if not (REVIEW_FETCH.search(cmd_blob) or SAVED_BODY.search(cmd_blob)):
                    continue
                try:
                    verdict = _cpfc.classify_verdict(body_text)
                    finding = _cpfc._unresolved_finding_pattern(body_text)
                except Exception:
                    continue
                pr_refs = set()
                for rx in _PR_IN_COMMAND:
                    pr_refs.update(rx.findall(cmd_blob))
                pr_refs.update(PR_NUMBER_JSON.findall(cmd_blob))
                if verdict == "clean" and finding:
                    hazards.append({"index": i, "pr_refs": pr_refs})
                elif verdict == "clean":
                    # A later fetch of the same PR that is genuinely clean
                    # SUPERSEDES an earlier hazard for it. Without this the
                    # ordinary loop -- fetch, fix, re-fetch clean, report clean
                    # -- warned on correct behaviour, citing a hazard the
                    # session had already resolved, and only an explicit
                    # check-pr-fully-clean.py run could discharge it (round 8,
                    # finding 3). That is this corpus's central workflow, so
                    # nagging there is the failure that gets a hook switched
                    # off.
                    #
                    # Only a CLEAN re-read supersedes. A not-clean one leaves
                    # the hazard standing, which is the safe direction: the
                    # claim being guarded against is a clean claim.
                    #
                    # An unattributed re-read (no PR reference recoverable from
                    # the command) clears nothing, since it cannot be shown to
                    # be about the hazard's PR.
                    if pr_refs:
                        hazards = [
                            h for h in hazards
                            if not (h["pr_refs"] and h["pr_refs"] & pr_refs)
                        ]
                continue

            elif btype == "text" and rec_type == "assistant":
                txt = b.get("text") or ""
                if txt.strip():
                    last_text = txt

        if rec_type == "assistant" and (
            m.get("source") == "MODEL" or (m.get("type") or "") in {"PLANNER_RESPONSE", "GENERIC"}
        ):
            raw_content = m.get("content")
            if isinstance(raw_content, str) and raw_content.strip():
                last_text = raw_content

    return hazards, last_text


def _discharged_after(path, since_index, pr_refs):
    """True when check-pr-fully-clean.py ran successfully AFTER `since_index`
    for one of `pr_refs` (or, when `pr_refs` is empty, for ANY PR).

    An earlier revision called `no-handrolled-verdict-parse.py`'s
    `checked_prs()` on the WHOLE transcript, which is order-blind: an
    adversarial review reproduced a checker run recorded BEFORE the hazard
    still discharging it, and -- more seriously -- an untargeted hazard
    (no PR number attributable to its fetch) being discharged by a
    checker run for a wholly UNRELATED PR earlier in the same session,
    which silently disarms the guard in the multi-PR sessions this corpus
    runs constantly.

    Rather than re-deriving `checked_prs()`'s own success/failure
    detection (a failed run -- missing `gh`, a bad ref -- must not
    discharge either), this hands it only the records that come AFTER the
    hazard, reusing its exact logic for a question it was not written to
    answer on its own.
    """
    if _hrp is None:
        return False
    try:
        tail = [m for i, m in enumerate(records(path)) if i > since_index]
    except Exception:
        return False
    if not tail:
        return False
    fd, tmp_path = tempfile.mkstemp(suffix=".jsonl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for m in tail:
                fh.write(json.dumps(m) + "\n")
        ran, checked = _hrp.checked_prs(tmp_path)
    except Exception:
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    if pr_refs:
        return bool(pr_refs & checked)
    return ran


def _last_break_before(rx, prose, pos):
    """End offset of the LAST `rx` break match entirely before `pos`, or 0.

    Deliberately searches the WHOLE string rather than
    `rx.finditer(prose, 0, pos)`. A fifth-round adversarial review
    reproduced a real bug from that shortcut: `endpos` makes the regex
    engine treat the string as ENDING at `pos`, so a lookahead assertion
    sitting right at the boundary (the bold-lead break's own `(?!\\s*$)`,
    "not blank to the end of this line") sees a truncated, apparently-
    blank remainder and wrongly concludes it IS blank -- so the break
    silently fails to match exactly when a marker sits immediately before
    `pos`, which is precisely the case that matters most. Scanning
    unrestricted lets every lookahead see real context; filtering by
    `b.end() <= pos` afterward keeps the same "entirely before" contract.
    """
    start = 0
    for b in rx.finditer(prose):
        if b.end() > pos:
            break
        start = b.end()
    return start


def _sentence_start(prose, pos):
    """Start of the sentence containing `pos`, per SENTENCE_BREAK_RX.

    Used for the HEDGE scan only. A bare `\\n` there is deliberately a
    boundary (an unrelated earlier list/table row is its own clause), so
    a hedge word on one row cannot reach forward across it -- see
    `_hedge_attaches`.
    """
    return _last_break_before(SENTENCE_BREAK_RX, prose, pos)


def _wrapped_sentence_start(prose, pos):
    """Start of the sentence containing `pos`, per
    CORRELATION_SENTENCE_BREAK_RX -- tolerating a semantic-line-break wrap
    (a bare `\\n` alone is NOT a boundary) but still breaking at a
    list-item marker after one (a bullet/numbered item IS its own clause).

    Used for PR-CORRELATION only, alongside `_sentence_end` (same regex):
    the two together need to see the clean-claim's WHOLE wrapped
    sentence, since the hazard's own `#N` reference can sit on an
    EARLIER wrapped line of the very sentence stating the claim
    ("Fixes flowed from PR #42's review\\nand also touched on #17 --
    Ready for merge."). `_sentence_start` (the hedge-scan variant, which
    treats EVERY `\\n` as a hard break) would exclude `#42` from that
    window for the identical reason it correctly excludes an unrelated
    hedge word -- the two questions need different regexes, not one
    shared compromise. See the module-level comment above
    `CORRELATION_SENTENCE_BREAK_RX` for why plain wrap-tolerance alone
    (the regex round 3 originally used here) is not enough either.
    """
    return _last_break_before(CORRELATION_SENTENCE_BREAK_RX, prose, pos)


def _last_match_end(rx, text):
    """End offset of the LAST `rx` hit in `text`, or None."""
    end = None
    for m in rx.finditer(text):
        end = m.end()
    return end


def _hedge_attaches(prose, window_start, match_start, rx):
    """True when the LAST `rx` hit in prose[window_start:match_start]
    grammatically reaches the clean-claim match -- nothing between the
    hedge word and the match breaks its scope.

    A blind "is this word anywhere in the sentence" check over-disqualifies:
    a second-round adversarial review reproduced "You should hold off on
    #99, but PR #42 is Ready for merge." going silent, because "should"
    sits in the same SENTENCE as the claim (no `.`/`!`/`?`/`\\n` between
    them) but in a different, comma-plus-"but"-separated CLAUSE. Reusing
    `_attaches`/`RX_LEADING_SEPARATOR` (see the module-level comment above)
    is what tells "should ... Ready for merge" (attaches, same clause,
    genuinely hedged) apart from "should hold off on #99, but ... Ready
    for merge" (does not attach, different clause, a plain assertion).
    A missing hit is vacuously "does not apply"; a missing sibling fails
    toward DISQUALIFYING (the direction that costs a missed warning, not a
    false one).
    """
    end = _last_match_end(rx, prose[window_start:match_start])
    if end is None:
        return False
    if _ATTACHES is None or _LEADING_SEPARATOR_RX is None:
        return True
    connector = prose[window_start + end:match_start]
    return _ATTACHES(connector, _LEADING_SEPARATOR_RX)


def _asserted_clean_claim(prose):
    """First CLEAN_CLAIM_RX match in `prose` that is actually ASSERTED.

    Skips a match preceded, WITHIN THE SAME CLAUSE (never crossing a
    sentence boundary, and never reaching across a comma/conjunction into
    an earlier clause -- see `_hedge_attaches`), by hedging/reported-speech
    vocabulary or a negation -- the exact disqualifiers `classify_verdict()`
    applies to its own bare clean patterns, reused here rather than
    re-derived (see the module-level comment above `PREFIX_DISQUALIFY_RX`).
    An adversarial review reproduced this hook warning on "a reviewer
    usually says something like Ready for merge", which discusses the
    phrase rather than asserting the current round is clean; `says` alone
    already disqualifies it, and `GENERIC_FRAMING_RX` catches the
    "usually"/"for example" family a review body never needs to guard
    against.
    """
    for m in CLEAN_CLAIM_RX.finditer(prose):
        # The SENTENCE bound, with no additional character cap: a
        # third-round adversarial review reproduced a leftover
        # `_PREFIX_WINDOW` character cap silently un-disqualifying a
        # genuinely-governing hedge word merely for sitting more than 50
        # characters before the claim in one long, unbroken clause ("I
        # would say based on everything I have verified so far that PR
        # #42 is Ready for merge."). `_hedge_attaches`'s clause-attachment
        # test is what actually bounds the search correctly now -- a
        # character cap on top of it only reintroduces the failure it was
        # built to fix.
        sent_start = _sentence_start(prose, m.start())
        if _hedge_attaches(prose, sent_start, m.start(), PREFIX_DISQUALIFY_RX):
            continue
        if _hedge_attaches(prose, sent_start, m.start(), GENERIC_FRAMING_RX):
            continue
        # CLEAN_NEGATION_PREFIX_RX is end-anchored to at most a few words
        # before the match (`(?:\w+\s+){0,2}$`), so it self-limits and
        # needs no separate window.
        if CLEAN_NEGATION_PREFIX_RX.search(prose[sent_start:m.start()]):
            continue
        return m
    return None


def _sentence_end(prose, pos):
    """End of the sentence containing `pos`, per
    CORRELATION_SENTENCE_BREAK_RX -- the PR-correlation counterpart to
    `_wrapped_sentence_start` (same regex, forward direction).

    Deliberately NOT `SENTENCE_BREAK_RX` (the hedge-scan/LEADING regex,
    which treats EVERY bare `\\n` as a boundary): this is a forward scan
    for a genuine mid-sentence wrap, not for excluding an unrelated
    earlier clause -- see the module-level comment above
    `CORRELATION_SENTENCE_BREAK_RX`.
    """
    m = CORRELATION_SENTENCE_BREAK_RX.search(prose, pos)
    return m.start() if m else len(prose)


def main() -> int:
    # Both the load AND the lookup live in one try, matching the sibling hooks
    # this borrows from. json.load succeeds for `[1,2,3]`, `42`, `null` and a
    # bare string, each of which is valid JSON and none of which has .get, so
    # splitting them turned a fail-open hook into one that raised (round 8,
    # finding 2).
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path") or ""
    except Exception:
        return 0

    if not path or not os.path.isfile(path):
        return 0

    try:
        hazards, last_text = scan(path)
    except Exception:
        return 0

    if not hazards or not last_text.strip():
        return 0

    hazard = hazards[-1]  # only the MOST RECENT hazard, see module docstring

    try:
        if _discharged_after(path, hazard["index"], hazard["pr_refs"]):
            return 0
    except Exception:
        pass

    try:
        prose = strip_code(last_text)
    except Exception:
        prose = last_text

    if ACK_RX.search(prose):
        return 0

    clean_hit = _asserted_clean_claim(prose)
    if not clean_hit:
        return 0

    # Correlate a known hazard PR against a PR reference NEAR the
    # clean-claim itself -- its own sentence, not the whole reply. When
    # both are known and disjoint, the claim is plausibly about a
    # DIFFERENT, already-clean PR the reply happens to also mention. A
    # second-round adversarial review reproduced a whole-message scope
    # here going silent on "By the way, #99 merged last week. Ready for
    # merge.": #99 is wholly unrelated to the bare "Ready for merge."
    # claim two sentences later, but a whole-message scan still read them
    # as disjoint PR references and suppressed a genuine, unqualified
    # claim about the hazard PR. When either side is unknown, err toward
    # warning (the findings-acknowledgment and checker-discharge outs
    # above already did the precision work).
    if hazard["pr_refs"]:
        # `_wrapped_sentence_start`, NOT `_sentence_start`: a third-round
        # adversarial review reproduced the hedge-scan variant (which
        # treats a bare `\n` as a hard break) excluding the hazard's own
        # `#N` reference when it sat on an earlier, semantic-line-break
        # wrapped line of the SAME sentence as the claim -- see
        # `_wrapped_sentence_start`'s own docstring.
        clean_sent_start = _wrapped_sentence_start(prose, clean_hit.start())
        clean_sent_end = _sentence_end(prose, clean_hit.end())
        reply_prs = set(RX_PR_REF.findall(prose[clean_sent_start:clean_sent_end]))
        if reply_prs and not (reply_prs & hazard["pr_refs"]):
            return 0

    key = hashlib.sha256(last_text.encode()).hexdigest()[:16]
    sentinel = os.path.join(
        tempfile.gettempdir(), f".claude-clean-over-findings-{key}"
    )
    if os.path.exists(sentinel):
        return 0
    try:
        open(sentinel, "w").close()
    except Exception:
        pass

    phrase = clean_hit.group(0).strip()
    which = f" (PR #{', #'.join(sorted(hazard['pr_refs']))})" if hazard["pr_refs"] else ""
    print(json.dumps({"systemMessage": (
        f"Your reply states \"{phrase}\"{which}, but a review body read earlier "
        "in this session states a clean verdict while still carrying an "
        "unresolved finding (per check-pr-fully-clean.py's own "
        "classify_verdict()/_unresolved_finding_pattern()). "
        "fully-clean.md: a \"Ready\" verdict above a findings list loses to "
        "the findings -- the test is the ABSENCE of findings, not the "
        "presence of a positive verdict line.\n\n"
        "Read the findings section itself before reporting the round clean, "
        "and run `python3 scripts/check-pr-fully-clean.py <PR>` -- the real "
        "instrument -- rather than the verdict line alone."
    )}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
