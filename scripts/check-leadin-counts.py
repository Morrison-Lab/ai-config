#!/usr/bin/env python3
"""Flag a lead-in count that disagrees with the enumeration below it.

Morrison-Lab/ai-config#3005. Corpus prose regularly introduces a list with a
spelled-out count -- "Three things the new observation adds to those two
records.", "Two lightweight checks keep the skill catalog well-formed:" --
and then enumerates the items as bullets, numbered items, or bold-header
paragraphs underneath. When a later edit splits or merges one of those items
the lead-in count is not updated, and a reader who counts along stops at the
stated number and never reaches the last item.

The defect is invisible to every other check here: `check-links.py` sees no
link, `semantic-line-breaks.py` sees well-formed lines, and the prose reads
fluently in both the correct and the incorrect state. It is also pure counting
with no judgment in it, which is `shared/workflow/algorithmatize-checks.md`'s
exact shape for an instrument.

**False positives, not recall, are the binding constraint.** A checker that
flags every numeral in the corpus gets switched off, taking the real cases
with it. So this one fires only when all of the following hold, each bound
measured against the live corpus rather than guessed:

- The count word is spelled out (`two` .. `ten`). Numerals are excluded: in
  this corpus they are version numbers, day counts, and step numbers far more
  often than they are list counts. `one` is excluded for the same reason.
- The count opens the LAST sentence of the lead-in line, behind at most two
  function words ("There are two ..."). That is what separates "Two
  consequences worth keeping straight:" from "a cheap habit with two payoffs
  rather than a new one." and from "Holding two variables at once is hard."
- That count is followed within three tokens by a plural-looking noun, so
  "two variables" is a candidate and "two of those runs" is not.
- The lead-in starts its own paragraph and is not itself a list item, so a
  count inside one bullet never claims the bullets below it.
- The enumeration begins within one blank line of the lead-in.
- The count is not an explicit back-reference ("those three checks", "the
  three rules above"), which points at content already written rather than at
  the enumeration below.

Two enumeration shapes are counted, and they need different bounds:

- A **list** is bounded structurally: sibling items at one indent, ending at
  the first paragraph at that indent that is not an item. A `**Do:**` /
  `**Don't:**` block is a rule summary rather than the enumeration a lead-in
  counts, so it terminates the run (and an enumeration that opens with one is
  not an enumeration at all).
- **Bold-header paragraphs** have no such boundary: body prose sits between
  them, so the run can only stop at the next heading, and a long section will
  carry sub-points that are not siblings. Over-counting is therefore the
  normal failure there, so a bold-header mismatch is reported only when the
  count found is at most one above the count stated. That deliberately gives
  up the badly-stale bold lead-in to keep the checker quiet enough to leave
  on; the measured instance in #3005 was off by exactly one.

Exit codes: 0 clean, 1 at least one mismatch, 2 the scan examined no files
(a check that examined nothing reports clean and is indistinguishable from
one that passed).

Not wired into CI. Wiring it as a gate is a deliberate follow-up, after the
findings it reports on the live corpus have been read and fixed.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Add scripts/lib to import path for shared fences module
SCRIPTS_LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(SCRIPTS_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_LIB_DIR))

from fences import find_fence_spans  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

SUFFIXES = {".md", ".qmd", ".mdc"}

WORD_TO_NUM = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
COUNT_RE = re.compile(
    r"\b(?P<count>" + "|".join(WORD_TO_NUM) + r")\b(?P<rest>[^.;:!?]*)",
    re.IGNORECASE,
)

# Words ending in "s" that are not plural nouns. The list is short on purpose:
# over-excluding costs real catches, and the position requirements below are
# what actually bound the false positives.
NOT_A_PLURAL = {
    "is", "was", "has", "does", "its", "this", "thus", "us", "as", "plus",
    "versus", "less", "across", "always", "perhaps", "yes", "various",
    "previous", "obvious", "serious", "dangerous", "else", "otherwise",
}
IRREGULAR_PLURALS = {
    "people", "men", "women", "children", "criteria", "phenomena", "data",
}

# The only words a lead-in count may sit behind. Anything else in front of it
# ("Holding two variables at once", "a cheap habit with two payoffs") means the
# count is describing the sentence's own subject rather than announcing the
# items below, which is the commonest false positive this checker faces. The
# allowlist also disposes of the back-reference ("those three checks"), since
# no determiner pointing backwards is in it.
LEAD_IN_PREFIX = {
    "the", "and", "but", "so", "yet", "then", "now", "here", "there", "are",
    "is", "were", "also", "note", "all", "only", "just", "still",
}
# A count phrase carrying one of these is a cross-reference to content
# elsewhere in the file rather than to what follows.
BACKREF_AFTER = {"above", "below", "earlier"}

HEADING_RE = re.compile(r"^ {0,3}#{1,6}\s")
# The marker must be followed by whitespace, which is what keeps a bold run
# ("**Three surfaces.**") from reading as a `*` bullet.
ITEM_RE = re.compile(r"^(?P<indent> *)(?P<marker>[-*+]|\d+[.)])\s+\S")
DO_DONT_RE = re.compile(
    r"^ *(?:[-*+]|\d+[.)])\s+\**(?:Do|Don't|Do NOT)\b[:*]", re.IGNORECASE
)
BOLD_RE = re.compile(r"^\*\*(?!\s)")
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

# How many blank lines may separate the lead-in from the first item. 1 is a
# paragraph break; 0 is a list starting on the very next line.
MAX_GAP = 1
# How many word tokens may precede the count inside the lead-in sentence.
# Each of them must also be in LEAD_IN_PREFIX above.
MAX_TOKENS_BEFORE_COUNT = 2
# How many tokens after the count word may carry the plural noun, so that
# "Four freshness checks" is a candidate.
NOUN_WINDOW = 3
# How far a bold-header count may exceed the stated count before the run is
# read as having spilled past the enumeration rather than as a mismatch.
BOLD_OVERSHOOT = 1


def looks_plural(token: str) -> bool:
    """Return True when the token reads as a plural noun."""
    low = token.lower()
    if low in IRREGULAR_PLURALS:
        return True
    if low in NOT_A_PLURAL:
        return False
    if low.endswith("ss") or low.endswith("ness"):
        return False
    return len(low) > 3 and low.endswith("s")


def last_sentence(line: str) -> str:
    """Return the final sentence of a line, with leading markup removed.

    Semantic line breaks mean a corpus paragraph is one sentence per line, so
    the last sentence of the line above an enumeration is the clause the
    enumeration hangs off. A trailing colon is the commonest lead-in
    punctuation, so it is trimmed before splitting rather than producing an
    empty tail.
    """
    text = line.strip().rstrip(":")
    parts = [p for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    tail = parts[-1] if parts else ""
    return re.sub(r"^[\s*_>]+", "", tail)


def stated_count(sentence: str) -> tuple[int, str] | None:
    """Return (count, phrase) for a genuine lead-in count, else None."""
    for match in COUNT_RE.finditer(sentence):
        before = [tok.lower() for tok in TOKEN_RE.findall(sentence[: match.start()])]
        if len(before) > MAX_TOKENS_BEFORE_COUNT:
            # Past this point the count is inside the sentence rather than
            # announcing it, which is the commonest false positive of all.
            return None
        if any(tok not in LEAD_IN_PREFIX for tok in before):
            return None
        raw = match.group("count").lower()
        value = WORD_TO_NUM[raw]
        window = TOKEN_RE.findall(match.group("rest"))[:NOUN_WINDOW]
        if not window:
            continue
        # "three of those runs" counts runs, not the items below.
        if window[0].lower() == "of":
            continue
        if any(tok.lower() in BACKREF_AFTER for tok in window):
            continue
        if not any(looks_plural(tok) for tok in window):
            continue
        return value, f"{match.group('count')} {' '.join(window)}"
    return None


def count_list_items(lines: list[str], start: int, fenced: set[int]) -> int:
    """Count sibling list items at the indent of the item on `start`."""
    match = ITEM_RE.match(lines[start])
    if not match or DO_DONT_RE.match(lines[start]):
        return 0
    base = len(match.group("indent"))
    items = 0
    previous_blank = False
    for idx in range(start, len(lines)):
        if idx in fenced:
            previous_blank = False
            continue
        line = lines[idx]
        if not line.strip():
            previous_blank = True
            continue
        if HEADING_RE.match(line):
            break
        if DO_DONT_RE.match(line):
            # A Do/Don't block summarizes the rule; it is never the thing a
            # lead-in count is counting.
            break
        item = ITEM_RE.match(line)
        indent = len(line) - len(line.lstrip(" "))
        if item and indent == base:
            items += 1
        elif indent > base:
            # A nested item, or an indented continuation of the item above.
            pass
        elif not previous_blank:
            # CommonMark lazy continuation: an unindented line directly under
            # an item still belongs to it. Treating it as the end of the list
            # under-counts every item written that way.
            pass
        else:
            break
        previous_blank = False
    return items


def count_bold_headers(lines: list[str], start: int, fenced: set[int]) -> int:
    """Count paragraph-initial bold headers from `start` to the next heading.

    Body prose sits between such headers, so contiguity cannot bound the run
    the way it bounds a list. The section boundary is the only bound
    available, which is why the caller discounts a run that overshoots.
    """
    items = 0
    for idx in range(start, len(lines)):
        if idx in fenced:
            continue
        line = lines[idx]
        if HEADING_RE.match(line):
            break
        if not BOLD_RE.match(line):
            continue
        if idx == 0 or not lines[idx - 1].strip():
            items += 1
    return items


def enumeration_after(
    lines: list[str], lead: int, fenced: set[int]
) -> tuple[int, str] | None:
    """Return (start_index, kind) of the enumeration just below `lead`."""
    idx = lead + 1
    gap = 0
    while idx < len(lines) and not lines[idx].strip():
        gap += 1
        idx += 1
    if idx >= len(lines) or gap > MAX_GAP:
        return None
    if idx in fenced or HEADING_RE.match(lines[idx]):
        return None
    if ITEM_RE.match(lines[idx]):
        return idx, "list item"
    # A bold header must start its own paragraph. Without the blank line it is
    # a sentence-initial bold phrase inside the lead-in's own paragraph, and
    # the headers counted below it belong to some later block.
    if BOLD_RE.match(lines[idx]) and gap:
        return idx, "bold-header paragraph"
    return None


def is_lead_in(lines: list[str], idx: int, fenced: set[int]) -> bool:
    """Return True when line `idx` can announce an enumeration below it."""
    line = lines[idx]
    if idx in fenced or not line.strip():
        return False
    if HEADING_RE.match(line) or ITEM_RE.match(line):
        return False
    if idx == 0:
        return True
    previous = lines[idx - 1]
    # Its own paragraph: a count buried at the end of a long paragraph is not
    # announcing anything.
    return not previous.strip() or bool(HEADING_RE.match(previous))


def scan_text(text: str) -> list[tuple[int, int, int, str, str]]:
    """Return (line_no, stated, actual, kind, phrase) for each mismatch."""
    lines = text.split("\n")
    fenced, _, orphans = find_fence_spans(text, swallow_unclosed=False)
    fenced = fenced | orphans
    findings = []
    for lead, line in enumerate(lines):
        if not is_lead_in(lines, lead, fenced):
            continue
        found = enumeration_after(lines, lead, fenced)
        if found is None:
            continue
        counted = stated_count(last_sentence(line))
        if counted is None:
            continue
        start, kind = found
        stated, phrase = counted
        if kind == "list item":
            actual = count_list_items(lines, start, fenced)
        else:
            actual = count_bold_headers(lines, start, fenced)
            if actual > stated + BOLD_OVERSHOOT:
                continue
        if actual and actual != stated:
            findings.append((lead + 1, stated, actual, kind, phrase))
    return findings


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            capture_output=True, encoding="utf-8", check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"::error::cannot list tracked files: {exc}", file=sys.stderr)
        raise SystemExit(2)
    return [ROOT / p for p in out.split("\0") if p]


def scan(paths) -> tuple[list[tuple[Path, int, int, int, str, str]], int]:
    findings = []
    examined = 0
    for path in paths:
        if path.suffix not in SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        examined += 1
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        for line_no, stated, actual, kind, phrase in scan_text(text):
            findings.append((rel, line_no, stated, actual, kind, phrase))
    return findings, examined


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths", nargs="*", type=Path,
        help="markdown files to scan (default: every tracked markdown file)",
    )
    args = parser.parse_args(argv)
    findings, examined = scan(args.paths or tracked_files())
    if examined == 0:
        print("::error::examined 0 files -- the check did not run", file=sys.stderr)
        return 2
    # Report the population, not only the hits: a zero with no denominator is
    # indistinguishable from a detector that never ran.
    print(f"Examined {examined} markdown file(s) for lead-in count mismatches.")
    if not findings:
        print("OK: every lead-in count matches the enumeration below it.")
        return 0
    for rel, line_no, stated, actual, kind, phrase in findings:
        print(
            f"::warning file={rel},line={line_no}::"
            f"lead-in says {stated} ('{phrase}') but {actual} "
            f"{kind}(s) follow; update whichever is wrong"
        )
    print(f"\n{len(findings)} lead-in count mismatch(es) found.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
