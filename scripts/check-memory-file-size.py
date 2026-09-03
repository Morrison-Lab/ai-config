#!/usr/bin/env python3
"""Flag memory files that have grown large enough to warrant splitting.

Memory files under `memories/` are read on demand, not auto-loaded into
context the way `CLAUDE.md` and its `@shared/...` fragments are. So their
length is a real per-use cost: an agent that reads one whole to retrieve a
single fact pays for the entire file. They also grow one appended bullet at
a time, and no single append ever looks like the one that made the file too
big -- which is how `memories/tools.md` reached 3,496 lines before
ai-config#694 split it into topical files.

Per `shared/workflow/algorithmatize-checks.md`, "is this file too long" is a
decidable check over available data, so it belongs in an instrument rather
than in anyone's periodic judgment.

Threshold rationale (`--max-lines`, default below):

  1,250 lines of memory prose is roughly 12.5k tokens -- a defensible ceiling
  for a file an agent may read whole. It also sits just above the largest
  file ai-config#694's split produced (`github-actions.md`, ~1,066 lines),
  so the corpus starts green with real but finite headroom. The value is a
  parameter rather than a literal per
  `shared/coding/configurable-parameters.md`.

CI AND PRE-PUSH ENFORCEMENT
---------------------------
CI (.github/workflows/validate.yml) runs `python3 scripts/check-memory-file-size.py --strict`
(ai-config#2970), and `scripts/test_check_memory_file_size.py` asserts the live
corpus is under DEFAULT_MAX_LINES (1250 lines). A PR that appends past 1250 lines
cannot merge; it has to split first. A file already AT the cap cannot take a
net-positive append either. Recover lines (re-wrap or drop) or split, rather
than adding lines. A fold has two shapes and neither escapes every gate:
putting the new sentence on its own source line trips this size test, while
densifying an existing line leaves the line count flat but makes that line a
changed line the new-line-breaks gate can flag.

Run `python3 scripts/check-memory-file-size.py --strict` before pushing to match CI.
When run without `--strict`, the script is advisory (exits 0 while printing findings).

APPROACHING THE CAP (`--warn-fraction`)
---------------------------------------
Reporting only the breach is what made this check arrive too late to act on.
"No memory file exceeds 1250 lines" is equally true at 3 lines and at 1250, so
a session about to append learned a file was full by tripping the gate, then
filed an issue about whichever file it happened to touch -- 22 near-identical
issues across six weeks, per ai-config#3102. The information is actionable
*before* the write, not after.

So any file in the band `warn_lines <= n <= max_lines` is reported with its
remaining headroom. A file sitting exactly AT the cap is a warning rather than
a breach (the failure fires strictly above `max_lines`), and it is precisely
the file that cannot take another line.

Warnings never change the exit code, under `--strict` or without it. The band
is a trend line, not a second gate: making it fail would just move the wall
inward and re-create the same surprise 100 lines earlier.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MAX_LINES = 1250

# Fraction of `--max-lines` above which a file is reported as approaching the
# cap. 0.92 of 1250 is 1150, which leaves 100 lines -- room for several UMS
# appends, so a warned file can be split at some deliberate moment rather than
# by whichever session happens to run out of room first. A parameter rather
# than a literal per `shared/coding/configurable-parameters.md`.
DEFAULT_WARN_FRACTION = 0.92

# `MEMORY.md` is the index, not a memory file; `session/` holds
# conversation-scoped notes that are never meant to persist or be split.
#
# The `session/` prefix filter is load-bearing, NOT redundant with the
# `<dir>/*.md` pathspec below. In a DEFAULT git pathspec a wildcard does
# match `/`; it is the explicit `:(glob)` magic that stops it, not the
# default. So `memories/*.md` returns nested files too:
#
#   $ git ls-files -- "memories/*.md"
#   memories/session/notes.md
#   memories/top.md
#   $ git ls-files -- ":(glob)memories/*.md"
#   memories/top.md
#
# Without this filter, session notes would be scanned and flagged.
# `test_check_memory_file_size.py` asserts the `git ls-files` half of this
# directly, so the claim is checked rather than trusted.
_EXCLUDED_NAMES = ("MEMORY.md",)
_EXCLUDED_PREFIXES = ("memories/session/",)


def tracked_memory_files(directory: str) -> list[str]:
    """Repo-relative paths of the tracked .md files under `directory`."""
    out = subprocess.run(
        ["git", "ls-files", "--", f"{directory}/*.md"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    ).stdout
    paths = [line for line in out.split("\n") if line]
    return [
        p
        for p in paths
        if Path(p).name not in _EXCLUDED_NAMES
        and not p.startswith(_EXCLUDED_PREFIXES)
    ]


def measured_files(directory: str) -> list[tuple[str, list[str]]]:
    """(path, lines) for each tracked memory file under `directory`."""
    return [
        (rel_path, (REPO_ROOT / rel_path).read_text(encoding="utf-8").splitlines())
        for rel_path in tracked_memory_files(directory)
    ]


def warn_line_threshold(max_lines: int, warn_fraction: float) -> int:
    """Line count at or above which a file is reported as approaching."""
    return round(max_lines * warn_fraction)


def section_sizes(lines: list[str]) -> list[tuple[str, int]]:
    """(heading, line-count) for each `## ` section, largest first."""
    sections: list[tuple[str, int]] = []
    heading: str | None = None
    count = 0
    for line in lines:
        if line.startswith("## "):
            if heading is not None:
                sections.append((heading, count))
            heading = line[3:].strip()
            count = 0
        count += 1
    if heading is not None:
        sections.append((heading, count))
    return sorted(sections, key=lambda s: -s[1])


def oversized_files(
    directory: str, max_lines: int
) -> list[tuple[str, int, list[tuple[str, int]]]]:
    """(path, line-count, largest sections) for each file over `max_lines`."""
    findings = [
        (rel_path, len(lines), section_sizes(lines)[:5])
        for rel_path, lines in measured_files(directory)
        if len(lines) > max_lines
    ]
    return sorted(findings, key=lambda f: -f[1])


def approaching_files(
    directory: str, max_lines: int, warn_lines: int
) -> list[tuple[str, int, int]]:
    """(path, line-count, headroom) for each file in the warning band.

    The band is `warn_lines <= n <= max_lines`, so it is disjoint from
    `oversized_files`, which fires strictly above `max_lines`. A file at
    exactly the cap therefore appears here, with a headroom of 0.
    """
    findings = [
        (rel_path, len(lines), max_lines - len(lines))
        for rel_path, lines in measured_files(directory)
        if warn_lines <= len(lines) <= max_lines
    ]
    return sorted(findings, key=lambda f: -f[1])


def report_approaching(
    approaching: list[tuple[str, int, int]],
    max_lines: int,
    warn_lines: int,
    announce_empty: bool = True,
) -> None:
    """Print the warning band, or say the band is empty.

    Printed even when nothing breached, because the silence in the clean case
    is the whole defect (ai-config#3102): a session reading "no memory file
    exceeds 1250 lines" cannot tell 3 lines from 1250.

    `announce_empty` is False when a breach was already reported. An
    over-cap file is past the cap rather than near it, so "no memory file is
    within N lines of the cap" would read as contradicting the finding
    printed directly above it.
    """
    if not approaching:
        if announce_empty:
            print(
                f"No memory file is within {max_lines - warn_lines} lines of the cap."
            )
        return

    print(
        f"\n{len(approaching)} memory file(s) are approaching the "
        f"{max_lines}-line cap ({warn_lines} lines or more).\n"
        "Split before appending: the next entry may not fit.\n"
    )
    for rel_path, n_lines, headroom in approaching:
        print(f"  {rel_path}: {n_lines} lines ({headroom} lines of headroom)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        default="memories",
        help="directory of memory files to check (default: memories)",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=DEFAULT_MAX_LINES,
        help=f"lines above which a file is flagged (default: {DEFAULT_MAX_LINES})",
    )
    parser.add_argument(
        "--warn-fraction",
        type=float,
        default=DEFAULT_WARN_FRACTION,
        help=(
            "fraction of --max-lines at which a file is reported as "
            f"approaching the cap (default: {DEFAULT_WARN_FRACTION})"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if any file is over the threshold (default: advisory, exits 0)",
    )
    args = parser.parse_args()

    # Fail fast rather than silently degrading the band: a fraction of 1
    # collapses it to files at exactly the cap, one above 1 empties it, and one
    # at or below 0 warns on every file. None of those is a usable band, and
    # each fails silently -- the run just prints a band that says nothing.
    if not 0 < args.warn_fraction < 1:
        parser.error("--warn-fraction must be strictly between 0 and 1")

    warn_lines = warn_line_threshold(args.max_lines, args.warn_fraction)
    findings = oversized_files(args.directory, args.max_lines)
    approaching = approaching_files(args.directory, args.max_lines, warn_lines)

    if not findings:
        print(f"No memory file exceeds {args.max_lines} lines.")
        report_approaching(approaching, args.max_lines, warn_lines)
        return

    print(
        f"{len(findings)} memory file(s) exceed {args.max_lines} lines and may "
        f"be worth splitting into topical files (see ai-config#694 for the "
        f"pattern):\n"
    )
    for rel_path, n_lines, largest in findings:
        print(f"  {rel_path}: {n_lines} lines")
        for heading, size in largest:
            print(f"      {size:5d}  ## {heading}")
        print()
    print(
        "Splitting is a judgment call, not an automatic fix: move whole "
        "sections,\nregister each new file in memories/MEMORY.md, and "
        "repoint inbound references."
    )

    report_approaching(approaching, args.max_lines, warn_lines, announce_empty=False)

    if args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
