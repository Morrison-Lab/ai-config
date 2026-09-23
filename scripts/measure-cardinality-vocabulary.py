#!/usr/bin/env python3
"""Measure what widening `CARDINALITY_COUNT` past `twelve` costs in precision.

`hooks/flag-uncounted-comment-claims.py` extended its cardinality vocabulary
from `twelve` to `hundred` on 2026-09-23. The justification for doing so
without narrowing any guard is that the wider vocabulary flags no MORE of
this repository's own commit bodies than the twelve-word one did, so the
widening buys recall at no cost in false positives.

That is a claim about a population, so it belongs in an instrument rather
than in a comment nobody can re-run. This script is that instrument: it
loads the hook, swaps the narrow vocabulary back in, and reports both
counts alongside the size of the population it examined.

    python3 scripts/measure-cardinality-vocabulary.py

A run reports the flagged count under each vocabulary. They are expected to
be equal; a wider count means the widening has started costing precision on
this corpus and the comment in the hook needs re-deriving.
"""

import argparse
import importlib.util
import pathlib
import re
import subprocess
import sys

HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks" / (
    "flag-uncounted-comment-claims.py"
)

# The vocabulary as it stood before the 2026-09-23 widening. Kept here rather
# than reconstructed from the hook, because the point of the comparison is to
# measure against a fixed historical baseline.
NARROW = (
    r"\d[\d,]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|zero"
)


def load_hook():
    spec = importlib.util.spec_from_file_location("flag_uncounted", HOOK)
    if spec is None or spec.loader is None:
        sys.exit(f"cannot load {HOOK}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def commit_bodies(ref):
    """Every commit message reachable from `ref`, NUL-delimited.

    A commit message may contain blank lines, so splitting on anything but a
    NUL would cut one body into several.
    """
    out = subprocess.run(
        ["git", "log", ref, "--format=%x00%B"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [b.strip("\n") for b in out.split("\x00") if b.strip()]


def flagged(mod, bodies, vocabulary):
    """How many bodies yield at least one cardinality claim under `vocabulary`."""
    saved = mod.CARDINALITY_RE
    swapped = saved.pattern.replace(mod.CARDINALITY_COUNT, vocabulary)
    if swapped == saved.pattern and vocabulary != mod.CARDINALITY_COUNT:
        # A substitution that matches nothing reports perfect stability
        # rather than an error, so refuse rather than return a number.
        sys.exit(
            "CARDINALITY_COUNT no longer appears verbatim in CARDINALITY_RE; "
            "this script's substitution would silently measure one vocabulary "
            "twice."
        )
    mod.CARDINALITY_RE = re.compile(swapped, saved.flags)
    try:
        return sum(
            1 for b in bodies
            if any(kind == "cardinality" for kind, _ in mod.find_claims(b))
        )
    finally:
        mod.CARDINALITY_RE = saved


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", default="origin/main",
                    help="git ref whose history supplies the corpus")
    args = ap.parse_args()

    mod = load_hook()
    bodies = commit_bodies(args.ref)
    multi = [b for b in bodies if len(b.strip().splitlines()) > 1]
    if not multi:
        sys.exit(f"no multi-line commit bodies reachable from {args.ref}")

    narrow = flagged(mod, multi, NARROW)
    wide = flagged(mod, multi, mod.CARDINALITY_COUNT)

    print(f"ref:                {args.ref}")
    print(f"commits examined:   {len(bodies)}")
    print(f"multi-line bodies:  {len(multi)}")
    print(f"flagged, to twelve: {narrow}")
    print(f"flagged, to hundred:{wide}")
    if wide != narrow:
        print(
            f"\nThe wider vocabulary flags {wide - narrow} more than the "
            "narrow one. Re-derive the precision claim in "
            "hooks/flag-uncounted-comment-claims.py."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
