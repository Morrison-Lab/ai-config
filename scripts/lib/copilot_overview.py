#!/usr/bin/env python3
"""Parse Copilot's ``ccr-overview-v2`` review body ``**Findings:**`` line.

``scripts/check-pr-fully-clean.py``'s ``copilot_verdict()`` reads a
Copilot formal review's own inline-finding count so it can decide whether
an affirmative overview heading (``### Approval recommended``) is
genuinely finding-free. The legacy body format states that count as
``Comments generated: N``; the newer ``ccr-overview-v2`` format
(ai-config#3899) states it instead as a ``**Findings:**`` line: either the
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
clean (ai-config#3899 review finding). This matches the real overview
shape in the Lacaedemon/sparta#1635 fixtures, where ``**Findings:**``
always starts its own line, unindented.

A further structural gap (ai-config#3899 review finding, PR
ai-config#3906 Copilot review): even a correctly-anchored, correctly
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
within that region. ``_copilot_overview_block_span`` locates that region:
it starts at the ``<!-- ccr-overview-v2 -->`` marker if present, or the
``## Copilot review overview`` heading if not (both are seen across the
real #1635 fixtures, always together and in that order; using EITHER as
a fallback start keeps this robust to a future body that drops one), and
ends immediately before the first ``<details`` tag or the next ``##``
heading that follows -- whichever comes first -- treating the block's own
``## Copilot review overview`` heading (when it follows a marker) as part
of the start, not as "the next heading" that would immediately end the
block at itself. ``_find_html_comment_spans`` then locates every
``<!--...-->`` span in the body with a linear ``str.find``-based scan
(not a lazy-dot regex, which would reintroduce the exact
"every unclosed opener rescans to the end" quadratic trap this module's
tokenizer already avoids for tag matching -- an unclosed ``<!--`` is
treated as extending to the end of the string, which is also the correct
fail-closed direction: content after a comment that never closes should
not be trusted as real). A ``**Findings:**`` match is accepted only when
it falls within the block span AND outside every comment span.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple

COPILOT_FINDINGS_LINE = re.compile(
    r"(?:^|\n)[ ]{0,3}\*\*Findings:\*\*[ \t]*(?P<rest>[^\n\r]*)", re.IGNORECASE
)
# Locate the actual Copilot v2 overview block rather than searching the
# whole body -- see the module docstring's last section for why. All three
# patterns are simple bounded literals/alternations with no lazy-dot or
# self-ambiguous repetition, so each `.search()` call is a single linear
# scan (shared/coding/regex-backtracking-pitfalls.md).
_COPILOT_OVERVIEW_MARKER = re.compile(r"<!--\s*ccr-overview-v2\s*-->")
_COPILOT_OVERVIEW_HEADING = re.compile(
    r"(?:^|\n)[ ]{0,3}##[ \t]+Copilot review overview\b", re.IGNORECASE
)
_COPILOT_DETAILS_OPEN = re.compile(r"(?:^|\n)[ ]{0,3}<details\b", re.IGNORECASE)
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
# after it (ai-config#3899 review finding). Requiring the whole line to be
# `None` (plus optional surrounding whitespace) means any trailing content
# falls through to the grammar parser instead, which fails it closed.
_COPILOT_NONE_LINE = re.compile(r"^[ \t]*None[ \t]*$", re.IGNORECASE)


def _copilot_overview_block_span(scan: str) -> Optional[Tuple[int, int]]:
    """Return the (start, end) character span of the Copilot v2 overview
    block in `scan`, or None if no block start (marker or heading) is
    found at all -- meaning this body carries no v2 overview, and any
    `**Findings:**`-looking text elsewhere is not a real field.

    See the module docstring's last section for the block boundary rule.
    The block's own `## Copilot review overview` heading, when it follows
    a found marker, is consumed as part of the start rather than left for
    the "next heading" search: since it is located with the SAME
    heading-specific pattern, whatever `_COPILOT_OVERVIEW_HEADING` finds
    after the marker cannot be a DIFFERENT heading by construction, so
    there is no ambiguity to resolve with a distance heuristic.
    """
    marker = _COPILOT_OVERVIEW_MARKER.search(scan)
    if marker is not None:
        start = marker.start()
        search_from = marker.end()
        own_heading = _COPILOT_OVERVIEW_HEADING.search(scan, search_from)
        if own_heading is not None:
            search_from = own_heading.end()
    else:
        heading = _COPILOT_OVERVIEW_HEADING.search(scan)
        if heading is None:
            return None
        start = heading.start()
        search_from = heading.end()
    end = len(scan)
    for pattern in (_COPILOT_DETAILS_OPEN, _COPILOT_NEXT_HEADING):
        m = pattern.search(scan, search_from)
        if m is not None and m.start() < end:
            end = m.start()
    return (start, end)


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


def _position_in_spans(pos: int, spans: List[Tuple[int, int]]) -> bool:
    """True when `pos` falls inside any (start, end) span in `spans`."""
    return any(s <= pos < e for s, e in spans)


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
    checks above (ai-config#3899 review finding). While scanning for a
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

    That last check is required, not merely stricter (ai-config#3899
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
        if inner_name == "source":
            i += 1
            continue
        if inner_name == "img" and not saw_img:
            saw_img = True
            i += 1
            continue
        return None  # any other tag, including a second <img> or a nested
        # <picture>, is disallowed inside a picture badge


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

    The search is restricted to the actual overview block
    (`_copilot_overview_block_span`, see the module docstring's last
    section), and a match landing inside an HTML comment within that
    block is skipped, not counted -- both are structural fixes for
    non-rendered content (an indented pseudo-code-block field, or one
    hidden inside a multi-line `<!-- ... -->` comment) reading as the real
    field (ai-config#3899 review finding, PR ai-config#3906 Copilot
    review). No block found at all means this body carries no v2 overview
    -- absent, not merely unparseable -- so this returns None exactly as
    it already does when a recognisable line is missing.

    Scans every uncited line within the block rather than committing to
    the first (ai-config#3899 review finding), the same way the caller
    scans every uncited match of its own negative/affirmative heading and
    legacy count patterns: a body carrying two uncited `**Findings:**`
    lines -- `None` followed by a genuine `5 <picture...>` from a later
    round, or the reverse order -- must not let either line's zero win
    over the other's nonzero. A nonzero count on any uncited line is
    decisive and returned immediately; failing that, any unparseable line
    makes the whole result None; only when every uncited line parses to
    exactly zero does this return 0.

    `match_is_cited` is injected rather than imported: it is the caller's
    own general-purpose citation-span check (used for several other
    patterns beyond this one), not specific to Copilot-overview parsing,
    so keeping it in the caller and passing it in here avoids a reverse
    dependency from this library module back onto its only consumer.
    """
    block = _copilot_overview_block_span(scan)
    if block is None:
        return None
    block_start, block_end = block
    # Bounded to `scan[:block_end]`, not the whole body: a comment span
    # this function needs to know about can only matter if it overlaps
    # [block_start, block_end), so scanning past block_end wastes time
    # proportional to whatever unrelated content follows the block (a
    # measured 780KB body with a small real block and a huge trailing
    # section cost ~0.2s scanning for comments that could not possibly
    # affect the block, against ~0.09s for a comparably-sized body whose
    # content stayed within the block). A comment that opens before
    # block_end and closes AFTER it is still handled correctly: slicing
    # at block_end makes it look "unterminated" within the slice, which
    # is the same conclusion (its span "extends to block_end" and beyond)
    # this function only ever needs, since nothing past block_end is
    # ever checked for containment. Starting the slice at 0 rather than
    # block_start also keeps a comment that OPENS before the block and
    # remains open across the boundary correctly detected.
    comment_spans = _find_html_comment_spans(scan[:block_end])
    saw_line = False
    saw_unparseable = False
    for m in COPILOT_FINDINGS_LINE.finditer(scan, block_start, block_end):
        if match_is_cited(cited, m.start(), m.end()):
            continue
        if _position_in_spans(m.start(), comment_spans):
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
    if not saw_line or saw_unparseable:
        return None
    return 0
