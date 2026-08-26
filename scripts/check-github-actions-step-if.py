#!/usr/bin/env python3
"""Fail if memories/github-actions.md reintroduces a false step-if rule.

GitHub's expression docs (read 2026-08-26) apply a default status check of
``success()`` unless the ``if:`` includes a status-check function
(``success``, ``always``, ``cancelled``, ``failure``).
A non-status condition such as ``if: steps.guard.outputs.blocked != 'true'``
therefore still skips after a failed prior step.
The older heading "Writing any explicit step-level if: REPLACES the default
success()" is false (ai-config#2307).

This check pins three unique needles from that false heading/body/Don't,
and three required phrases from the corrected writeup, so deleting a
finder turns its unique-negative red.

Exit codes (per ``shared/principles/fail-fast.md``):
0 = the memory matches the docs on this point;
1 = a false claim returned, or a required phrase vanished;
2 = the file is missing, so the check could not run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEMORY = ROOT / "memories" / "github-actions.md"

# Unique to the pre-#2307 writeup. The corrected retraction names the older
# claim in different words ("The older claim that *any* explicit step if:
# discards that default is false"), so these needles must not match that
# sentence.
FALSE_CLAIMS = (
    (
        "Writing any explicit step-level",
        "false heading: Writing any explicit step-level if: replaces success()",
    ),
    (
        "silently discards that",
        "false body: a non-status if: silently discards that default",
    ),
    (
        "steps that carry their own",
        "false Don't: skip steps that carry their own if:",
    ),
)

# Unique to the corrected writeup. Dropping any of them is a regression even
# when the false heading stays gone.
REQUIRED = (
    (
        "success() &&",
        "missing recommended success() && (visibility / later failure() copy)",
    ),
    (
        "auto-applies",
        "missing GitHub auto-applies success() unless a status-check function",
    ),
    (
        "status-check function",
        "missing status-check function as the thing that overrides the default",
    ),
)


def findings(text: str) -> list[str]:
    """Return one message per violated invariant."""
    out: list[str] = []
    for needle, message in FALSE_CLAIMS:
        if needle in text:
            out.append(message)
    for needle, message in REQUIRED:
        if needle not in text:
            out.append(message)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "memory",
        nargs="?",
        type=Path,
        default=DEFAULT_MEMORY,
        help="path to github-actions.md (default: memories/github-actions.md)",
    )
    args = parser.parse_args(argv)
    path = args.memory
    if not path.is_file():
        print(f"missing file: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    n_invariants = len(FALSE_CLAIMS) + len(REQUIRED)
    hits = findings(text)
    print(
        f"Examined {n_invariants} invariants on {path}: "
        f"{len(FALSE_CLAIMS)} forbidden, {len(REQUIRED)} required; "
        f"{len(hits)} finding(s)"
    )
    if hits:
        for hit in hits:
            print(hit)
        return 1
    print("github-actions step-if memory matches GitHub's default success().")
    return 0


if __name__ == "__main__":
    sys.exit(main())
