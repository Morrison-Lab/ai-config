#!/usr/bin/env python3
"""Parse Copilot's ``ccr-overview-v2`` review body ``**Findings:**`` line.

``scripts/check-pr-fully-clean.py``'s ``copilot_verdict()`` reads a
Copilot formal review's own inline-finding count so it can decide whether
an affirmative overview heading (``### Approval recommended``) is
genuinely finding-free. The legacy body format states that count as
``Comments generated: N``; the newer ``ccr-overview-v2`` format
([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899)) states it instead as a ``**Findings:**`` line: either the
word ``None``, or one or more ``<n> <severity-badge>`` pairs (an inline
``<picture>`` or ``<img>`` element per severity) that need summing when
several severities appear on the same line, e.g. ``2 <picture ...>
...</picture>`` alone, or ``2 <picture ...></picture> · 1 <picture
...></picture>`` (a middle dot, U+00B7, between them) for a mixed body.

``**Findings:**`` line's per-severity counts are validated against a
small grammar rather than by pattern-matching one bad shape at a time.
Four narrower fixes in a row each still had a gap, which is the tell that
the right fix is a grammar rather than a fifth exclusion
(``shared/coding/regex-backtracking-pitfalls.md``'s "replace nested
quantifiers with linear scans" remedy, generalised from a counting regex
to a small hand-rolled parser): an unbounded ``\\d+`` backtracked
quadratically on a long digit run with no trailing badge; bounding it to
``\\d{1,4}`` alone let it match the LAST 1-4 digits of a longer run
(``12345<picture`` read as ``2345``); a ``(?<!\\d)`` digit boundary still
let a comma or decimal point reset that boundary (``1,000 <picture>``
summed to 0); a lazy-dot ``<picture\\b.*?</picture>`` regex was itself
quadratic on many unclosed openers (1.37s at 7,280 repeats of
``"<picture "``) and, once replaced with a bounded ``str.find``, still let
``str.find`` land on an INNER ``</picture>`` for nested markup
(``1 <picture 2 <picture></picture></picture>``), silently swallowing the
count between the two openers rather than failing closed; and the
regex-based nested-opener guard added for THAT case still missed a digit
sitting INSIDE a malformed tag itself (``0 <picture 5 <img></picture>``
read as 0, not None), because a ``<`` that opens a second tag before the
first one's own ``>`` was never rejected at the tokenisation boundary.

Grammar (WS = an optional run of space/tab; SEP is the middle dot, the
only separator the real ccr-overview-v2 fixtures use)::

    LINE  := WS? ENTRY (WS? SEP WS? ENTRY)* WS?
    ENTRY := COUNT WS? BADGE
    COUNT := 1-4 ASCII digits
    BADGE := `<picture ...>`, then any number of `<source ...>` and AT
              MOST one `<img ...>` (whitespace-only text allowed between
              the tags, nothing else, and no nested `<picture`), then
              `</picture>` -- or a standalone `<img ...>` tag on its own.

Parsing is two linear passes. ``_tokenize_copilot_line`` splits a
Findings-line remainder into TAG (``<...>``) and TEXT tokens in one
left-to-right scan: an unterminated ``<`` (no ``>`` anywhere after it)
fails the whole line closed, and so does a SECOND ``<`` appearing before
the first one's own ``>`` -- that second condition is what makes
``<picture 5 <img></picture>`` and the nested-``<picture>`` case both fail
at tokenisation, since in each one a ``<`` opens before the enclosing
tag's ``>`` arrives, with no dedicated per-shape check needed for either.
The grammar walk in ``_copilot_v2_line_findings_count`` then consumes
that fixed token list once, in order, doing only O(1) work per token (a
regex match against one already-short token's text, or a name comparison
against one already-short tag's text), so the whole function is linear in
``len(rest)`` regardless of how the line is malformed.

``COPILOT_FINDINGS_LINE`` is anchored to the start of a Markdown line --
``(?:^|\\n)`` plus AT MOST 3 leading spaces (never a tab: CommonMark
treats a tab as advancing to the next 4-column stop, so even one leading
tab already forces 4+ effective columns) -- because an unanchored,
unbounded-indent ``\\*\\*Findings:\\*\\*`` matches anywhere in the body:
mid-sentence prose ("Earlier output said **Findings:** None"), a
blockquoted copy of an earlier round's overview (whose line begins with
``>``, which the whitespace-only prefix does not admit), or a 4-space
CommonMark INDENTED CODE BLOCK (four spaces is the threshold; the anchor
alone does not exclude this, hence the ``{0,3}`` bound). Any of these
would otherwise be read as the real v2 zero-count source for an
affirmative review that carries no genuine overview field at all, reading
clean ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding). This matches the real overview
shape in the [Lacaedemon/sparta#1635](https://github.com/Lacaedemon/sparta/pull/1635) fixtures, where ``**Findings:**``
always starts its own line, unindented.

A further structural gap ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding, PR
[ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review): even a correctly-anchored, correctly
unindented ``**Findings:**`` line can still be NON-RENDERED content --
sitting inside an HTML comment (``<!-- ... **Findings:** None ... -->``,
which can itself span multiple lines and start at column zero), or simply
placed somewhere in the body that isn't the actual overview section at
all (a later ``##`` section, or content after the ``<details>`` block
that follows the real overview). Neither an indentation check nor a
citation mask catches either shape: ``strip_cited_finding_vocab_with_mask``
(the caller's own masking pass) only recognises code spans, fenced code
blocks, and quoted text as citations -- HTML comments and plain later
sections are outside its scope entirely.

The fix is structural rather than a further pattern exclusion, per the
same reasoning that already replaced this module's counting logic with a
grammar: restrict the SEARCH REGION to the actual overview block, and
independently reject any match that lands inside an HTML comment even
within that region.

``_copilot_overview_block_spans`` locates every such region (PR
[ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, second round on this same function: a
bare marker with no heading, or a heading found much later past an
unrelated section, both used to open a "trusted" block on their own).
The block START is now ONE combined pattern requiring the marker AND the
``## Copilot review overview`` heading immediately after it, with only
blank/whitespace-only lines allowed between them -- not two independently
optional signals. The marker is also now line-anchored, like every
sibling boundary pattern in this module, so it cannot open a block from
inside a blockquote or mid-sentence prose quoting an earlier round's
marker. There is no heading-only fallback: every real ccr-overview-v2
fixture (the transcribed [Lacaedemon/sparta#1635](https://github.com/Lacaedemon/sparta/pull/1635) bodies, and every
constructed fixture in scripts/test_check_pr_fully_clean.py) carries the
marker, so a body with the heading but no marker is not a shape any real
fixture needs to support, and treating it as a block start would revive
exactly the "one signal alone is enough" gap this round closes. A body
with no marker+heading pair at all yields no block, meaning no v2
verdict -- the same as before.

Several marker+heading pairs can appear in one body (an earlier round's
overview quoted ahead of the current one, or vice versa), so
``_copilot_overview_block_spans`` returns every one found, each with its
own end -- the first ``<details`` tag or next ``##`` heading following
THAT pair, not a single body-wide end. ``_copilot_v2_findings_count``
then searches every block's own span, and the existing any-nonzero-wins
combine rule (already scanning every uncited ``**Findings:**`` line
within one block) needs no separate cross-block rule: it already applies
across the concatenated set of candidate lines from every block, exactly
as if they had all been in a single region, so a nonzero finding in a
LATER block still overrides an earlier block's zero, and vice versa.

``_find_html_comment_spans`` locates every ``<!--...-->`` span in the
body with a linear ``str.find``-based scan (not a lazy-dot regex, which
would reintroduce the exact "every unclosed opener rescans to the end"
quadratic trap this module's tokenizer already avoids for tag matching --
an unclosed ``<!--`` is treated as extending to the end of the string,
which is also the correct fail-closed direction: content after a comment
that never closes should not be trusted as real), computed once up to
the FURTHEST block's end (not once per block, and not over the whole
body) so its cost stays bounded by the total blocks' own extent rather
than compounding per block or tracking unrelated trailing content. A
``**Findings:**`` match inside some block's span and outside every
comment span is read as that block's field. A live match OUTSIDE every
block (not cited, not in a comment, not in a ``<details>`` region) is
an orphan: typically a block whose own marker was excluded as cited
while its content was not. A nonzero orphan is decisive, an
unparseable one gives no verdict, and a zero one is ignored.
"""
from __future__ import annotations

import bisect
import re
from typing import Callable, List, Optional, Tuple

# A-Z -> a-z only. Length-preserving by construction, unlike `str.lower()`
# (see `_find_details_regions`).
_ASCII_LOWER = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"
)

COPILOT_FINDINGS_LINE = re.compile(
    r"(?:^|\n)[ ]{0,3}\*\*Findings:\*\*[ \t]*(?P<rest>[^\n\r]*)", re.IGNORECASE
)


def _findings_line_cite_start(m: "re.Match[str]") -> int:
    """The position to check citedness FROM, for a `COPILOT_FINDINGS_LINE`
    match -- the line's own first character, not `m.start()` ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899)
    review finding).

    The pattern's own leading `(?:^|\\n)` consumes the PRECEDING
    line-ending character whenever the match isn't at the very start of
    the string, so `m.start()` then points at that newline rather than
    at the line's own first character. The citation mask this module's
    caller builds (`strip_cited_finding_vocab_with_mask`) never marks a
    newline offset as cited -- by that mask's own design, every newline
    position is unconditionally 0 (see `_copilot_overview_block_spans`'s
    docstring, "the mask's newline positions are unconditionally 0 in
    every caller") -- so `match_is_cited(cited, m.start(), m.end())`
    always finds an uncited newline inside the checked range and reports
    the WHOLE match as uncited, even when every real character of the
    line itself sits inside a double-backtick code span: a whole
    ` ``**Findings:** None`` ` line still read as a live, uncited zero.
    Every other caller in this module checks a piece that does not cross
    a line break (the marker, the heading, a single `**Findings:**` line
    with no leading anchor consumed), which is why this gap is specific
    to this one pattern.

    When the match starts with the consumed `\\n` (`m.group(0)[:1] ==
    "\\n"`), the content begins one character later; at the very start
    of the string the zero-width `^` branch matched instead, consuming
    nothing, so `m.start()` already IS the line's own first character
    and needs no adjustment.
    """
    return m.start() + 1 if m.group(0)[:1] == "\n" else m.start()


# Locate every actual Copilot v2 overview block rather than searching the
# whole body -- see the module docstring's last section for why. All
# patterns are simple bounded literals/alternations with no lazy-dot or
# self-ambiguous repetition, so each `.search()`/`.finditer()` call is a
# single linear scan (shared/coding/regex-backtracking-pitfalls.md).
#
# The marker and the heading are ONE combined pattern, not two
# independently optional signals (PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review,
# second round): line-anchored like every sibling boundary here (so a
# blockquoted or mid-sentence quote of an earlier round's marker cannot
# open a block), and requiring the heading immediately after the marker
# with only blank/whitespace-only lines between -- `(?:[ \t]*\r?\n)+`
# consumes the marker's own line ending plus any number of blank lines,
# and stops (with no backtracking needed) the instant it reaches a
# non-blank line, so a real heading right after matches in one pass and
# a marker with no adjacent heading, or one found only much later past
# an unrelated section, matches nothing at all. `\r?\n`, not a bare
# `\n` ([ai-config#3917](https://github.com/Morrison-Lab/ai-config/issues/3917) item 2, PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, third
# round): a CRLF body's marker line ends in `\r\n`, and the bare `\n`
# form cannot consume the `\r` (it is neither `[ \t]` nor `\n` itself),
# so the bridge failed to match at all and the whole body read as
# carrying no v2 overview. That was the fail-closed direction (no block
# found means no verdict, never a wrong clean), and GitHub's API
# normalizes bodies to LF before this ever runs, so it was consistency
# rather than exposure -- but every other line-anchor in this module
# already tolerates a `\r` for free (a preceding `\r\n` still contains
# the literal `\n` those patterns look for), and this is the one place
# that did not.
#
# The heading is anchored at ITS end too -- `[ \t]*(?=\r?\n|$)`, not a
# trailing `\b` ([ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, third round): a word
# boundary only asserts a transition between a word and non-word
# character, which the space before "quoted" in "## Copilot review
# overview quoted" already satisfies, so that suffixed line opened a
# trusted block too. The lookahead instead requires nothing but
# whitespace between the heading text and the end of its line (or the
# end of the string), so any real trailing content -- a word, a colon
# and more heading text, anything -- fails the match outright.
# The marker and heading are each their own capturing group (PR
# [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, tenth round) so the block-start scan can
# check EACH one's own citedness against the caller's `cited` mask,
# separately from the other -- checking the WHOLE combined match would
# never fire, since the mask's newline positions are unconditionally 0
# (every line-splitting/rejoining pass in check-pr-fully-clean.py's
# strip_cited_finding_vocab_with_mask leaves the separator `\n` at mask
# 0), and this pattern's own marker-to-heading bridge always crosses at
# least one newline. A single-line citation of EITHER piece alone (a
# genuine two-backtick code span wrapping just `<!-- ccr-overview-v2 -->`
# on its own line, or just `## Copilot review overview` on its own line)
# is real and constructible, and is exactly the shape a body describing
# the ccr-overview-v2 format in prose would use.
_COPILOT_OVERVIEW_START = re.compile(
    r"(?:^|\n)[ ]{0,3}(<!--[ \t]*ccr-overview-v2[ \t]*-->)"
    r"(?:[ \t]*\r?\n)+"
    r"[ ]{0,3}(##[ \t]+Copilot review overview[ \t]*)(?=\r?\n|$)",
    re.IGNORECASE,
)
# A lookahead for a real tag-name delimiter, not a trailing `\b` (PR
# [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, ninth round): `\b` only asserts a
# transition between a word and non-word character, which "details:evil"
# and "details-evil" both satisfy at the character right after "details"
# (":" and "-" are equally non-word), so either malformed shape opened a
# real `<details>` region and could hide a genuine v2 block inside it.
# `_copilot_tag_name` already draws this same line for a BADGE's own tag
# name (a real opening tag's name is always followed by whitespace, `/`,
# or `>`); this mirrors that same delimiter set here, for consistency, so
# `<details:evil>`/`<details-evil>` are rejected outright while
# `<details>`, `<details open>`, and `<details/>` still match.
_COPILOT_DETAILS_OPEN = re.compile(
    r"(?:^|\n)[ ]{0,3}<details(?=[ \t/>])", re.IGNORECASE
)
_COPILOT_NEXT_HEADING = re.compile(r"(?:^|\n)[ ]{0,3}##[ \t]")
# `[0-9]`, not `\d`: Python's `\d` matches every Unicode `Nd`-category
# digit, not just ASCII -- a full-width digit (U+FF15, "5") would
# otherwise satisfy "1-4 ASCII digits" and parse as a real count,
# contradicting the grammar's own stated ASCII-only rule.
_COPILOT_FIRST_COUNT = re.compile(r"^[ \t]*([0-9]{1,4})[ \t]*$")
_COPILOT_SEP_COUNT = re.compile(r"^[ \t]*·[ \t]*([0-9]{1,4})[ \t]*$")
_COPILOT_WS_ONLY = re.compile(r"^[ \t]*$")
# Anchored at both ends (`$`, not `\b`): a bare `re.match(r"[ \t]*None\b", ...)`
# only checked the START of the line, so `**Findings:** None but actually 5
# <picture></picture>` satisfied it and read as zero -- the word boundary
# after "None" is satisfied by the following space regardless of what comes
# after it ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding). Requiring the whole line to be
# `None` (plus optional surrounding whitespace) means any trailing content
# falls through to the grammar parser instead, which fails it closed.
_COPILOT_NONE_LINE = re.compile(r"^[ \t]*None[ \t]*$", re.IGNORECASE)


def _copilot_overview_block_spans(
    scan: str,
    cited: bytearray,
    match_is_cited: Callable[[bytearray, int, int], bool],
) -> List[Tuple[int, int]]:
    """Return the (start, end) character span of every Copilot v2 overview
    block in `scan` -- normally zero or one, but a body can legitimately
    quote an earlier round's overview ahead of (or after) its own current
    one, each carrying a genuine marker+heading pair.

    See the module docstring's last section for the block boundary rule.
    Each block starts where `_COPILOT_OVERVIEW_START` matches (the marker
    immediately followed by its heading, with only blank lines between --
    a bare marker with no heading, or a heading found later past some
    other content, matches nothing and opens no block) and ends
    immediately before the first `<details` tag or next `##` heading that
    follows THAT block's own start, not a single body-wide end. An empty
    list means this body carries no v2 overview at all.

    A marker+heading pair whose own START falls inside an already-open
    `<details>...</details>` region is excluded ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review
    finding, PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, fourth round): such a
    region is exactly what a re-review's "Resolved since last review" or
    "Open (N)" listing quotes, and a PRIOR round's overview -- marker,
    heading, and its own `**Findings:**` line all included -- is a
    completely genuine sequence by every OTHER check here, so without
    this it would be trusted as a current block. A genuinely later block
    that starts AFTER a `<details>` region has already closed still
    counts, since its start position falls outside every region.

    Every boundary search this function drives -- the marker+heading
    START itself, and the `<details`/`##` END search -- is ALSO checked
    against `_find_html_comment_spans`, symmetrically with the details
    -region search below (PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, seventh
    round, closing a sweep the sixth round's fix prompted): a marker+
    heading pair swallowed by an EARLIER unclosed `<!--` (which
    `_find_html_comment_spans` already treats as extending to the end of
    the string, the same fail-closed convention as everywhere else in
    this module) was still trusted as real; and a fake, line-anchored
    `<details>` or `##` heading hidden inside a comment BETWEEN a genuine
    marker+heading and its own real `**Findings:**` line truncated the
    block's END before ever reaching that line, silently losing it
    (measured: an affirmative body with a real `**Findings:** None` line
    read as no verdict instead of clean, because the truncated block
    never contained the line at all). `_search_outside_comments` is the
    shared helper for the second case: it re-searches past any candidate
    match that itself falls inside a comment, the same forward-only
    cursor discipline `_find_html_comment_spans`/`_find_details_regions`
    already use, so this stays linear regardless of how many fake
    candidates are skipped.

    Comment spans are computed ONCE here and threaded into
    `_find_details_regions` as a parameter, rather than recomputed a
    second time inside it -- `_position_in_spans` is the same
    bisect-backed containment check both the comment and the
    details-region exclusions use, so sharing the one already-sorted list
    keeps every lookup O(log k) without paying for
    `_find_html_comment_spans`'s own O(n) scan twice.

    Each block's END search is bounded at the NEXT valid block's own
    START (PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, eighth round): a body with
    many marker+heading blocks and no `<details` anywhere ran the
    `<details`/`##` END search all the way to end-of-string for EVERY
    block, since `_COPILOT_DETAILS_OPEN.search()` never matches and a
    regex search that fails to match still costs O(remaining length) to
    conclude that -- making the total cost O(blocks x body-length), not
    O(body-length) (measured before this fix, at a fixed 262,144
    characters: 10 blocks 0.0002s, 100 blocks 0.0076s, 500 blocks
    0.1874s, ~2,570 blocks 4.68s, clearly super-linear). Since blocks
    come from one ordered `finditer` pass, the valid starts are collected
    FIRST, in order, and each block's END search is then capped at the
    position where the next valid block begins -- nothing past that
    point can matter to the CURRENT block's own end, because a search
    that finds nothing within `[search_from, next_start)` still has the
    next block's own start as a safe fallback end (the next block cannot
    have started without leaving this one behind). That makes each
    region of `scan` scanned by at most a small constant number of
    bounded searches (one per pattern, from the previous block's end to
    the next block's start), so the total cost across every block is
    O(body-length) again, regardless of block count.

    The marker's own span (`start_m.span(1)`) and the heading's own span
    (`start_m.span(2)`) are ALSO checked against the caller's `cited`
    mask, independently of each other (PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review,
    tenth round): a body describing the ccr-overview-v2 format in prose
    can genuinely cite one piece as a single-line two-backtick code span
    (` ``<!-- ccr-overview-v2 --> `` ` or ` ``## Copilot review
    overview`` ` on its own line), which `strip_cited_finding_vocab_with_
    mask` leaves in place -- its inline-code-stripping pass only removes
    the SINGLE backtick pairs, so the marker/heading text itself survives
    in `scan` unmodified and still matches `_COPILOT_OVERVIEW_START`,
    with the caller's mask correctly marking that text cited. Without
    this check, an affirmative heading elsewhere in the body plus a real,
    uncited `**Findings:** None` line following the cited pair read as a
    clean v2 block, even though the pair citing the format is not a live
    overview at all. `match_is_cited` on the WHOLE combined match would
    never fire here (or anywhere): the mask's newline positions are
    unconditionally 0 in every caller, and the marker-to-heading bridge
    always crosses at least one -- checking each piece separately is what
    makes the check reachable at all, not merely a stricter version of a
    whole-match check. Its reach is exactly the caller's mask: a code
    span whose backtick delimiters sit on their own lines is not marked
    cited by `_citation_mask` today, so a marker quoted that way still
    opens a block ([ai-config#3956](https://github.com/Morrison-Lab/ai-config/issues/3956)).
    """
    comment_spans = _find_html_comment_spans(scan)
    comment_span_starts = [s for s, _ in comment_spans]
    details_regions = _find_details_regions(scan, comment_spans, comment_span_starts)
    details_region_starts = [s for s, _ in details_regions]
    valid_starts: List[Tuple[int, int]] = []
    for start_m in _COPILOT_OVERVIEW_START.finditer(scan):
        start = start_m.start()
        # strict=True: the marker text is itself a complete HTML comment,
        # so a non-strict check would always match a genuine marker's own
        # self-comment and exclude every real block. See
        # _position_in_spans' own docstring for why this call needs it
        # and no other caller does.
        if _position_in_spans(
            start, comment_span_starts, comment_spans, strict=True
        ):
            continue
        if _position_in_spans(start, details_region_starts, details_regions):
            continue
        if match_is_cited(cited, *start_m.span(1)) or match_is_cited(
            cited, *start_m.span(2)
        ):
            continue
        valid_starts.append((start, start_m.end()))
    scan_len = len(scan)
    spans: List[Tuple[int, int]] = []
    for i, (start, search_from) in enumerate(valid_starts):
        limit = valid_starts[i + 1][0] if i + 1 < len(valid_starts) else scan_len
        end = limit
        for pattern in (_COPILOT_DETAILS_OPEN, _COPILOT_NEXT_HEADING):
            m = _search_outside_comments(
                pattern,
                scan,
                search_from,
                comment_spans,
                comment_span_starts,
                endpos=limit,
            )
            if m is not None and m.start() < end:
                end = m.start()
        spans.append((start, end))
    return spans


def _find_html_comment_spans(text: str) -> List[Tuple[int, int]]:
    """Find every `<!--...-->` span in `text`, or one that opens but never
    closes (treated as extending to the end of the string -- the
    fail-closed direction: content after an unterminated comment should
    not be trusted as real, matching this module's other unterminated-tag
    handling).

    One linear pass via `str.find`, not a lazy-dot regex: `<!--.*?-->`
    under DOTALL would re-scan to the end of the string at EVERY unclosed
    `<!--`, the same quadratic trap `_tokenize_copilot_line` already
    avoids for tag matching. `pos` only ever advances past a span already
    found, so no character is examined by more than one comment's scan.
    """
    spans: List[Tuple[int, int]] = []
    pos = 0
    n = len(text)
    while True:
        open_pos = text.find("<!--", pos)
        if open_pos == -1:
            break
        close_pos = text.find("-->", open_pos + 4)
        if close_pos == -1:
            spans.append((open_pos, n))
            break
        spans.append((open_pos, close_pos + 3))
        pos = close_pos + 3
    return spans


def _search_outside_comments(
    pattern: "re.Pattern[str]",
    scan: str,
    pos: int,
    comment_spans: List[Tuple[int, int]],
    comment_span_starts: List[int],
    endpos: Optional[int] = None,
) -> Optional["re.Match[str]"]:
    """Return the first match of `pattern` in `scan[:endpos]` at or after
    `pos` whose own start does NOT fall inside any span in
    `comment_spans`, or None if every match from `pos` onward (within
    that bound) is inside one (PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review,
    seventh round).

    `endpos` defaults to `len(scan)` (the whole rest of the string, via
    `re.Pattern.search`'s own `endpos` parameter) and is otherwise passed
    straight through to it -- the caller does the bounding, this function
    only threads the bound to every retry so a rejected match's own
    `endpos` doesn't silently widen back out.

    Used by `_copilot_overview_block_spans` for its `<details`/`##`
    block-end search ONLY -- that function's marker+heading START check
    uses `_position_in_spans(..., strict=True)` directly instead (PR
    [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, eighth round, correcting an earlier
    version of this docstring that claimed both call sites shared this
    helper): the marker-start check needs the strict variant documented
    on `_position_in_spans` itself, for the marker's own self-comment
    self-match, and `strict` has no meaning for a moving `pattern.search`
    match the way it does for a single fixed position, so this helper
    was never a fit for that call site to begin with.

    Each rejected candidate advances `pos` to that match's own end before
    retrying, so -- exactly like `_find_html_comment_spans` and
    `_find_details_regions` -- the cursor only ever moves forward and the
    total work across every call from one starting `pos` is O(endpos -
    pos), regardless of how many comment-hidden candidates are skipped
    along the way.
    """
    while True:
        m = pattern.search(scan, pos, endpos if endpos is not None else len(scan))
        if m is None:
            return None
        if not _position_in_spans(m.start(), comment_span_starts, comment_spans):
            return m
        pos = m.end()


def _find_details_regions(
    scan: str,
    comment_spans: List[Tuple[int, int]],
    comment_span_starts: List[int],
) -> List[Tuple[int, int]]:
    """Find every `<details>...</details>` region in `scan`, one linear
    pass, so a marker+heading pair sitting inside an already-open
    `<details>` section can be excluded from
    `_copilot_overview_block_spans` ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding, PR
    [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, fourth round): without this, a block
    quoted inside a PRIOR round's `<details>` "Resolved since last
    review" listing -- itself containing a full marker+heading+Findings
    sequence, since that is exactly what a re-review quotes -- was
    trusted as a genuine, current block.

    The opening `<details` is located with the same line-anchored
    `_COPILOT_DETAILS_OPEN` pattern the block-end search already uses, so
    "what counts as a details opening" stays consistent between the two
    call sites; the closing `</details>` is then found via a linear
    `str.find` sweep (not line-anchored -- matching
    `_find_html_comment_spans`'s own convention for its closing marker).
    An opening with no closing `</details>` anywhere after it is treated
    as extending to the end of the string -- the same fail-closed
    direction `_find_html_comment_spans` already takes for an
    unterminated comment.

    NESTED `<details>` are tracked by DEPTH, not skipped (PR
    [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, eleventh round -- this function's own
    earlier version closed an OUTER opening at the FIRST `</details>`
    found after it, which for a nested body is the INNER details' own
    closer, not the outer's; everything between that inner closer and
    the outer's TRUE closer then read as outside any region at all, so a
    marker+heading pair placed there -- still nested inside the outer
    `<details>`, exactly what a re-review's own listing quotes -- was
    wrongly treated as a genuine top-level block, contradicting this
    docstring's own stated purpose). Every opening and every closing tag
    is collected first (each list already in left-to-right order, since
    both come from a single forward-only scan), then merged by a
    two-pointer walk that advances whichever list's next candidate sits
    first: an opening at depth 0 starts a NEW region and increments
    depth; a closing at depth 0 has no opener in effect and is ignored;
    any other closing decrements depth, and CLOSES the current region
    only when depth returns to 0. `region_start` therefore survives
    across any number of nested opens/closes in between, and a nested
    opening never starts a region of its own -- it is absorbed into its
    enclosing one, matching this docstring's stated purpose (a nested
    `<details>`, which real Copilot markup does not produce but this
    does not assume, contributes no separate region). If depth is still
    above 0 once every event is consumed, the outermost still-open
    chain's own `region_start` is used for one final region extending to
    the end of the string -- the same fail-closed direction as an
    unterminated single `<details>`.

    Both list-building passes and the merge walk are each a single
    forward-only scan (`finditer`'s own cursor, `str.find`'s own
    advancing `pos`, and the two-pointer walk's own advancing indices
    never revisit a position already consumed), so the whole function
    stays linear in `len(scan)` regardless of nesting depth or how many
    `<details>` sections the body contains -- unlike a merge via
    `sorted()`, which would cost O(m log m) in the event count.

    An opening whose own START falls inside an HTML comment is skipped
    entirely, not paired with whatever `</details>` follows (PR
    [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, fifth round): a fake
    `<!--\n<details>\n-->` opener would otherwise pair with the NEXT real
    `</details>` -- however far away -- producing a region that engulfs
    everything between them, including a genuine marker+heading+Findings
    block. That reads as no block found at all (this function's own
    caller then excludes the real block's start, which falls inside the
    artificially-huge region), which is the fail-closed direction --
    `copilot_verdict` returns no verdict rather than a wrong clean -- but
    it is asymmetric with the containment check this same round already
    added for a marker+heading pair, and it silently drops a genuine
    not-clean finding down to no-verdict.

    The CLOSING `</details>` search carries the same guard, symmetrically
    (PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, sixth round): a real
    `<details>` containing a commented-out `<!-- </details> -->` before
    its own genuine closer would otherwise have `str.find` land on that
    fake closer, truncating the region early -- content still inside the
    real `<details>` (between the fake closer and the true one) would
    then read as OUTSIDE any details region, and a marker+heading pair
    there would be wrongly treated as a genuine top-level block rather
    than one still nested inside the details section. This could not by
    itself produce a false CLEAN (the truncated-in content is exactly
    what a re-review quotes, so at worst it adds a spurious candidate
    block whose own combine-rule participation still requires an
    affirmative reading to matter), but it is the same asymmetry as the
    opener fix above and is closed the same way: `close_pos` now loops
    forward past any candidate `</details>` that itself falls inside a
    comment span, rather than accepting the first occurrence
    unconditionally.

    `comment_spans`/`comment_span_starts` are precomputed by the caller
    (PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, seventh round) rather than
    recomputed here with a second `_find_html_comment_spans(scan)` call:
    `_copilot_overview_block_spans` needs the same list for its own
    marker-start and block-end checks, and one shared O(n) scan is
    strictly better than two.
    """
    n = len(scan)
    close_tag = "</details>"
    close_len = len(close_tag)

    opens: List[int] = []
    for m in _COPILOT_DETAILS_OPEN.finditer(scan):
        if _position_in_spans(m.start(), comment_span_starts, comment_spans):
            continue
        opens.append(m.start())

    # The closer search must be case-insensitive too, matching
    # `_COPILOT_DETAILS_OPEN`'s own `re.IGNORECASE` ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review
    # finding): a plain `scan.find(close_tag, ...)` never matches
    # `</DETAILS>`, so an opener genuinely closed that way found NO closer
    # at all and fell to the unterminated-details fail-closed path below
    # -- extending the region all the way to the end of the string and
    # wrongly absorbing every marker+heading pair AND every orphan
    # `**Findings:**` line after it (a real nonzero orphan finding
    # swallowed this way reads as no finding at all, the unsafe
    # direction: see `_copilot_v2_findings_count`'s orphan scan).
    #
    # The closer is matched case-insensitively against an ASCII-only
    # lowercased copy of `scan`, computed ONCE and reused for every search
    # in this loop. `str.translate` with an A-Z -> a-z table maps each
    # character to exactly one character, so the copy always has the same
    # length and every position found in it is the same position in
    # `scan`. `str.lower()` would not do: some non-ASCII characters (e.g.
    # U+0130, Turkish dotted capital I) lower to TWO characters, which
    # shifts every later position. The closer tag itself is pure ASCII,
    # so folding only ASCII letters loses nothing.
    scan_for_close = scan.translate(_ASCII_LOWER)

    closes: List[Tuple[int, int]] = []
    search_from = 0
    while True:
        candidate = scan_for_close.find(close_tag, search_from)
        if candidate == -1:
            break
        search_from = candidate + close_len
        if _position_in_spans(candidate, comment_span_starts, comment_spans):
            continue
        closes.append((candidate, search_from))

    # Two-pointer merge of two already-ordered lists (each produced by a
    # single forward-only scan above), walking a depth counter rather
    # than sorting the combined event list -- sorting would cost
    # O(m log m) in the total open+close count, and a merge of two
    # sorted lists is O(m).
    regions: List[Tuple[int, int]] = []
    depth = 0
    region_start = -1
    i = j = 0
    n_opens, n_closes = len(opens), len(closes)
    while i < n_opens or j < n_closes:
        if j >= n_closes or (i < n_opens and opens[i] < closes[j][0]):
            if depth == 0:
                region_start = opens[i]
            depth += 1
            i += 1
        else:
            _, close_end = closes[j]
            j += 1
            if depth == 0:
                continue  # a closing tag with no opener currently in effect
            depth -= 1
            if depth == 0:
                regions.append((region_start, close_end))
    if depth > 0:
        regions.append((region_start, n))
    return regions


def _position_in_spans(
    pos: int,
    span_starts: List[int],
    spans: List[Tuple[int, int]],
    *,
    strict: bool = False,
) -> bool:
    """True when `pos` falls inside any (start, end) span in `spans`.

    `span_starts` is the parallel, already-sorted list of each span's own
    start (`_find_html_comment_spans` produces spans in start order via
    sequential `str.find`, so this is just `[s for s, _ in spans]`,
    computed ONCE by the caller rather than rebuilt on every call).
    Comment spans never overlap (each subsequent search starts strictly
    after the previous span's end), so the only span that could contain
    `pos` is the one with the rightmost start <= pos -- found with
    `bisect_right` in O(log k) rather than scanning every span in O(k)
    ([ai-config#3917](https://github.com/Morrison-Lab/ai-config/issues/3917) item 1, PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, third
    round). The prior linear scan made the OVERALL cost O(blocks x
    findings): each block's own marker is itself a complete HTML
    comment, so the comment-span list grows with the block count, and
    this function ran once per Findings-line match -- measured at a fixed
    262,144 characters: 1000 blocks 0.053s, 2000 blocks 0.188s.

    `strict=True` requires `pos` to fall AFTER a span's own start (`start
    < pos`, not `start <= pos`), for exactly one caller (PR
    [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review, seventh round): checking whether a v2
    marker's OWN start position is "inside a comment" is a trap the other
    callers of this function do not have, because the marker text
    `<!-- ccr-overview-v2 -->` is ITSELF a complete, self-contained HTML
    comment -- `_find_html_comment_spans` finds it and reports a span
    whose start EQUALS the marker's own start, so the default (`start <=
    pos`) trivially matches every genuine, standalone marker as "inside
    its own comment" and excludes it outright. What the marker-start
    check actually needs to catch is a marker whose `<!--` was consumed
    as the CLOSE of some EARLIER, different, unclosed comment (so the
    comment span found there starts strictly BEFORE the marker, not AT
    it) -- `strict=True` is exactly that distinction.
    """
    i = bisect.bisect_right(span_starts, pos) - 1
    if i < 0:
        return False
    start, end = spans[i]
    if strict:
        return start < pos < end
    return start <= pos < end


def _tokenize_copilot_line(rest: str) -> Optional[List[Tuple[str, str]]]:
    """Split a Findings-line remainder into ('TAG', text) / ('TEXT', text)
    tokens in one left-to-right pass, or None if a `<` is unterminated, a
    second `<` opens (outside any quoted attribute value) before the first
    one's own `>` closes it, or a quoted attribute value itself is left
    unterminated.

    The nested-`<` condition is deliberate, not merely a stricter version
    of "unterminated": it is what rejects a digit sitting INSIDE a
    malformed tag (`<picture 5 <img>`), by refusing to let that whole span
    collapse into one TAG token whose embedded `5` a later grammar check
    could never see as a separate token to validate.

    Quote tracking exists because a naive "next `>`" search truncates a
    tag at a `>` that appears inside a quoted attribute value
    (`<img alt="a>5">` would otherwise end at the `>` inside the quotes),
    which both mis-tokenizes legitimate markup and lets a `<`/`>` hidden
    inside a quoted value silently evade the nested-tag/unterminated-tag
    checks above ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding). While scanning for a
    tag's own `>`, a `"` or `'` toggles an in-quote state, and any `<`/`>`
    encountered while in that state is ordinary attribute content, not a
    tag boundary; a quote left open when the scan runs off the end of the
    string is itself an unterminated tag.

    Still one linear pass: the inner quote-tracking scan for one tag's `>`
    only ever advances forward, and the outer loop resumes immediately
    after wherever that scan stopped (its found `>`, or the end of the
    string on failure) -- so no character is ever re-examined by a second
    tag's scan, the same non-overlapping-advance argument that keeps a
    `str.find`-based scan linear.
    """
    tokens: List[Tuple[str, str]] = []
    pos = 0
    n = len(rest)
    while pos < n:
        if rest[pos] == "<":
            j = pos + 1
            quote = None
            close = -1
            while j < n:
                c = rest[j]
                if quote is not None:
                    if c == quote:
                        quote = None
                elif c in ('"', "'"):
                    quote = c
                elif c == ">":
                    close = j
                    break
                elif c == "<":
                    close = -2  # a second '<' before this tag's own '>'
                    break
                j += 1
            if close < 0:
                # close == -1: ran off the end with no '>' found, or a
                # quoted attribute value left open. close == -2: a nested
                # '<' outside any quote. Both fail the whole line closed.
                return None
            tokens.append(("TAG", rest[pos:close + 1]))
            pos = close + 1
        else:
            next_lt = rest.find("<", pos)
            if next_lt == -1:
                next_lt = n
            tokens.append(("TEXT", rest[pos:next_lt]))
            pos = next_lt
    return tokens


def _copilot_tag_name(tag: str) -> Optional[str]:
    """Return the lowercased name of an OPENING TAG token ('picture',
    'img', 'source', ...), or None for a closing tag or anything else that
    doesn't start with a letter right after `<`, or where the character
    right after the scanned name isn't a valid tag-name delimiter.

    That last check is required, not merely stricter ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899)
    review finding): stopping the alnum scan at the first non-alnum
    character without also checking what that character IS let
    `<img:evil>` and `<picture:evil>` -- neither a real tag -- scan as
    plain "img"/"picture" names (`:` simply isn't alnum, so the loop
    stopped there and returned the prefix as if it were valid), so
    `0 <img:evil>` parsed as a real zero-finding badge instead of failing
    closed. A real opening tag's name is always followed by whitespace
    (before an attribute), `/` (a void-element self-close), or `>` (the
    tag's own end) -- anything else means the "name" scanned is not
    actually a complete tag name.
    """
    low = tag.lower()
    if len(low) < 2 or not low[1].isalpha():
        return None
    j = 1
    while j < len(low) and low[j].isalnum():
        j += 1
    if low[j] not in (" ", "\t", "/", ">"):
        return None
    return low[1:j]


def _consume_copilot_badge(tokens: List[Tuple[str, str]], i: int) -> Optional[int]:
    """Consume one BADGE starting at tokens[i] (already known to be a TAG).

    Returns the index just past the badge on success, or None if it is
    not well-formed per the grammar in `_copilot_v2_line_findings_count`.
    """
    name = _copilot_tag_name(tokens[i][1])
    if name == "img":
        return i + 1
    if name != "picture":
        return None
    i += 1
    n = len(tokens)
    saw_img = False
    while True:
        if i >= n:
            return None  # <picture ...> never closed
        kind, val = tokens[i]
        if kind == "TEXT":
            if not _COPILOT_WS_ONLY.match(val):
                return None
            i += 1
            continue
        if val.lower() == "</picture>":
            return i + 1
        inner_name = _copilot_tag_name(val)
        # A `<source>` is only valid BEFORE the fallback `<img>` -- real
        # `<picture>` markup requires `<source>` elements to precede the
        # `<img>` they fall back from, and the grammar in this module's
        # docstring says the same ("any number of `<source ...>` and AT
        # MOST one `<img ...>`", in that order). `not saw_img` enforces
        # it: `0 <picture><img><source></picture>` used to accept the
        # `<source>` unconditionally, regardless of position
        # ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding, PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot
        # review, fourth round).
        if inner_name == "source" and not saw_img:
            i += 1
            continue
        if inner_name == "img" and not saw_img:
            saw_img = True
            i += 1
            continue
        return None  # any other tag -- a second <img>, a <source> after
        # the <img>, or a nested <picture> -- is disallowed inside a
        # picture badge


def _copilot_v2_line_findings_count(rest: str) -> Optional[int]:
    """Parse one `**Findings:**` line's remainder against the grammar in
    this module's docstring, summing the per-badge counts, or None (fail
    closed) if the line does not match.
    """
    tokens = _tokenize_copilot_line(rest)
    if tokens is None:
        return None
    n = len(tokens)
    i = 0
    total = 0
    saw_badge = False
    first = True
    while i < n:
        if tokens[i][0] != "TEXT":
            return None
        pattern = _COPILOT_FIRST_COUNT if first else _COPILOT_SEP_COUNT
        m = pattern.match(tokens[i][1])
        if m is None:
            # Only a whitespace-only tail at the very end of the line
            # (the grammar's trailing WS?) may fail this without failing
            # the whole line.
            if i == n - 1 and _COPILOT_WS_ONLY.match(tokens[i][1]):
                i += 1
                break
            return None
        i += 1
        if i >= n or tokens[i][0] != "TAG":
            return None
        new_i = _consume_copilot_badge(tokens, i)
        if new_i is None:
            return None
        total += int(m.group(1))
        saw_badge = True
        i = new_i
        first = False
    if i != n:
        return None
    return total if saw_badge else None


def _copilot_v2_findings_count(
    scan: str,
    cited: bytearray,
    match_is_cited: Callable[[bytearray, int, int], bool],
) -> Optional[int]:
    """Parse every `ccr-overview-v2` `**Findings:**` line into an inline-finding count.

    Mirrors the legacy `Comments generated: N` field's contract: returns
    an int (0 for `None`, otherwise the summed per-severity counts) and
    None -- fail closed -- when no recognisable line is present, every
    match is cited (quoted inside a fenced example), or a line is present
    but in neither recognised shape (a future format this function does
    not know).

    The main search is restricted to the actual overview block(s)
    (`_copilot_overview_block_spans`, see the module docstring's last
    section), and a match landing inside an HTML comment within a block
    is skipped, not counted -- both are structural fixes for non-rendered
    content (an indented pseudo-code-block field, or one hidden inside a
    multi-line `<!-- ... -->` comment) reading as the real field
    ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding, PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review).
    A second, orphan scan then reads live lines outside every block, so
    a real block whose own marker was excluded is not silently dropped:
    nonzero is decisive, unparseable gives no verdict, zero is ignored
    (see the comment above that loop). No
    block found at all means this body carries no v2 overview -- absent,
    not merely unparseable -- so this returns None exactly as it already
    does when a recognisable line is missing.

    Scans every uncited line across every block rather than committing to
    the first ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding), the same way the caller
    scans every uncited match of its own negative/affirmative heading and
    legacy count patterns: a body carrying two uncited `**Findings:**`
    lines -- `None` followed by a genuine `5 <picture...>` from a later
    round, or the reverse order, whether within one block or across two
    separate marker+heading pairs -- must not let either line's zero win
    over the other's nonzero. A nonzero count on any uncited line, in any
    block, is decisive and returned immediately; failing that, any
    unparseable line makes the whole result None; only when every uncited
    line across every block parses to exactly zero does this return 0.

    `match_is_cited` is injected rather than imported: it is the caller's
    own general-purpose citation-span check (used for several other
    patterns beyond this one), not specific to Copilot-overview parsing,
    so keeping it in the caller and passing it in here avoids a reverse
    dependency from this library module back onto its only consumer.
    """
    blocks = _copilot_overview_block_spans(scan, cited, match_is_cited)
    if not blocks:
        return None
    # Comment spans are computed ONCE, up to the FURTHEST block's end, not
    # once per block: a per-block `scan[:block_end]` call would repeat an
    # O(distance-from-start) scan for every block, which is quadratic-ish
    # when many marker+heading pairs are scattered through a large body
    # (block N's own scan would re-walk everything blocks 1..N-1 already
    # covered). One bounded scan up to `max(end for _, end in blocks)`
    # both avoids that and keeps the earlier-established property that a
    # comment opening before a block and extending into it is still
    # detected, for every block, not just the first (a measured 780KB
    # body with a small real block and a huge trailing section cost
    # ~0.2s scanning for comments that could not possibly affect the
    # block, against ~0.09s for a comparably-sized body whose content
    # stayed within the block, before this bound was added; the max-end
    # form preserves that fix across multiple blocks).
    max_end = max(end for _, end in blocks)
    comment_spans = _find_html_comment_spans(scan[:max_end])
    comment_span_starts = [s for s, _ in comment_spans]
    saw_line = False
    saw_unparseable = False
    for block_start, block_end in blocks:
        for m in COPILOT_FINDINGS_LINE.finditer(scan, block_start, block_end):
            if match_is_cited(cited, _findings_line_cite_start(m), m.end()):
                continue
            if _position_in_spans(m.start(), comment_span_starts, comment_spans):
                continue
            saw_line = True
            rest = m.group("rest")
            if _COPILOT_NONE_LINE.match(rest):
                continue
            count = _copilot_v2_line_findings_count(rest)
            if count is None:
                saw_unparseable = True
                continue
            if count != 0:
                return count
    # A live, uncited `**Findings:**` line OUTSIDE every recognised block
    # is one this function cannot place: typically a block whose own
    # marker was excluded (cited) while its real content was not, so that
    # content is orphaned before the next block. A line inside a
    # `<details>` region is skipped here for the same reason a block start
    # there is: that region quotes an earlier round's overview.
    # Its nonzero count is still decisive, and an unparseable one makes
    # the result None, rather than letting a later clean block speak for
    # the whole body. A zero one is ignored, exactly as before this scan
    # existed: it cannot make a body clean (only a recognised block's own
    # line can), so it cannot fail open either.
    block_starts = [b for b, _ in blocks]
    orphan_comment_spans: Optional[List[Tuple[int, int]]] = None
    orphan_comment_starts: List[int] = []
    orphan_details: List[Tuple[int, int]] = []
    orphan_details_starts: List[int] = []
    for m in COPILOT_FINDINGS_LINE.finditer(scan):
        if _position_in_spans(m.start(), block_starts, blocks):
            continue
        if match_is_cited(cited, _findings_line_cite_start(m), m.end()):
            continue
        if orphan_comment_spans is None:
            orphan_comment_spans = _find_html_comment_spans(scan)
            orphan_comment_starts = [a for a, _ in orphan_comment_spans]
            orphan_details = _find_details_regions(
                scan, orphan_comment_spans, orphan_comment_starts
            )
            orphan_details_starts = [a for a, _ in orphan_details]
        if _position_in_spans(m.start(), orphan_comment_starts, orphan_comment_spans):
            continue
        if _position_in_spans(m.start(), orphan_details_starts, orphan_details):
            continue
        rest = m.group("rest")
        if _COPILOT_NONE_LINE.match(rest):
            continue
        count = _copilot_v2_line_findings_count(rest)
        if count is None:
            saw_unparseable = True
        elif count != 0:
            return count
    if not saw_line or saw_unparseable:
        return None
    return 0
