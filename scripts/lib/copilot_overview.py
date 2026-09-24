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
``**Findings:**`` match is accepted only when it falls within some
block's span AND outside every comment span.
"""
from __future__ import annotations

import bisect
import re
from typing import Callable, List, Optional, Tuple

COPILOT_FINDINGS_LINE = re.compile(
    r"(?:^|\n)[ ]{0,3}\*\*Findings:\*\*[ \t]*(?P<rest>[^\n\r]*)", re.IGNORECASE
)
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
_COPILOT_OVERVIEW_START = re.compile(
    r"(?:^|\n)[ ]{0,3}<!--\s*ccr-overview-v2\s*-->"
    r"(?:[ \t]*\r?\n)+"
    r"[ ]{0,3}##[ \t]+Copilot review overview[ \t]*(?=\r?\n|$)",
    re.IGNORECASE,
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
# after it ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding). Requiring the whole line to be
# `None` (plus optional surrounding whitespace) means any trailing content
# falls through to the grammar parser instead, which fails it closed.
_COPILOT_NONE_LINE = re.compile(r"^[ \t]*None[ \t]*$", re.IGNORECASE)


def _copilot_overview_block_spans(scan: str) -> List[Tuple[int, int]]:
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
    counts, since its start position falls outside every region. Reuses
    `_find_details_regions` / `_position_in_spans` -- the same
    bisect-backed containment check the HTML-comment exclusion already
    uses -- rather than a second, differently-shaped detector, and stays
    linear the same way: the regions are computed once, sorted by
    construction, and each block-start lookup costs O(log k) rather than
    a scan of every region.
    """
    details_regions = _find_details_regions(scan)
    details_region_starts = [s for s, _ in details_regions]
    spans: List[Tuple[int, int]] = []
    for start_m in _COPILOT_OVERVIEW_START.finditer(scan):
        start = start_m.start()
        if _position_in_spans(start, details_region_starts, details_regions):
            continue
        search_from = start_m.end()
        end = len(scan)
        for pattern in (_COPILOT_DETAILS_OPEN, _COPILOT_NEXT_HEADING):
            m = pattern.search(scan, search_from)
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


def _find_details_regions(scan: str) -> List[Tuple[int, int]]:
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
    call sites; the closing `</details>` is then found with `str.find`
    from there (not line-anchored -- matching `_find_html_comment_spans`'s
    own convention for its closing marker). An opening whose region
    already covers a later opening (a nested `<details>`, which real
    Copilot markup does not produce but this does not assume) is skipped
    rather than treated as a second region, and an opening with no
    closing `</details>` anywhere after it is treated as extending to the
    end of the string -- the same fail-closed direction
    `_find_html_comment_spans` already takes for an unterminated comment.
    `pos`/`finditer`'s own cursor only ever advance forward past a region
    already found or skipped, so this stays linear regardless of how many
    `<details>` sections (nested or not) the body contains.

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
    not-clean finding down to no-verdict. Checked with the same
    bisect-backed `_position_in_spans` helper against
    `_find_html_comment_spans(scan)`, computed once up front.
    """
    comment_spans = _find_html_comment_spans(scan)
    comment_span_starts = [s for s, _ in comment_spans]
    regions: List[Tuple[int, int]] = []
    pos = 0
    n = len(scan)
    for m in _COPILOT_DETAILS_OPEN.finditer(scan):
        if m.start() < pos:
            continue
        if _position_in_spans(m.start(), comment_span_starts, comment_spans):
            continue
        close_pos = scan.find("</details>", m.end())
        if close_pos == -1:
            regions.append((m.start(), n))
            break
        regions.append((m.start(), close_pos + len("</details>")))
        pos = close_pos + len("</details>")
    return regions


def _position_in_spans(
    pos: int, span_starts: List[int], spans: List[Tuple[int, int]]
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
    """
    i = bisect.bisect_right(span_starts, pos) - 1
    if i < 0:
        return False
    start, end = spans[i]
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

    The search is restricted to the actual overview block(s)
    (`_copilot_overview_block_spans`, see the module docstring's last
    section), and a match landing inside an HTML comment within a block
    is skipped, not counted -- both are structural fixes for non-rendered
    content (an indented pseudo-code-block field, or one hidden inside a
    multi-line `<!-- ... -->` comment) reading as the real field
    ([ai-config#3899](https://github.com/Morrison-Lab/ai-config/issues/3899) review finding, PR [ai-config#3906](https://github.com/Morrison-Lab/ai-config/pull/3906) Copilot review). No
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
    blocks = _copilot_overview_block_spans(scan)
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
            if match_is_cited(cited, m.start(), m.end()):
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
    if not saw_line or saw_unparseable:
        return None
    return 0
