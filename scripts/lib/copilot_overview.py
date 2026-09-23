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
...</picture>`` alone, or ``2 <picture ...></picture> . 1 <picture
...></picture>`` (a middle dot between them) for a mixed body.

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
``(?:^|\\n)`` plus optional leading whitespace only -- because an
unanchored ``\\*\\*Findings:\\*\\*`` matches anywhere in the body,
including mid-sentence prose ("Earlier output said **Findings:** None")
or a blockquoted copy of an earlier round's overview (whose line begins
with ``>``, which the whitespace-only prefix does not admit). Either
would otherwise be read as the real v2 zero-count source for an
affirmative review that carries no genuine overview field at all, reading
clean (ai-config#3899 review finding). This matches the real overview
shape in the Lacaedemon/sparta#1635 fixtures, where ``**Findings:**``
always starts its own line.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple

COPILOT_FINDINGS_LINE = re.compile(
    r"(?:^|\n)[ \t]*\*\*Findings:\*\*[ \t]*(?P<rest>[^\n\r]*)", re.IGNORECASE
)
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

    Scans every uncited line rather than committing to the first
    (ai-config#3899 review finding), the same way the caller scans every
    uncited match of its own negative/affirmative heading and legacy
    count patterns: a body carrying two uncited `**Findings:**` lines --
    `None` followed by a genuine `5 <picture...>` from a later round, or
    the reverse order -- must not let either line's zero win over the
    other's nonzero. A nonzero count on any uncited line is decisive and
    returned immediately; failing that, any unparseable line makes the
    whole result None; only when every uncited line parses to exactly
    zero does this return 0.

    `match_is_cited` is injected rather than imported: it is the caller's
    own general-purpose citation-span check (used for several other
    patterns beyond this one), not specific to Copilot-overview parsing,
    so keeping it in the caller and passing it in here avoids a reverse
    dependency from this library module back onto its only consumer.
    """
    saw_line = False
    saw_unparseable = False
    for m in COPILOT_FINDINGS_LINE.finditer(scan):
        if match_is_cited(cited, m.start(), m.end()):
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
