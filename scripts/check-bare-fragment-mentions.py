#!/usr/bin/env python3
"""Report fragments a file links once and then mentions bare in the same file.

`CLAUDE.md`'s "Hyperlink technical terms and results" convention says a
fragment reference should carry its link.  The recurring miss is not a broken
link but an absent one: a file writes ``[`quotable-findings`](quotable-findings.md)``
correctly, then refers to the same fragment as plain prose further down.

`scripts/check-links.py` cannot see this by construction.  It validates the
links that *exist*, so a link nobody wrote is invisible to it --- the same
shape `shared/workflow/verify-the-right-artifact.md` records, where an
instrument keyed on the present artifact is unsound for an absent one.

## The strong case, and only the strong case

This checker fires only where the evidence is unambiguous:

* the file **already links** the fragment, so the author knew the link form
  and meant the reference;
* a later bare occurrence of that same basename appears **after** the first
  link, outside code fences, code spans, link constructs, URLs, blockquotes
  and headings;
* the basename is hyphenated, and is not one of the names that double as
  ordinary English.

A file that never links a fragment it names is deliberately out of scope: the
mention may be incidental, and a checker that guessed would train its readers
to ignore it.

## Two boundaries the issue states outright

**One finding per (file, fragment) pair, never one per occurrence.**  Linking
the same fragment five times in a paragraph is worse prose than the miss it
fixes, and `shared/workflow/challenge-redundant-content.md` would flag it.  The
report names the count so a reader can judge, and asks for a link at the first
bare mention rather than at all of them.

**`.cases.md` companions are skipped entirely.**  A case record discusses names
rather than referencing them, so a bare mention there is the subject of the
sentence.  Blockquoted lines are skipped everywhere for the same reason: quoted
review text names a fragment it is reporting on.

## Exemptions are reported, never silent

An exemption nobody can see is indistinguishable from a detector that missed
the file (`shared/principles/fail-fast.md`), so every (file, fragment) pair
that had a bare mention and was dropped anyway is listed in the `exempt`
bucket with its reason.  Two reasons exist, and neither can be decided from
the corpus alone:

* `single-word` --- an unhyphenated basename (`ardi`, `handoff`) that a
  boundary match cannot separate from ordinary text reliably enough;
* `common-phrase` --- a hyphenated basename that is also ordinary English
  (`fail-fast`, `issue-first`), where a bare occurrence is usually the phrase
  and not the reference.

Advisory: always exits 0, and reports what it examined rather than only what
it found, so a run that scanned nothing is distinguishable from a clean
corpus.

Usage:
    python3 scripts/check-bare-fragment-mentions.py
    python3 scripts/check-bare-fragment-mentions.py --json
    python3 scripts/check-bare-fragment-mentions.py --root /path/to/checkout
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from fences import CODE_SPAN_RE, strip_fences  # noqa: E402

# Same link vocabulary as scripts/check-links.py and
# scripts/check-stale-records.py, so the three agree on what a link is.
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# The whole link construct, stripped before the bare-mention scan: a fragment
# named inside link text is a reference that already carries its link.
LINK_CONSTRUCT = re.compile(r"\[[^\]]*\]\([^)]*\)")

# A markdown link reference definition, e.g. `[label]: some/path.md`.
LINK_DEFINITION = re.compile(r"^\s{0,3}\[[^\]]*\]:\s*\S")

# Autolinks and bare URLs: a basename inside a URL path is part of the path.
AUTOLINK = re.compile(r"<[^ >]+>")
BARE_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+")

# A double-quoted span on one line.  Quoted text -- an error message, a
# reviewer's wording, a login -- is being reported rather than referenced, the
# same reason blockquotes are skipped below.
QUOTED = re.compile(r'"[^"\n]{1,200}"')

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")

DEFAULT_SCAN_GLOBS = [
    "skills/**/*.md",
    "commands/**/*.md",
    "docs/**/*.md",
    "memories/**/*.md",
    "references/**/*.md",
    "shared/**/*.md",
    "*.md",
]

# Companion suffixes that belong to a parent fragment.  A `.rationale.md` or
# `.cases.md` file naming its own parent is talking about itself, not making a
# reference, so the parent stem counts as the file's own name.
COMPANION_SUFFIXES = (".cases", ".rationale")

# Hyphenated basenames that are also ordinary English phrases.  A bare
# occurrence of one of these is usually the phrase, so flagging it would train
# readers to ignore the checker.  Every drop is reported in the `exempt`
# bucket, so this list shrinks the findings visibly rather than silently.
# Extend with --common-phrase rather than by loosening the boundary match.
DEFAULT_COMMON_PHRASES = (
    "fail-fast",
    "fully-clean",
    "issue-first",
    "merge-queue",
    "plain-prose",
    "tidy-code",
)


def _blank(match: re.Match[str]) -> str:
    """Blank a matched region, keeping its newlines so line numbers hold."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_spans(text: str) -> str:
    """Fenced blocks and code spans blanked, line count preserved.

    `fences.strip_code_spans` substitutes a single space for a span that
    crosses a line, which collapses two source lines into one and shifts every
    later line number.  A finding that names the wrong line is worse than no
    finding, so blank the span in place instead.
    """
    return CODE_SPAN_RE.sub(_blank, strip_fences(text))


def is_external(target: str) -> bool:
    return target.startswith(SKIP_PREFIXES) or "://" in target


def fragment_name(target: str) -> str | None:
    """The fragment basename a relative markdown-link target names.

    `shared/workflow/quotable-findings.md#anchor` -> `quotable-findings`.
    Returns None for anything that is not a relative link to a markdown file.

    A companion target normalizes to its parent, so a link to
    `ardi.cases.md` registers `ardi`: the author demonstrated the link form
    for that family, which is the evidence this checker runs on.
    """
    target = target.strip()
    if not target or is_external(target):
        return None
    if "<" in target or ">" in target:
        return None  # angle-bracket placeholder, e.g. <owner>/<repo>
    path_part = re.split(r"[#?]", target, maxsplit=1)[0].strip()
    if not path_part.endswith(".md"):
        return None
    stem = Path(path_part).name[: -len(".md")]
    for suffix in COMPANION_SUFFIXES:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem or None


def own_names(md: Path) -> set[str]:
    """Names that refer to the scanned file itself, including its companions."""
    stem = md.name[: -len(".md")] if md.name.endswith(".md") else md.stem
    # The parent directory counts too: `skills/ardi/SKILL.md` naming `ardi` is
    # the skill talking about itself, not making an unlinked reference.
    names = {stem, md.parent.name}
    for suffix in COMPANION_SUFFIXES:
        if stem.endswith(suffix):
            names.add(stem[: -len(suffix)])
    return names


def is_case_record(md: Path) -> bool:
    """True for a `.cases.md` companion.

    A case record discusses fragment names rather than referencing them, so a
    bare mention there is the subject of the sentence.
    """
    return md.name.endswith(".cases.md")


def prose_lines(text: str) -> list[str]:
    """Line-aligned prose with every non-prose region blanked.

    Fenced blocks, code spans, whole link constructs, autolinks and bare URLs
    all go, and blockquote, heading, and link-definition lines are dropped
    whole.  Line indices are preserved so a finding can name a real line.
    """
    stripped = strip_spans(text)
    out: list[str] = []
    for line in stripped.split("\n"):
        bare = line.lstrip()
        if bare.startswith(">") or bare.startswith("#"):
            out.append("")
            continue
        if LINK_DEFINITION.match(line):
            out.append("")
            continue
        line = LINK_CONSTRUCT.sub(" ", line)
        line = BARE_URL.sub(" ", line)
        line = AUTOLINK.sub(" ", line)
        line = QUOTED.sub(" ", line)
        out.append(line)
    return out


def link_lines(text: str) -> dict[str, list[int]]:
    """Map each linked fragment basename to the 1-indexed lines linking it."""
    stripped = strip_spans(text)
    found: dict[str, list[int]] = {}
    for idx, line in enumerate(stripped.split("\n"), start=1):
        for target in LINK.findall(line):
            name = fragment_name(target)
            if name:
                found.setdefault(name, []).append(idx)
    return found


def mention_pattern(name: str) -> re.Pattern[str]:
    """A boundary match for `name` that no path or longer slug can satisfy.

    The lookarounds carry `-`, `/` and `.` on top of word characters, so
    `quotable-findings.md`, `x/quotable-findings` and `quotable-findings-2` are
    all path or slug context rather than a bare mention.  A trailing `.` only
    disqualifies the match when something word-like follows it: otherwise every
    sentence-final mention -- the commonest shape the checker exists to catch
    -- would be read as a file extension and silently dropped.

    Case-insensitive, because a sentence-initial `Quotable-findings` is the
    same missing link as a mid-sentence one, and a hyphenated lowercase slug
    is no likelier to collide with ordinary English in one case than the other.
    """
    return re.compile(
        r"(?<![A-Za-z0-9_/.-])"
        + re.escape(name)
        + r"(?![A-Za-z0-9_/-])(?!\.[A-Za-z0-9])",
        re.IGNORECASE,
    )


def bare_lines(lines: list[str], name: str, after: int) -> list[int]:
    """1-indexed lines after `after` carrying a bare mention of `name`."""
    pattern = mention_pattern(name)
    return [
        idx
        for idx, line in enumerate(lines, start=1)
        if idx > after and pattern.search(line)
    ]


def exempt_reason(name: str, common_phrases: tuple[str, ...]) -> str | None:
    """Why `name` is not a reliable bare-mention signal, or None."""
    if "-" not in name:
        return "single-word"
    if name in common_phrases:
        return "common-phrase"
    return None


def scan_files(root: Path, globs: list[str]) -> list[Path]:
    seen: set[Path] = set()
    for glob in globs:
        for md in root.glob(glob):
            if md.is_file():
                seen.add(md.resolve())
    return sorted(seen)


def scan_text(
    text: str,
    md: Path,
    common_phrases: tuple[str, ...] = DEFAULT_COMMON_PHRASES,
) -> tuple[list[dict], list[dict], int]:
    """Findings, exemptions, and the number of linked fragments considered."""
    findings: list[dict] = []
    exempt: list[dict] = []
    links = link_lines(text)
    lines = prose_lines(text)
    mine = own_names(md)
    considered = 0
    for name, at in sorted(links.items()):
        if name in mine:
            continue
        considered += 1
        first_link = min(at)
        linked_here = set(at)
        # A line that also links the fragment is not a missing link: the link
        # is right there, and asking for a second one on the same line is the
        # redundancy shared/workflow/challenge-redundant-content.md rejects.
        bare = [
            idx
            for idx in bare_lines(lines, name, first_link)
            if idx not in linked_here
        ]
        if not bare:
            continue
        reason = exempt_reason(name, common_phrases)
        record = {
            "fragment": name,
            "link_line": first_link,
            "bare_lines": bare,
        }
        if reason:
            exempt.append({**record, "reason": reason})
        else:
            findings.append(record)
    return findings, exempt, considered


def collect(
    root: Path,
    globs: list[str],
    common_phrases: tuple[str, ...] = DEFAULT_COMMON_PHRASES,
) -> dict:
    """Scan `root` and return the full report as data."""
    files = scan_files(root, globs)
    findings: list[dict] = []
    exempt: list[dict] = []
    scanned = 0
    skipped_cases = 0
    considered = 0
    for md in files:
        if is_case_record(md):
            skipped_cases += 1
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        file_findings, file_exempt, file_considered = scan_text(
            text, md, common_phrases
        )
        considered += file_considered
        rel = str(md.relative_to(root)) if md.is_relative_to(root) else str(md)
        for record in file_findings:
            findings.append({"path": rel, **record})
        for record in file_exempt:
            exempt.append({"path": rel, **record})
    findings.sort(key=lambda r: (-len(r["bare_lines"]), r["path"], r["fragment"]))
    exempt.sort(key=lambda r: (r["path"], r["fragment"]))
    return {
        "root": str(root),
        "files_scanned": scanned,
        "case_records_skipped": skipped_cases,
        "links_considered": considered,
        "findings": findings,
        "exempt": exempt,
    }


def format_report(report: dict, limit: int) -> str:
    out: list[str] = []
    out.append(
        f"Examined {report['files_scanned']} file(s), "
        f"{report['links_considered']} linked fragment reference(s); "
        f"skipped {report['case_records_skipped']} .cases.md companion(s)."
    )
    findings = report["findings"]
    out.append(f"\nBare mentions after a link: {len(findings)}")
    for record in findings[:limit]:
        lines = ", ".join(str(n) for n in record["bare_lines"][:5])
        more = "" if len(record["bare_lines"]) <= 5 else ", ..."
        out.append(
            f"  {record['path']}: {record['fragment']} "
            f"linked at line {record['link_line']}, bare at line(s) "
            f"{lines}{more}"
        )
    if len(findings) > limit:
        out.append(f"  ... {len(findings) - limit} more")
    exempt = report["exempt"]
    out.append(f"\nExempt (reported, not dropped silently): {len(exempt)}")
    counts: dict[str, int] = {}
    for record in exempt:
        counts[record["reason"]] = counts.get(record["reason"], 0) + 1
    for reason in sorted(counts):
        out.append(f"  {reason}: {counts[reason]}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    parser.add_argument(
        "--glob",
        action="append",
        dest="globs",
        help="scan glob, repeatable (default: this repo's markdown trees)",
    )
    parser.add_argument(
        "--common-phrase",
        action="append",
        dest="phrases",
        help=(
            "hyphenated basename that is also ordinary English, repeatable "
            f"(default: {', '.join(DEFAULT_COMMON_PHRASES)})"
        ),
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="max findings to print (default: 20)"
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    globs = args.globs or DEFAULT_SCAN_GLOBS
    phrases = tuple(args.phrases) if args.phrases else DEFAULT_COMMON_PHRASES
    report = collect(root, globs, phrases)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report, args.limit))

    return 0  # advisory


if __name__ == "__main__":
    sys.exit(main())
