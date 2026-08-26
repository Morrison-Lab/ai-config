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

  1,200 lines of memory prose is roughly 12k tokens -- a defensible ceiling
  for a file an agent may read whole. It also sits just above the largest
  file ai-config#694's split produced (`github-actions.md`, ~1,066 lines),
  so the corpus starts green with real but finite headroom. The value is a
  parameter rather than a literal per
  `shared/coding/configurable-parameters.md`.

WHAT "ADVISORY" DOES AND DOES NOT MEAN HERE
-------------------------------------------
Read this before concluding the cap is soft. THIS SCRIPT is advisory. The
CORPUS is gated, from `test_check_memory_file_size.py`, whose final assertion
calls `oversized_files("memories", DEFAULT_MAX_LINES)` on the live tree and
exits 1 on any finding -- so a `validate` run goes red at "Run
memory-file-size check tests", never at the step that runs this file. A PR
that appends past 1200 lines cannot merge; it has to split first.
A file already AT the cap cannot take a net-positive append either.
Recover lines (re-wrap or drop) or split, rather than adding lines.
Folding a sentence into an existing bullet still adds a source line.
Measured 2026-08-25 on memories/preferences.md in ai-config#2262:
origin/main was exactly 1200 lines. A +5-line append failed
scripts/test_check_memory_file_size.py.

The two statements are consistent and read as contradictory, which is why
they are stated together: the advisory exit keeps THIS check from blocking an
unrelated PR over a file it did not touch, while the test keeps the shipped
default honest. `shared/workflow/batch-merge-and-resolve.cases.md` records an
instance of the misreading, and `shared/writing/semantic-line-breaks.md` says
it in one line: read the test suite itself, not this docstring.

Advisory by default: always exits 0 unless `--strict` is passed. A memory
file crossing a line count is a prompt to consider splitting, not a defect
that should block an unrelated PR -- the same stance the repo's other
advisory check takes (the diff-scoped semantic-line-break check, which
started here as `scripts/check-new-line-breaks.py` and now runs from
`d-morrison/gha`'s reusable workflow per gha#300 / ai-config#703), and the
one `shared/writing/semantic-line-breaks.md` prescribes for style findings.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MAX_LINES = 1200

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
    findings = []
    for rel_path in tracked_memory_files(directory):
        lines = (REPO_ROOT / rel_path).read_text(encoding="utf-8").splitlines()
        if len(lines) > max_lines:
            findings.append((rel_path, len(lines), section_sizes(lines)[:5]))
    return sorted(findings, key=lambda f: -f[1])


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
        "--strict",
        action="store_true",
        help="exit 1 if any file is over the threshold (default: advisory, exits 0)",
    )
    args = parser.parse_args()

    findings = oversized_files(args.directory, args.max_lines)

    if not findings:
        print(f"No memory file exceeds {args.max_lines} lines.")
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

    if args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
