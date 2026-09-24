#!/usr/bin/env python3
"""PreToolUse warning: a disposition comment that echoes the verdict it answers.

THE MISTAKE (Morrison-Lab/mln#49, measured 2026-09-24)
-------------------------------------------------------
An agent answered a review round by opening its reply with the reviewer's own
call, reproduced verbatim at line start so the reply could then take the
findings one by one. The comment was a DISPOSITION -- it said what had been
Addressed, Rebutted and Deferred, and named the commit that closed each item.
It stated no verdict of its own.

A line-anchored verdict scanner cannot tell those apart. `classify_verdict()`
in `scripts/check-pr-fully-clean.py` read the echoed line as this author's own
authored verdict, so the author acquired a standing not-clean verdict on a PR
whose reviewer had since returned a clean one. Per ai-config#2274 a later
all-clear from a DIFFERENT reviewer does not supersede a standing not-clean
from another author, so the PR scored not fully clean on a head where every
check was green (14 check runs, 13 success and 1 skipped) and the live review
verdict was clean. Nothing about the PR was wrong; the blocker was the shape of
the reply.

WHY THIS NEEDS A GUARD RATHER THAN CARE
-----------------------------------------
The failure is silent and runs in the blocking direction, which is the
combination a prose rule cannot reach. Nothing turns red, no check reports it,
and the comment reads as scrupulous: quoting the call you are answering is
exactly what good practice looks like from the inside. It is discovered only by
running the fully-clean instrument and reading WHY it refused -- and a session
that has just posted a careful disposition has no reason to suspect its own
comment is the cause.

Two adjacent remedies were measured on the incident and BOTH FAIL, which is why
the guidance in the message is what it is rather than the obvious advice:

  - Blockquoting the echoed line does not help. `classify_verdict` reads a
    blockquoted line exactly as it reads a bare one.
  - A backtick code span does not help either, at one backtick or at two, once
    the span runs across a line break: the per-line citation scan cannot close
    it, so the phrase stays visible to the scan.

The rendering that works is not to reproduce the phrase -- describe the call and
link the review instead. That is the same remedy
`shared/writing/examples-are-scanned.md` gives for a document that trips the
rule it is describing, and the second-order case bit here too: the comment
EXPLAINING the mechanism re-tripped it by quoting the phrase.

WHY IT REUSES check-pr-fully-clean.py's OWN CLASSIFIER
--------------------------------------------------------
`no-handrolled-verdict-parse.py`'s docstring is the standing cautionary tale
for hand-rolling a second verdict detector: a bare phrase search misreads in
both directions. So this hook does not invent one. It imports
`scripts/check-pr-fully-clean.py` by path and calls its own
`classify_verdict()` -- the exact function whose reading caused the incident,
so the guard and the instrument cannot disagree about what a verdict is.
`flag-clean-claim-over-findings.py` imports the same function for the Stop
surface; this is the PreToolUse surface, over a body about to be posted.

FIRE CONDITION (all of)
-------------------------
  1. The call posts or edits a forge comment (Bash `gh pr comment`,
     `gh issue comment`, `gh api .../comments`, or an MCP comment tool).
  2. The body is readable.
  3. `classify_verdict(body)` returns "not-clean".
  4. The body carries no `review-data:` machine payload OF ITS OWN -- a real
     review emits one, so a body with one is a review stating its own verdict
     and is none of this hook's business. Tested against the body with fenced
     and blockquoted lines blanked, because a disposition may quote the
     reviewer's payload back to say what the review concluded, and a quoted
     one is not this author's verdict.
  5. The body carries ARD disposition vocabulary (Addressed / Rebutted /
     Deferred, "addressed in", "closed in", "answered below"). This is the
     discriminator that separates a disposition ANSWERING findings from a
     self-review STATING them -- `shared/workflow/self-review-fallback.md`
     requires the second to carry a real verdict, including a not-clean one,
     and warning on those is how a guard gets switched off. The three MCP
     surfaces a review is SUBMITTED through (`pull_request_review_write`,
     `discussion_comment_write`, `add_comment_to_pending_review`) are
     subtracted from the inherited tool tuple for the same reason: a
     second-round review reproduced a formal REQUEST_CHANGES review warning
     through the first of them. That subtraction is by SURFACE, so it says
     nothing about a review posted as a plain comment: a fallback
     self-review written with `add_issue_comment` still warns, which is a
     residual rather than an oversight and is tracked as ai-config#3938.
  6. That vocabulary is not NEGATED or hedged by a word that GRAMMATICALLY
     REACHES it. "None of the findings are addressed yet" is the honest
     sentence a self-review writes when it has found work and not done it,
     and an earlier draft warned on it -- which is condition 5's own failure
     reached from the other side. Two bounds do this, and the second is what
     an earlier draft lacked: the search runs back only to the last sentence
     end or blank line, and inside that window the nearest hit must attach,
     so a negator broken off by a comma, a semicolon or a conjunction does
     not govern. Without it, "None are deferred; all five are addressed in
     `f120e5a`" went silent -- a second-round review reproduced four such
     bodies. The attach TEST is reused from
     `flag-clean-claim-over-findings.py` (`_ATTACHES`); its separator
     VOCABULARY is not, because that hook's set is tuned to a hedge rather
     than to a negator, and reusing both shipped a measured regression -- a
     third-round review reproduced four honest self-review sentences
     starting to warn. `SCOPE_BREAK_RX` is this hook's own set.

     The hedge vocabulary IS `classify_verdict()`'s own
     (`PREFIX_DISQUALIFY_RX`, imported). The negator set is this file's,
     because the instrument's `NOT_CLEAN_NEGATION_PREFIX` is end-anchored to
     at most two intervening words and this hook's phrases run longer. Where
     either bound is ambiguous the result errs toward disqualifying: a
     missed warning costs one unguarded comment, a false one teaches the
     author to ignore the hook.

It WARNS and never blocks. Whether an echo is the author's own call is a
judgment the lexical condition only approximates, and refusing to post a
disposition would be far worse than posting one that scores oddly.

Fails open on every unexpected shape, per the file-wide contract.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)


def _sibling(name, key):
    """Import a hyphenated sibling module, or None if unavailable."""
    path = os.path.join(HERE, name)
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _instrument():
    """`scripts/check-pr-fully-clean.py` as a module, or None."""
    path = os.path.join(ROOT, "scripts", "check-pr-fully-clean.py")
    try:
        spec = importlib.util.spec_from_file_location(
            "_sib_verdict_echo_instrument", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_rebuttal = _sibling("flag-uncited-rebuttal.py", "_sib_verdict_echo_rebuttal")
_disclosure = _sibling("require-agent-disclosure.py", "_sib_verdict_echo_disclosure")
_clean_claim = _sibling("flag-clean-claim-over-findings.py",
                        "_sib_verdict_echo_clean_claim")
_checker = _instrument()

classify_verdict = getattr(_checker, "classify_verdict", None)

RX_COMMENT_POST = getattr(_rebuttal, "RX_COMMENT_POST", None)
extract_body_text = getattr(_rebuttal, "extract_body_text", None)

_INHERITED_POST_TOOLS = tuple(getattr(_disclosure, "MCP_POST_TOOLS", (
    "mcp__github__add_issue_comment",
    "mcp__github__add_reply_to_pull_request_comment",
)))
# The surfaces a REVIEW is submitted through, subtracted from the inherited
# tuple. `require-agent-disclosure.py` wants them, because every one of them
# posts text that must carry the marker; this hook must not have them, because
# fire condition 5 exists to leave a self-review alone and these are exactly
# how one is filed. A second-round adversarial review reproduced a formal
# REQUEST_CHANGES review, carrying ARD labels and its own not-clean verdict,
# warning through `pull_request_review_write` -- the population the docstring
# promises to exclude, and the direction that gets a guard switched off.
# Subtracted by name rather than re-listing the comment tools, so a comment
# surface added to the sibling still reaches this hook.
# `add_comment_to_pending_review` is step 2 of the three-call sequence
# CLAUDE.md's own MCP table documents for filing a formal review (create the
# pending review, add each comment, submit), so it belongs here by the
# criterion above. A third-round adversarial review found it in the POST
# tuple instead, which contradicted that criterion.
MCP_REVIEW_TOOLS = (
    "mcp__github__pull_request_review_write",
    "mcp__github__discussion_comment_write",
    "mcp__github__add_comment_to_pending_review",
)
# EDITING a comment is this hook's case as much as posting one: the incident's
# first two attempted fixes were edits. The sibling's tuple already carries
# some of these, so the union is deduplicated in order rather than concatenated
# -- an adversarial review found `add_comment_to_pending_review` listed twice.
MCP_POST_TOOLS = tuple(t for t in dict.fromkeys(_INHERITED_POST_TOOLS + (
    "mcp__github__update_issue_comment",
)) if t not in MCP_REVIEW_TOOLS)

# What the subtraction above does NOT reach, stated rather than implied: a
# self-review posted as a PLAIN COMMENT. `self-review-fallback.md` prescribes
# exactly that route ("post it as a PR comment"), and its own text notes that
# `gh pr comment` files an issue comment rather than a review object -- so no
# surface distinguishes it, and only fire conditions 5 and 6 stand between
# such a body and a warning. A review that labels its findings with ARD
# disposition words still warns on that route. Tracked as ai-config#3938;
# the direction is a spurious warning on a real artifact, which is the
# expensive one, so it is a residual rather than an accepted cost.

BASH_TOOL_NAMES = ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")

# A real review emits a `review-data` payload beside its verdict, so a body
# carrying its OWN one is a review rather than a disposition.
#
# Read with the instrument's own extractor rather than a regex here. A
# hand-rolled `review-data\s*:` substring test shipped first and was
# unanchored and case-insensitive, so any MENTION of the marker exempted the
# comment -- and this corpus writes that string constantly, in the README row
# this hook adds, in this very comment, and in both `why` fields. A third-round
# adversarial review reproduced the bypass by appending one sentence naming the
# mechanism. `extract_structured_review` requires the payload to open its own
# line and masks fences, code spans AND indented blocks, so it returns None for
# a mention, for a blockquoted payload and for an indented one, and a dict only
# for a payload the body actually carries.
#
# It also makes the hook's headline claim -- that it imports the instrument
# rather than inventing a second detector -- true of this gate as well as of
# `classify_verdict`. `None` when the instrument cannot be loaded, and the
# gate then exempts nothing, which errs toward warning on this gate alone;
# every other fallback in this file errs the other way, because this one
# cannot fabricate a payload that is not there.
extract_structured_review = getattr(_checker, "extract_structured_review", None)

RX_FENCE = re.compile(r"^ {0,3}(?P<d>`{3,}|~{3,})\s*(?P<info>.*)$")


def authored_text(body):
    """`body` with fenced-code and blockquote lines blanked.

    Line-oriented and deliberately simple, mirroring the same fence rule
    `check-review-execution.sh` uses for its own authored-heading scan: a
    fence closes only on a run of the SAME character, at least as long as
    the opener, with nothing but whitespace after it. Blanking rather than
    deleting keeps every line number and every sentence boundary, so a
    scan over the result cannot join two lines that were never adjacent.
    """
    out = []
    fence = None
    for line in (body or "").split("\n"):
        m = RX_FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group("d")
                out.append("")
                continue
        else:
            if (m and m.group("d")[0] == fence[0]
                    and len(m.group("d")) >= len(fence)
                    and not m.group("info").strip()):
                fence = None
            out.append("")
            continue
        out.append("" if line.lstrip().startswith(">") else line)
    return "\n".join(out)

# ARD disposition vocabulary. The point is a body that ANSWERS findings.
# The ARD bullet label is the commonest form by far and the easiest to miss:
# a disposition writes `**1. Addressed.**` or `**1--2. Rebutted.**`, so the
# numeric label sits INSIDE the bold run, between it and the verb. An earlier
# draft allowed the bold run but not the label, and a review fixture using only
# that form was silently unmatched -- which made a negative case pass for the
# wrong reason.
_ARD_LABEL = r"(?:\d+(?:\s*(?:--|-|to)\s*\d+)?\s*[.):]\s*)?"
RX_DISPOSITION = re.compile(
    r"(?:^|\n)\s{0,4}(?:[-*+]\s+|\d+[.)]\s+|\*{1,2}|_{1,2})?\s*" + _ARD_LABEL +
    # NOT `\b`: an adversarial review found the underscore branch above dead,
    # because `_` is a word character, so `_Addressed_` has no boundary after
    # the final `d`. A non-alphanumeric lookahead admits the closing emphasis
    # while still refusing `Addressedly`.
    r"(?:Addressed|Rebutted|Deferred)(?=[^A-Za-z0-9]|$)"
    r"|\b(?:are|all|each|both|every one|five|four|three|two)\s+"
    r"(?:\w+\s+){0,3}addressed\b"
    r"|\baddressed\s+in\b|\bclosed\s+in\b|\banswered\s+(?:below|point by point)\b",
    re.I,
)

NOTE = (
    "[flag-self-authored-verdict-echo] This {surface} classifies as a NOT-CLEAN "
    "verdict by `scripts/check-pr-fully-clean.py`'s own `classify_verdict()`, "
    "while reading as a disposition that ANSWERS findings rather than a review "
    "stating them (matched: {vocab}).\n\n"
    "If the not-clean phrasing is the reviewer's call quoted back, posting it "
    "gives THIS author a standing not-clean verdict on the PR. Per "
    "ai-config#2274 a later clean verdict from a different reviewer does not "
    "supersede it, so the PR scores not fully clean however green it is, and "
    "nothing reports why.\n\n"
    "Two obvious fixes were measured on Morrison-Lab/mln#49 and BOTH FAIL: "
    "blockquoting the line (`classify_verdict` reads a blockquoted line exactly "
    "as a bare one) and wrapping it in a backtick code span (of one backtick or "
    "two -- once the span crosses a line break the per-line citation scan cannot "
    "close it). Describe the call and link the review instead of reproducing the "
    "phrase.\n\n"
    "If this body IS your own verdict -- a self-review per "
    "`shared/workflow/self-review-fallback.md` -- post it as written; this "
    "warning does not apply."
)


def _split_segments(text):
    """Split a command into shell segments, preferring the sibling's splitter.

    Never a bare `re.split` on newlines: a `--body "..."` literal routinely
    spans lines, so splitting on `\n` cuts the body in half and the posting
    segment stops matching. Measured while writing this hook.
    """
    splitter = getattr(_disclosure, "split_segments", None)
    if callable(splitter):
        try:
            return list(splitter(text))
        except Exception:
            pass
    return [seg for seg in re.split(r"(?<![\\])[;&|]+", text) if seg.strip()]


# The write-then-post heredoc is this corpus's own convention for a
# backtick-heavy body -- CLAUDE.md's PowerShell/backtick rule sends exactly
# this hook's target there -- and at PreToolUse time the file the heredoc
# writes does not exist yet, so a disk read cannot reach it.
#
# `flag-unmeasured-timestamp.py`'s `_extract_heredoc_bodies` was used here
# first and cannot serve: it returns the bodies and discards the redirect
# TARGET, so the only thing to do with several of them is join them. A
# third-round adversarial review reproduced both directions of that. Writing
# the reviewer's report and the disposition in one Bash call and posting the
# disposition went SILENT, because the report's `review-data` payload joined
# the body and exempted it -- and the reviewer's report is the commonest
# neighbour a disposition has. Posting a file written in an earlier call, with
# an unrelated heredoc elsewhere in the command, warned about a body that was
# not being posted.
#
# So the target is captured and the heredoc is tied to the `--body-file` the
# posting segment names. No tie, no body: an untied heredoc reads as
# unreadable rather than as a guess.
RX_BODY_FILE = re.compile(r"--body-file[=\s]+(\S+)")
RX_HEREDOC = re.compile(
    r"([^\n]*)<<-?[ \t]*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?[^\n]*\n"
    r"(.*?)\n[ \t]*\2\b",
    re.DOTALL,
)


def _heredoc_body_for(command, segment):
    """The heredoc body the posting `segment` would send, or None.

    With a `--body-file` target the heredoc must name it, and exactly one
    must. Without one -- a `--body "$(cat <<EOF ...)"` form -- a single
    heredoc in the command is unambiguous and is taken; several are not.
    """
    docs = [(m.group(1), m.group(3)) for m in RX_HEREDOC.finditer(command)]
    if not docs:
        return None
    target = RX_BODY_FILE.search(segment) or RX_BODY_FILE.search(command)
    if target:
        name = os.path.basename(target.group(1).strip("'\"")).strip("'\"")
        if not name:
            return None
        hits = [b for pre, b in docs if name in pre]
        return hits[0] if len(hits) == 1 and hits[0].strip() else None
    if len(docs) == 1 and docs[0][1].strip():
        return docs[0][1]
    return None


def _bash_body(command, cwd):
    """(kind, body) for a Bash command that posts a comment, else (None, None)."""
    if RX_COMMENT_POST is None or extract_body_text is None:
        return None, None
    stripped = command
    strip_hd = getattr(_rebuttal, "strip_heredocs", None)
    if callable(strip_hd):
        try:
            stripped = strip_hd(command)
        except Exception:
            stripped = command
    for segment in _split_segments(stripped):
        if not segment.strip() or not RX_COMMENT_POST.search(segment):
            continue
        body = extract_body_text(segment, cwd)
        if body is None:
            body = extract_body_text(command, cwd)
        if body is None:
            body = _heredoc_body_for(command, segment)
        if body is None:
            return "unreadable", None
        return "body", body
    if RX_COMMENT_POST.search(stripped):
        body = extract_body_text(command, cwd)
        if body is not None:
            return "body", body
        return "unreadable", None
    return None, None


def _post_from_payload(tool_name, tool_input, cwd):
    """(kind, body, surface) for the action this tool call would perform."""
    if tool_name in BASH_TOOL_NAMES:
        command = (tool_input.get("command") or tool_input.get("CommandLine")
                   or tool_input.get("cmd") or tool_input.get("script"))
        if not isinstance(command, str) or not command.strip():
            return None, None, None
        kind, body = _bash_body(command, cwd)
        return kind, body, "comment body"
    if tool_name in MCP_POST_TOOLS:
        body = tool_input.get("body")
        if isinstance(body, str) and body.strip():
            return "body", body, "comment body"
    return None, None, None


# A negated or hedged disposition phrase means the OPPOSITE of answering a
# finding, so it must not fire. An adversarial review reproduced the gap end to
# end: "None of the findings are addressed yet" is an ordinary honest
# self-review, and this hook warned on it -- contradicting its own fire
# condition 5, and warning on a self-review is exactly how a guard gets
# switched off. `flag-clean-claim-over-findings.py` already carries the
# disqualifiers `classify_verdict()` applies to its own bare patterns, so they
# are reused rather than re-derived; the negator set is widened with the
# determiner forms ("none of the findings", "neither") that a disposition scan
# meets and a clean-claim scan does not.
_FALLBACK_PREFIX_DISQUALIFY = re.compile(
    r"(?i)\b(?:should|would|could|might|may|claims?|says?|said|saying|"
    r"seems?|apparently|maybe|perhaps|if|unless|hypothetically)\b"
)
# The clause-ATTACHMENT test, split into the part that transfers and the
# part that does not. `_attaches` is the MECHANISM -- does anything between
# a hit and the phrase break its scope -- and it transfers unchanged.
# `RX_LEADING_SEPARATOR` is a VOCABULARY, chosen for the sibling's verdict
# phrases, and it does not.
#
# Reusing both, which is what `_hedge_attaches` does, shipped a measured
# regression: that set counts `yet`, a bare comma and parentheses as clause
# breaks, and this hook's negators reach their phrase across exactly those
# tokens. "The root cause has not yet been addressed in the fix." warned,
# as did three more ordinary self-review sentences whose only offence was an
# appositive or a parenthetical. `check-purpose-before-reusing.md` names the
# shape: the structure fitted and the purpose did not.
#
# `None` when the sibling cannot be loaded; `_disqualified` then falls back
# to the plain window scan, which errs toward disqualifying.
_ATTACHES = getattr(_clean_claim, "_ATTACHES", None)

# This hook's own separator vocabulary. It keeps every token that genuinely
# opens a new clause and drops the three that do not, here:
#
#   `yet`   -- an adverb inside the negated clause ("has not yet been
#              addressed"), not the coordinating conjunction it is in the
#              sibling's phrases.
#   `(` `)` `[` `]`
#           -- an aside interrupts a clause without ending it.
#   a bare `,`
#           -- an appositive comma does the same. A comma that really does
#              open a clause is followed by a conjunction, which is matched
#              on its own below.
#
# The cost of dropping the bare comma is a comma splice ("Nothing was
# deferred, all five are addressed in `f120e5a`"), which now reads as
# governed and goes quiet. That is a missed warning, the cheap direction
# for a warn-only hook, and the docstring's stated asymmetry.
SCOPE_BREAK_RX = re.compile(
    r"--|[;:|]"
    r"|[\u2013\u2014\u2192\u2026]|\s[-/]\s"
    r"|\n[ \t]*[-*+>#]"
    r"|\b(?:but|and|or|so|however|though|although|while|whereas"
    r"|after|before|until|since|because|once|unless|if|now\s+that)\b",
    re.I,
)

# An aside is removed from the connector BEFORE the scope test, so a
# conjunction inside it cannot break a scope it never left: "None of them
# (three blockers and two nits) are addressed" must stay governed by
# `None`, and its `and` belongs to the parenthetical. The paired-comma form
# is an appositive; it requires two commas and stops at sentence
# punctuation, so a comma splice is not silently swallowed by it.
RX_ASIDE = re.compile(r"\([^()]*\)|\[[^\[\]]*\]|,[^,.;:!?]*,")

PREFIX_DISQUALIFY_RX = (getattr(_clean_claim, "PREFIX_DISQUALIFY_RX", None)
                        or _FALLBACK_PREFIX_DISQUALIFY)
NEGATION_RX = re.compile(
    r"(?i)(?:\bnot\b|\bnever\b|\bno\b|\bnone\b|\bneither\b|\bnor\b|"
    r"\bnothing\b|\bwithout\b|\bun(?:addressed|resolved)\b|n't\b|"
    r"\byet\s+to\b|\bfail(?:s|ed)?\s+to\b)"
)

# The clause the phrase sits in, bounded by a sentence end or a PARAGRAPH
# break. Deliberately not a bare `\n`: this corpus writes semantic line
# breaks, so a negator and the phrase it governs routinely sit on adjacent
# lines of one sentence ("... was never\naddressed in the fix"), and a
# newline boundary cut the negator off -- reproduced against the suite's
# own `NEGATED_PHRASES` fixture. A blank line is a real block boundary and
# still bounds the window.
RX_CLAUSE_START = re.compile(r"[.!?]|\n\s*\n")


def _governs(prose, window_start, match_start, rx):
    """True when the LAST `rx` hit in the window reaches `match_start`.

    The same shape as `flag-clean-claim-over-findings.py`'s
    `_hedge_attaches`, and deliberately not a call to it: that function
    hard-codes the sibling's `RX_LEADING_SEPARATOR`, which is the half that
    does not transfer (see `SCOPE_BREAK_RX` above). The mechanism it
    delegates to, `_attaches`, is reused unchanged.

    Asides are stripped from the connector first, so a conjunction inside a
    parenthetical or an appositive cannot break a scope it never left.

    A missing hit is vacuously "does not apply". A missing `_attaches`
    falls back to True, which DISQUALIFIES -- a missed warning rather than
    a false one.
    """
    window = prose[window_start:match_start]
    last = None
    for last in rx.finditer(window):
        pass
    if last is None:
        return False
    connector = RX_ASIDE.sub(" ", window[last.end():])
    if _ATTACHES is None:
        return not SCOPE_BREAK_RX.search(connector)
    return bool(_ATTACHES(connector, SCOPE_BREAK_RX))


def _disqualified(prose, match_start):
    """True when a negator or hedge GOVERNS the phrase at `match_start`.

    Two bounds, and both are needed. The window start is the last sentence
    end or blank line before the phrase (`RX_CLAUSE_START`). Inside that
    window, `_governs` decides whether the nearest hit actually reaches the
    phrase, or is broken off from it by a semicolon, a dash, a new list
    item or a conjunction.

    The window alone is not enough, and shipping it alone reproduced a
    defect `flag-clean-claim-over-findings.py:759` documents having
    already fixed: a blind "is this word anywhere in the sentence" scan
    silenced "None are deferred; all five are addressed in `f120e5a`",
    because the negator sits in the same SENTENCE but a different CLAUSE.
    A second-round adversarial review reproduced four such bodies going
    silent.

    The attachment test alone is not enough either, and shipping the
    sibling's vocabulary with it reproduced the mirror defect in round
    three: "The root cause has not yet been addressed in the fix." warned,
    because `yet` is a clause separator for the sibling's phrases and an
    adverb in this hook's. `SCOPE_BREAK_RX` is this hook's own set.

    A missing sibling fails toward DISQUALIFYING, which costs a missed
    warning rather than a false one that teaches the author to ignore the
    hook.
    """
    starts = [m.end() for m in RX_CLAUSE_START.finditer(prose, 0, match_start)]
    window_start = starts[-1] if starts else 0
    return bool(_governs(prose, window_start, match_start, NEGATION_RX)
                or _governs(prose, window_start, match_start,
                            PREFIX_DISQUALIFY_RX))


def echoed_verdict(body):
    """The matched disposition phrase when `body` should warn, else None."""
    if not body or classify_verdict is None:
        return None
    try:
        if classify_verdict(body) != "not-clean":
            return None
    except Exception:
        return None
    prose = authored_text(body)
    if extract_structured_review is not None:
        try:
            if extract_structured_review(body) is not None:
                return None
        except Exception:
            pass
    for hit in RX_DISPOSITION.finditer(prose):
        # The bullet branch starts at the preceding newline, so the clause
        # window would otherwise be the LINE ABOVE the bullet. Anchor on the
        # phrase's own first word instead.
        word = re.search(r"[A-Za-z0-9]", hit.group(0))
        start = hit.start() + (word.start() if word else 0)
        if _disqualified(prose, start):
            continue
        return " ".join(hit.group(0).split())
    return None


def _read_payload():
    """(payload, is_dry_run), accepting `--dry-run <command>` for tests."""
    argv = sys.argv[1:]
    is_dry_run = False
    if argv and argv[0] == "--dry-run":
        is_dry_run = True
        argv = argv[1:]
        if argv:
            return {"tool_name": "Bash", "tool_input": {"command": argv[0]}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception:
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    tpath = payload.get("transcript_path") or ""

    try:
        kind, body, surface = _post_from_payload(
            payload.get("tool_name"), tool_input, cwd)
        vocab = echoed_verdict(body) if kind == "body" else None
        if not vocab:
            if is_dry_run:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
            return 0

        if not is_dry_run:
            key = hashlib.sha256(
                (tpath + "|" + (body or "")).encode()).hexdigest()[:16]
            sentinel = os.path.join(
                tempfile.gettempdir(), f".claude-verdict-echo-{key}")
            if os.path.exists(sentinel):
                return 0
            try:
                open(sentinel, "w").close()
            except Exception:
                pass

        context = NOTE.format(surface=surface or "comment body", vocab=vocab)
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            },
        }
        if not os.environ.get("ANTIGRAVITY_AGENT"):
            out["systemMessage"] = (
                "Verdict-echo reminder: this comment classifies as a NOT-CLEAN "
                "verdict from you while reading as a disposition. If that "
                "phrasing is the reviewer's call quoted back, describe it "
                "instead -- blockquoting and code spans do not exempt it."
            )
        print(json.dumps(out))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
