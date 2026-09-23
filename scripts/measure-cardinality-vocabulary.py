#!/usr/bin/env python3
"""Measure what widening `CARDINALITY_COUNT` past `twelve` costs in precision.

`hooks/flag-uncounted-comment-claims.py` extended its cardinality vocabulary
from `twelve` to `hundred` on 2026-09-23. The justification for doing so
without narrowing any guard is that the wider vocabulary trips the hook on no
MORE of this repository's own commit bodies than the twelve-word one did, so
the widening buys recall at no cost in false positives.

That is a claim about a population, so it belongs in an instrument rather
than in a comment nobody can re-run. This script is that instrument: it
loads the hook, swaps the narrow vocabulary back in, and reports what each
vocabulary finds alongside the size of the population it examined.

    python3 scripts/measure-cardinality-vocabulary.py

THE INVARIANT IS THE SET OF FLAGGED BODIES, AND ONLY THAT SET. A body is
what the hook acts on, so a body newly flagged is a user-visible change and a
set that moves is a real precision regression. Exit status 1 reports that.
The set rather than its size: one body losing its only claim while another
gains its first leaves the COUNT unchanged over a population that moved.

The CLAIM counts are reported too, and are expected to differ. Reporting only
bodies hid that: measured 2026-09-23 against origin/main, both vocabularies
flagged 54 of 111 multi-line bodies while the claim totals were 319 and 325,
so the headline number was structurally blind to every claim the widening
gained or lost inside an already-flagged body. Both directions are worth
seeing, and the LOST ones are the more interesting:

  - A gained claim is a count the narrow vocabulary could not spell.
  - A lost claim is usually a mis-quote the widening CORRECTED. On this
    corpus the single lost claim is `six lines`, which the narrow pattern
    quoted out of `thirty-six lines` -- the exact "surfaced figure the author
    never wrote" failure the hook's own comment describes.

So read a claim delta as information rather than as a verdict, and re-derive
the precision claim in the hook if the body count ever moves.
"""

import argparse
import collections
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

# How many gained and lost claims to quote. Enough to judge a small delta by
# eye; a larger one wants the whole list, which `--all-samples` prints.
SAMPLE = 10


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


def claims_per_body(mod, bodies, vocabulary):
    """The cardinality claims each body yields under `vocabulary`.

    Returns one list of matched texts per body, in `bodies` order, so a
    caller can count bodies, count claims, or diff the texts. Returning the
    texts rather than a total is what lets the caller see a claim gained or
    lost inside a body that was already flagged -- a change no body count can
    represent.
    """
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
        return [
            [text for kind, text in mod.find_claims(b) if kind == "cardinality"]
            for b in bodies
        ]
    finally:
        mod.CARDINALITY_RE = saved


def claim_delta(narrow, wide):
    """Claims the wide vocabulary gained and lost, as flat lists of texts.

    Compared per body with a multiset difference rather than a set one, so a
    body that yields the same text twice under one vocabulary and once under
    the other reports the single instance it actually differs by.
    """
    gained, lost = [], []
    for n, w in zip(narrow, wide):
        cn, cw = collections.Counter(n), collections.Counter(w)
        gained.extend((cw - cn).elements())
        lost.extend((cn - cw).elements())
    return gained, lost


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", default="origin/main",
                    help="git ref whose history supplies the corpus")
    ap.add_argument("--all-samples", action="store_true",
                    help=f"quote every gained and lost claim, not the first {SAMPLE}")
    args = ap.parse_args()

    mod = load_hook()
    bodies = commit_bodies(args.ref)
    multi = [b for b in bodies if len(b.strip().splitlines()) > 1]
    if not multi:
        sys.exit(f"no multi-line commit bodies reachable from {args.ref}")

    narrow = claims_per_body(mod, multi, NARROW)
    wide = claims_per_body(mod, multi, mod.CARDINALITY_COUNT)

    # The SETS, not their sizes. Two different sets of bodies can have the
    # same size -- one body losing its only claim while another gains its
    # first -- so a size comparison would report perfect stability over a
    # population that changed underneath it.
    narrow_set = {i for i, c in enumerate(narrow) if c}
    wide_set = {i for i, c in enumerate(wide) if c}
    newly_flagged = wide_set - narrow_set
    no_longer_flagged = narrow_set - wide_set
    gained, lost = claim_delta(narrow, wide)

    print(f"ref:                 {args.ref}")
    print(f"commits examined:    {len(bodies)}")
    print(f"multi-line bodies:   {len(multi)}")
    print(f"bodies flagged, to twelve:  {len(narrow_set)}")
    print(f"bodies flagged, to hundred: {len(wide_set)}")
    print(f"same bodies under both:     {narrow_set == wide_set}")
    print(f"claims, to twelve:   {sum(len(c) for c in narrow)}")
    print(f"claims, to hundred:  {sum(len(c) for c in wide)}")
    print(f"claims gained:       {len(gained)}")
    print(f"claims lost:         {len(lost)}")

    for label, texts in (("gained", gained), ("lost", lost)):
        if not texts:
            continue
        shown = texts if args.all_samples else texts[:SAMPLE]
        print(f"\n  {label}:")
        for t in shown:
            print(f"    {t!r}")
        if len(shown) < len(texts):
            print(f"    ... and {len(texts) - len(shown)} more (--all-samples)")

    if narrow_set != wide_set:
        print(
            f"\nThe two vocabularies no longer flag the same bodies: "
            f"{len(newly_flagged)} newly flagged, {len(no_longer_flagged)} no "
            "longer flagged. The widening has started costing precision on "
            "this corpus, so re-derive the precision claim in "
            "hooks/flag-uncounted-comment-claims.py.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
