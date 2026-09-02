#!/usr/bin/env python3
"""Check that `## Pattern N:` headings in memories/mistake-patterns.md are unique and sequential.

The pattern number is a value the file itself determines -- the next integer
after the last heading -- and every PR that appends an entry types it by hand
against the `main` it branched from. Two PRs branched from the same `main`
therefore both claim the same number, each correctly, and the merged file
carries a duplicate heading (or, after one is renumbered by hand, a gap). On
2026-09-01 three open PRs each appended `## Pattern 42`
(Morrison-Lab/ai-config#2946). Per shared/workflow/algorithmatize-checks.md
this is a decidable property of one file, so it belongs in an instrument that
runs on the merged result rather than in a merge-time reminder.

Checks, in order:
  1. every `## Pattern N:` / `## Pattern Nx:` heading is distinct;
  2. the integer parts run 1, 2, ..., K in file order with no gap;
  3. a lettered sub-pattern (`5b`, `5c`, ...; the file's existing scheme for
     entries filed under an earlier number) follows its base entry directly
     and its letters run b, c, ... in order.

Headings that are not `## Pattern ...:` are ignored: the file carries one
un-numbered `## ` section (at the time of writing) and this check has no
opinion about it.

Exit codes:
  0  all pattern headings unique and sequential (the examined count is printed)
  1  a duplicate, a gap, or an out-of-order number was found
  2  the file could not be read

Usage:
  python3 scripts/check-mistake-patterns.py [PATH]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "memories" / "mistake-patterns.md"
PATTERN_HEADING = re.compile(r"^## Pattern (\d+)([a-z]?):")


def pattern_numbers(text: str) -> List[Tuple[int, int, str]]:
    """Return (line_number, N, suffix) for every `## Pattern N[x]:` heading, in file order."""
    out = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = PATTERN_HEADING.match(line)
        if m:
            out.append((lineno, int(m.group(1)), m.group(2)))
    return out


def find_problems(numbers: List[Tuple[int, int, str]]) -> List[str]:
    """Describe every duplicate, gap, out-of-order number, or misplaced letter; empty when clean."""
    problems = []
    seen = {}
    for lineno, n, suffix in numbers:
        key = f"{n}{suffix}"
        if key in seen:
            problems.append(
                f"line {lineno}: Pattern {key} duplicates the heading at line {seen[key]}"
            )
        else:
            seen[key] = lineno
    base = 0          # the integer of the most recent entry
    letter = ""       # its suffix ("" for the base entry itself)
    for lineno, n, suffix in numbers:
        key = f"{n}{suffix}"
        if seen.get(key) != lineno:
            continue  # a duplicate, already reported
        if not suffix:
            if n != base + 1:
                problems.append(
                    f"line {lineno}: Pattern {n} follows Pattern {base}{letter}; "
                    f"expected Pattern {base + 1} (numbers run 1..K in file order with no gap)"
                )
            # Track the highest base seen, so one misplaced heading is reported
            # once rather than making every heading after it read as wrong too.
            if n > base:
                base, letter = n, ""
            continue
        expected_letter = "b" if not letter else chr(ord(letter) + 1)
        if n != base or suffix != expected_letter:
            problems.append(
                f"line {lineno}: Pattern {key} follows Pattern {base}{letter}; "
                f"a lettered sub-pattern must be Pattern {base}{expected_letter}"
            )
            continue
        letter = suffix
    return problems


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="?", default=str(DEFAULT_PATH))
    args = parser.parse_args(argv)
    path = Path(args.path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    numbers = pattern_numbers(text)
    problems = find_problems(numbers)
    for p in problems:
        print(f"{path}: {p}")
    if problems:
        print(f"FAIL: {len(problems)} problem(s) across {len(numbers)} pattern heading(s)")
        return 1
    print(f"OK: {len(numbers)} pattern heading(s) unique and sequential in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
