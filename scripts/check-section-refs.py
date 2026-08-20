#!/usr/bin/env python3
"""Check that quoted section-title references still name a real heading.

check-links.py verifies that a relative markdown link *resolves* --- the
target file exists.  It cannot see a narrower kind of breakage: prose that
links to a file AND quotes a section title from it, e.g.

    recorded in [`claude-review-dispatch.md`](claude-review-dispatch.md)'s
    "`ai-config` never auto-reviews a PR on push"

The link resolves even after the target's heading is renamed, so the quoted
title silently goes stale and check-links.py stays clean forever.  This
script extracts every such quoted reference, resolves the linked file, and
checks whether the quote still names a real heading there.

Three reference shapes were found by grepping the corpus for how this idiom
is actually written (roughly 130 apostrophe-form hits, ~40 comma-form hits,
and 2 quoted-link-text hits at survey time); all three are checked:

  Form A  (apostrophe, universal):
      [text](target)'s "Quoted Title"
  Form A2 (comma, scoped -- see SEE_PREFIX / CASES_SUFFIX below):
      See [text](target.cases.md), "Quoted Title"
  Form B  (quoted link text, universal):
      ["Quoted Title"](target)

A quote often does not spell out its target in full -- semantic line breaks
mean a long heading or bold lead gets truncated at whichever clause boundary
the citing prose needed, which can be the front ("A cancelled dispatch that
fired a" for a heading that continues "...failure webhook against the
superseded SHA"), the middle, or (after a colon) effectively the tail
("partial is worse than absent" for "## In a guard you ship: partial is
worse than absent").  So a quote is accepted if, after tolerant
normalization (backticks stripped, whitespace collapsed, case-folded), it is
a SUBSTRING of a real ATX heading, a paragraph-leading bold span
(`**Like this.**`), or a list item's own bold lead (`- **Like this:**`) in
the target file -- this corpus uses both bold conventions as informal
section anchors in the same idiom, and treating only `#`-headings as valid
targets makes those legitimate references false positives.

Clean-room; convention noted in CREDITS.md.

Exit codes (see shared/workflow/fully-clean.md's three-way convention):
    0 -- clean, no stale quoted references found
    1 -- at least one stale quoted reference found
    2 -- usage or environment error
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import CODE_SPAN_RE, strip_fences  # noqa: E402

USAGE_EXIT = 2

ROOT = Path(__file__).resolve().parent.parent

SCAN_GLOBS = [
    "skills/**/*.md",
    "codex-skills/**/*.md",
    "commands/**/*.md",
    "docs/**/*.md",
    "memories/**/*.md",
    "references/**/*.md",
    "shared/**/*.md",
    "*.md",
]

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")

MAX_QUOTE_LEN = 400

# Form A: [text](target)'s "Quoted Title"  -- the possessive-apostrophe idiom.
FORM_A = re.compile(
    r"\[[^\]]*\]\((?P<target>[^)]+)\)'s\s+"
    r'"(?P<quote>[^"]{1,%d})"' % MAX_QUOTE_LEN
)

# Form A2: [text](target), "Quoted Title"  -- the comma idiom.  find_references
# below scopes a match to a target ending in ".cases.md", or to text
# immediately preceded by "See ", since an unscoped comma-plus-quote is
# common ordinary prose ("Per [x](y.md), \"some phrase\" means ...") that was
# never meant as a title citation at all.
FORM_A2 = re.compile(
    r"\[[^\]]*\]\((?P<target>[^)]+)\),\s+"
    r'"(?P<quote>[^"]{1,%d})"' % MAX_QUOTE_LEN
)

# Form B: ["Quoted Title"](target)  -- the quote IS the link text.
FORM_B = re.compile(
    r'\["(?P<quote>[^"]{1,%d})"\]\((?P<target>[^)]+)\)' % MAX_QUOTE_LEN
)

HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
# A paragraph-leading bold span: "**Like this sentence.**" possibly wrapped
# across a semantic line break, so DOTALL and a length cap rather than a
# single-line match.
BOLD_LEAD = re.compile(r"^\*\*(.{1,%d}?)\*\*" % MAX_QUOTE_LEN, re.M | re.S)
# A list-item's own bold lead: "- **Do:** ..." / "  - **403 caveat** ...".
# This corpus's Do/Don't and named-finding bullets consistently open with a
# bold clause right after the list marker; that clause is a structural
# anchor in the same idiom as a heading, but BOLD_LEAD (anchored to column 0)
# never sees it because a list marker and its indent come first.
LIST_BOLD_LEAD = re.compile(
    r"^[ \t]*[-*][ \t]+\*\*(.{1,%d}?)\*\*" % MAX_QUOTE_LEN, re.M | re.S
)

MIN_QUOTE_LEN = 4  # normalized characters; guards against a trivial substring


def is_external(target: str) -> bool:
    return target.startswith(SKIP_PREFIXES) or "://" in target


def normalize(text: str) -> str:
    """Fold a quote or heading/bold-lead down to a comparable core string.

    Strips backticks (headings routinely wrap a code term in them, and a
    quote may or may not echo the backticks), and collapses all whitespace
    (a quote or heading can wrap across a semantic line break) to single
    spaces.  Comparison is a SUBSTRING test (see quote_matches below), so no
    punctuation trimming happens here: a quote is a verbatim truncation of
    the real text, not a reworded copy, and trimming could shift a boundary
    that was never actually ambiguous.
    """
    text = text.replace("`", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def quote_matches(quote: str, candidates: list[str]) -> bool:
    """True if the normalized quote is a substring of any candidate.

    A quote is not always a PREFIX of the real text: semantic line breaks
    mean a long heading or bold lead gets truncated at whichever clause
    boundary the citing prose needed, which can be the front ("A cancelled
    dispatch that fired a" for a heading that continues), the middle, or
    (after a colon) effectively the tail ("partial is worse than absent" for
    "## In a guard you ship: partial is worse than absent").  A substring
    test covers all three without over-matching, since MIN_QUOTE_LEN still
    rules out a trivial two-or-three-character quote matching everything.
    """
    norm_quote = normalize(quote)
    if len(norm_quote) < MIN_QUOTE_LEN:
        return False
    return any(norm_quote in c for c in candidates)


def strip_fenced_blocks(text: str) -> str:
    """Blank fenced code blocks only, preserving line count.

    Fenced blocks are the one place a literal illustration of this repo's
    quote-reference idiom could appear and must not trip the checker.
    Inline code spans are deliberately NOT stripped here (contrast
    check-links.py, which strips both): a quoted title routinely echoes a
    backtick-wrapped term from the heading itself (e.g. "`ai-config` never
    auto-reviews..."), so blanking every inline span would destroy real
    quote content, not just code examples.  strip_fences() also preserves
    line count (blanks whole lines), which line-number reporting needs.
    """
    return strip_fences(text)


def in_single_code_span(text: str, start: int, end: int) -> bool:
    """True if [start, end) falls entirely inside one inline code span.

    The narrow case inline-code stripping exists for: a match that is
    itself a literal illustration of the pattern, written inside backticks
    rather than as real prose (e.g. a doc explaining the idiom by showing
    `[text](file.md)'s "Title"` as a one-line example).  Uses fences.py's
    own CODE_SPAN_RE rather than a second hand-rolled backtick matcher.
    """
    for m in CODE_SPAN_RE.finditer(text):
        if m.start() <= start and end <= m.end():
            return True
        if m.start() > end:
            break
    return False


def extract_headings(text: str) -> list[str]:
    return [normalize(h) for h in HEADING.findall(text)]


def extract_bold_leads(text: str) -> list[str]:
    return [normalize(b) for b in BOLD_LEAD.findall(text)] + [
        normalize(b) for b in LIST_BOLD_LEAD.findall(text)
    ]


def resolve_target(referring_file: Path, target: str) -> Path | None:
    """Resolve a link target to a file path, or None if not a plain repo-relative file link."""
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.split(" ", 1)[0]
    if not target or is_external(target):
        return None
    if "<" in target or ">" in target:
        return None
    path_part = re.split(r"[#?]", target, maxsplit=1)[0]
    if not path_part:
        return None
    if "/" not in path_part and "." not in path_part:
        return None
    return (referring_file.parent / path_part).resolve()


class Reference:
    def __init__(
        self, referring_file: Path, line_no: int, quote: str, target: str,
        form: str,
    ):
        self.referring_file = referring_file
        self.line_no = line_no
        self.quote = quote
        self.target = target
        self.form = form


def line_number_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def find_references(md: Path, raw_text: str) -> list[Reference]:
    text = strip_fenced_blocks(raw_text)
    refs: list[Reference] = []

    for m in FORM_A.finditer(text):
        if in_single_code_span(text, m.start(), m.end()):
            continue
        refs.append(
            Reference(md, line_number_of(text, m.start()), m.group("quote"),
                       m.group("target"), "A")
        )

    for m in FORM_A2.finditer(text):
        if in_single_code_span(text, m.start(), m.end()):
            continue
        target = m.group("target").strip()
        preceding = text[max(0, m.start() - 5):m.start()]
        cases_target = re.split(r"[#?]", target, maxsplit=1)[0].endswith(
            ".cases.md"
        )
        see_prefix = preceding.endswith("See ")
        if not (cases_target or see_prefix):
            continue
        refs.append(
            Reference(md, line_number_of(text, m.start()), m.group("quote"),
                       target, "A2")
        )

    for m in FORM_B.finditer(text):
        if in_single_code_span(text, m.start(), m.end()):
            continue
        refs.append(
            Reference(md, line_number_of(text, m.start()), m.group("quote"),
                       m.group("target"), "B")
        )

    return refs


def scan_files(root: Path, globs: list[str]) -> list[Path]:
    seen: set[Path] = set()
    for glob in globs:
        for md in root.glob(glob):
            if md.is_file():
                seen.add(md.resolve())
    return sorted(seen)


def check_repo(root: Path, globs: list[str]) -> tuple[list[dict], int, int]:
    """Return (stale findings, references examined, files scanned)."""
    files = scan_files(root, globs)
    texts: dict[Path, str] = {}
    for md in files:
        try:
            texts[md] = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            texts[md] = ""

    heading_cache: dict[Path, list[str] | None] = {}
    bold_cache: dict[Path, list[str] | None] = {}

    def targets_for(target_path: Path) -> tuple[list[str], list[str]] | None:
        if target_path not in texts:
            if not target_path.exists() or not target_path.is_file():
                return None
            try:
                texts[target_path] = target_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return None
        if target_path not in heading_cache:
            body = strip_fenced_blocks(texts[target_path])
            heading_cache[target_path] = extract_headings(body)
            bold_cache[target_path] = extract_bold_leads(body)
        return heading_cache[target_path], bold_cache[target_path]

    findings: list[dict] = []
    examined = 0

    for md in files:
        for ref in find_references(md, texts[md]):
            target_path = resolve_target(md, ref.target)
            if target_path is None:
                continue
            resolved = targets_for(target_path)
            if resolved is None:
                # Missing-file breakage is check-links.py's job, not ours;
                # skip rather than double-report.
                continue
            headings, bold_leads = resolved
            examined += 1
            if quote_matches(ref.quote, headings) or quote_matches(
                ref.quote, bold_leads
            ):
                continue
            findings.append({
                "referring_file": md,
                "line": ref.line_no,
                "quote": ref.quote,
                "target": ref.target,
                "target_path": target_path,
                "form": ref.form,
            })

    return findings, examined, len(files)


def format_report(root: Path, findings: list[dict], examined: int, scanned: int) -> str:
    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(root))
        except ValueError:
            return str(p)

    lines = [
        f"Examined {examined} quoted section-title reference(s) across "
        f"{scanned} markdown files."
    ]
    if not findings:
        lines.append("no stale section-title references")
        return "\n".join(lines)

    lines.append(f"\n{len(findings)} stale section-title reference(s):")
    for f in findings:
        lines.append(
            f"  - {rel(f['referring_file'])}:{f['line']} quotes "
            f'"{f["quote"]}" -> {f["target"]} '
            f"({rel(f['target_path'])}), no matching heading found"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=ROOT,
        help="repository root to scan (default: this repo)",
    )
    parser.add_argument(
        "--glob", action="append", dest="globs",
        help="scan glob, repeatable (default: this repo's markdown trees)",
    )
    # argparse itself already exits 0 on --help and 2 on a usage error,
    # which lines up with this script's own usage-exit convention.
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: --root {root} is not a directory", file=sys.stderr)
        return USAGE_EXIT

    globs = args.globs or SCAN_GLOBS
    findings, examined, scanned = check_repo(root, globs)
    print(format_report(root, findings, examined, scanned))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
