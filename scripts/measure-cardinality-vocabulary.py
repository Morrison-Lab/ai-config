#!/usr/bin/env python3
"""Measure what widening `CARDINALITY_COUNT` past `twelve` costs in precision.

`hooks/flag-uncounted-comment-claims.py` extended its cardinality vocabulary
from `twelve` to `hundred` on 2026-09-23. The justification for doing so
without narrowing any guard is that the wider vocabulary yields a cardinality
claim in no MORE of this repository's own commit bodies than the twelve-word
one did, so the widening buys recall without flagging a body the narrow
vocabulary left alone.

That is a claim about a population, so it belongs in an instrument rather
than in a comment nobody can re-run. This script is that instrument: it
loads the hook, swaps the narrow vocabulary back in, and reports what each
vocabulary finds alongside the size of the population it examined.

    python3 scripts/measure-cardinality-vocabulary.py

IT MEASURES `find_claims`, NOT THE WARNING THE HOOK EMITS. `evaluate()` runs
a discharge step afterwards, so a body counted here may produce no warning at
all: 7 of the 54 flagged bodies discharge under `_derived_in_body(body,
need_count=True)` (measured 2026-09-23 against origin/main). Reaching
`evaluate()` would mean reconstructing each body's originating command, which
the git history does not carry, so the proxy is deliberate -- read a flagged
body as "yields a cardinality claim", never as "warns".

THE INVARIANT IS THE SET OF FLAGGED BODIES, AND ONLY THAT SET. A body is
what the hook acts on, so a set that moves is a population change worth a
human look, and exit status 1 reports that. The set rather than its size:
one body losing its only claim while another gains its first leaves the
COUNT unchanged over a population that moved.

A moved set is not by itself a precision cost, and the exit status does not
claim it is. A body the wide vocabulary flags and the narrow one does not is
the recall gain the widening exists to produce -- the founding case is
exactly that shape -- while a body no longer flagged is a recall loss.
Whether either is a FALSE positive is a judgment this script cannot make, so
it names the direction and asks for the reading rather than announcing a
verdict.

The CLAIM counts are reported too, and are expected to differ. Reporting only
bodies hid that: measured 2026-09-23 against origin/main, both vocabularies
flagged 54 of 111 multi-line bodies while the claim totals were 319 and 325,
so the headline number was structurally blind to every claim the widening
gained or lost inside an already-flagged body. Both directions are worth
seeing, and on this corpus BOTH are false positives rather than recall:

  - All 7 gained claims are positional line references (`fifty lines`,
    `thirty-six lines`, `TWENTY LINES`), which name a location rather than a
    count anyone could have got wrong. So this corpus carries no instance of
    the real miscount the widening was written for, and its recall gain is
    unrepresented here.
  - The single lost claim is `six lines`, which the narrow pattern quoted out
    of `thirty-six lines` -- the exact "surfaced figure the author never
    wrote" failure the hook's own comment describes, so the widening
    corrected it.

So read a claim delta as information rather than as a verdict, and re-derive
the precision claim in the hook if the body set ever moves.
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

# Labels for the two columns. The endpoints are not spelled into them, so a
# later widening past `hundred` does not leave every line naming a vocabulary
# nobody is running.
NARROW_LABEL = "narrow (pre-2026-09-23)"
WIDE_LABEL = "current"

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
    try:
        out = subprocess.run(
            ["git", "log", ref, "--format=%x00%B"],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        # Named rather than raised: an unfetched `origin/main`, or a clone
        # whose remote is not called `origin`, is the DEFAULT state for the
        # reader the hook's comment sends here.
        sys.exit(
            f"cannot read history from {ref!r}: git log exited "
            f"{exc.returncode}. Fetch that ref, or pass --ref."
        )
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

    Compared per body with a multiset difference rather than a set one. That
    is defensive rather than load-bearing: `find_claims` dedupes within a
    body by `(kind, quote.lower())`, so no body can yield the same text
    twice today (measured: 0 of 111) and the Counter difference degenerates
    to a set one on every input the callee can currently produce. It is
    written this way so that removing that dedup does not silently collapse a
    repeated claim to a single instance here.
    """
    gained, lost = [], []
    for n, w in zip(narrow, wide):
        cn, cw = collections.Counter(n), collections.Counter(w)
        gained.extend((cw - cn).elements())
        lost.extend((cn - cw).elements())
    return gained, lost


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--ref", default="origin/main",
                    help="git ref whose history supplies the corpus")
    ap.add_argument("--all-samples", action="store_true",
                    help="quote every gained and lost claim, not the first "
                         f"{SAMPLE}")
    args = ap.parse_args()

    mod = load_hook()
    bodies = commit_bodies(args.ref)
    multi = [b for b in bodies if len(b.strip().splitlines()) > 1]
    if not multi:
        sys.exit(f"no multi-line commit bodies reachable from {args.ref}")

    narrow = claims_per_body(mod, multi, NARROW)
    wide = claims_per_body(mod, multi, mod.CARDINALITY_COUNT)

    # The SETS, not their sizes -- see the module docstring.
    narrow_set = {i for i, c in enumerate(narrow) if c}
    wide_set = {i for i, c in enumerate(wide) if c}
    if not wide_set:
        # Two empty sets compare equal, so a detector that matches nothing
        # reports perfect stability over a population it never examined.
        # The `multi` guard above catches an empty CORPUS; this catches an
        # empty DETECTION, which is what a hook refactor actually produces.
        sys.exit(
            f"no cardinality claim found under EITHER vocabulary over "
            f"{len(multi)} multi-line bodies; the detector rather than the "
            "corpus is the likely cause, so a set comparison here would "
            "report a stability it never measured."
        )
    newly_flagged = wide_set - narrow_set
    no_longer_flagged = narrow_set - wide_set
    gained, lost = claim_delta(narrow, wide)

    # Padded from the labels themselves rather than by hand, so renaming a
    # vocabulary cannot leave the columns ragged.
    rows = [
        ("ref", args.ref),
        ("commits examined", len(bodies)),
        ("multi-line bodies", len(multi)),
        (f"bodies flagged, {NARROW_LABEL}", len(narrow_set)),
        (f"bodies flagged, {WIDE_LABEL}", len(wide_set)),
        ("same bodies under both", narrow_set == wide_set),
        (f"claims, {NARROW_LABEL}", sum(len(c) for c in narrow)),
        (f"claims, {WIDE_LABEL}", sum(len(c) for c in wide)),
        ("claims gained", len(gained)),
        ("claims lost", len(lost)),
    ]
    width = max(len(label) for label, _ in rows) + 2
    for label, value in rows:
        print(f"{label + ':':<{width}}{value}")

    for label, texts in (("gained", gained), ("lost", lost)):
        if not texts:
            continue
        shown = texts if args.all_samples else texts[:SAMPLE]
        print(f"\n  {label}:")
        for t in shown:
            print(f"    {t!r}")
        if len(shown) < len(texts):
            print(f"    ... and {len(texts) - len(shown)} more (--all-samples)")

    if narrow_set == wide_set:
        return 0

    # Named by DIRECTION, because the two mean opposite things and neither is
    # a precision cost this script can establish on its own.
    report = ["\nThe two vocabularies no longer flag the same bodies."]
    if newly_flagged:
        report.append(
            f"{len(newly_flagged)} newly flagged: each is either a real "
            "miscount the wider vocabulary caught -- the recall gain it "
            "exists for -- or a new false positive, which only reading them "
            "settles."
        )
    if no_longer_flagged:
        report.append(
            f"{len(no_longer_flagged)} no longer flagged: the wider "
            "vocabulary lost recall on those bodies."
        )
    report.append(
        "Re-derive the precision claim in "
        "hooks/flag-uncounted-comment-claims.py either way."
    )
    print("\n".join(report), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
