#!/usr/bin/env python3
"""Measure what widening `CARDINALITY_COUNT` past `twelve` costs in precision.

THE INVARIANT IS THE SET OF FLAGGED BODIES, AND ONLY THAT SET. A warning
fires per body, so a set that moves is a population change worth a human
look, and exit status 1 reports that. The set rather than its size: one body
losing its only claim while another gains its first leaves the COUNT
unchanged over a population that moved, which is why neither the flagged
count nor the corpus size is the thing being asserted.

`hooks/flag-uncounted-comment-claims.py` extended its cardinality vocabulary
from `twelve` to `hundred` on 2026-09-23, without narrowing any guard. That
is a claim about a population, so it belongs in an instrument rather than in
a comment nobody can re-run. This script is that instrument: it loads the
hook, swaps the narrow vocabulary back in, and reports what each vocabulary
finds alongside the size of the population it examined.

    python3 scripts/measure-cardinality-vocabulary.py

THE SET DOES MOVE, and saying otherwise was this script's own first finding
about itself. Measured 2026-09-24 against origin/main at b96c640f over a
COMPLETE clone: 2753 commits, 2539 multi-line bodies, 677 flagged under the
narrow vocabulary and 680 under the current one, with 3 bodies newly flagged
and none lost. An earlier revision reported 54 of 111 bodies identical under
both -- the same ref, read from a SHALLOW clone of 619 commits, whose
grafted fragment `git log` reports with no warning and exit 0. The truncated
and complete readings disagreed on the one thing this script asserts, so
`commit_bodies` now refuses a shallow clone outright.

Exit status 1 is not that report on its own, though. Eight refusals share it
-- an unloadable hook, a missing `git`, an unreadable history, a shallow
clone, a vocabulary the substitution can no longer find, a NARROW baseline
identical to the live one, an empty corpus, and an empty detection -- each
with its own message, so read the message rather than the status.

IT MEASURES `find_claims`, NOT THE WARNING THE HOOK EMITS. `evaluate()` runs
a discharge step afterwards, so a body counted here may produce no warning at
all: 20 of the 680 flagged bodies discharge under `_derived_in_body(body,
need_count=True)`. Reaching `evaluate()` would mean reconstructing each
body's originating command, which the git history does not carry, so the
proxy is deliberate -- read a flagged body as "yields a cardinality claim",
never as "warns".

A moved set is not by itself a precision cost, and the exit status does not
claim it is. A body the wide vocabulary flags and the narrow one does not is
the recall gain the widening exists to produce; a body no longer flagged is a
recall loss. Whether either is a FALSE positive is a judgment this script
cannot make, so it names the direction and asks for the reading rather than
announcing a verdict.

The body is also the coarser of the hook's two real units. A warning
enumerates the individual claims that produced it, so the claim counts are
not a secondary statistic: they are the finer unit, and a precision claim
stated only at body level says nothing about them. On this corpus the claim
totals are 1937 narrow against 1965 current, 29 gained and 1 lost, and the
two directions read differently:

  - 19 of the 29 gained claims are positional line references (`forty
    lines`, `thirty-six lines`, `TWENTY LINES`), which name a location
    rather than a count anyone could have got wrong. All 3 newly flagged
    bodies are of this kind.
  - The other 10 are counts of things -- `Fourteen markdown files`,
    `Fifteen tests`, `Nineteen of those cases`, `seventeen stale memories`
    -- which is exactly the shape of miscount the widening was written for,
    so the recall gain IS represented on this corpus. Whether each deserved
    a warning is the judgment named above, and 4 of the 29 sit in bodies
    `_derived_in_body` discharges, so those produce no warning under either
    vocabulary.
  - The single lost claim is `six lines`, which the narrow pattern quoted
    out of `thirty-six lines` -- the exact "surfaced figure the author never
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
    """The hook module, or a refusal naming why it could not be imported.

    `spec_from_file_location` returns a populated spec for a path that does
    not exist, so the `spec is None` guard below is not what catches a
    missing or renamed hook -- `exec_module` is, by raising. An earlier
    revision had only that guard, and a missing hook produced an uncaught
    traceback while this script's own docstring promised a refusal message.
    """
    spec = importlib.util.spec_from_file_location("flag_uncounted", HOOK)
    if spec is None or spec.loader is None:
        sys.exit(f"cannot load {HOOK}: no import spec.")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except FileNotFoundError:
        sys.exit(f"cannot load {HOOK}: no such file.")
    except Exception as exc:  # noqa: BLE001 -- re-raised as a refusal
        sys.exit(f"cannot load {HOOK}: {type(exc).__name__}: {exc}")
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
    except FileNotFoundError:
        sys.exit("cannot read history: git is not on PATH.")
    except subprocess.CalledProcessError as exc:
        # git's own stderr is quoted rather than replaced, because the advice
        # this handler can offer covers only the cases it can guess at -- an
        # unfetched `origin/main`, or a clone whose remote is not called
        # `origin`. Run outside a repository at all, git says `not a git
        # repository` and both of those remedies are inapplicable, so
        # dropping its line would substitute a wrong diagnosis for a right
        # one.
        detail = (exc.stderr or "").strip()
        sys.exit(
            f"cannot read history from {ref!r}: git log exited "
            f"{exc.returncode}."
            + (f" git said: {detail}" if detail else "")
            + " Fetch that ref, or pass --ref."
        )
    if is_shallow_clone():
        # The population is the whole point of the comparison, and a shallow
        # clone truncates it silently: `git log` reports the grafted
        # fragment with no warning and exits 0, so every count below is a
        # true statement about a history nobody chose. Measured 2026-09-24,
        # this repository read 619 commits shallow and 2753 unshallowed, and
        # the two disagreed on the one thing the script asserts -- the
        # fragment reported the body sets IDENTICAL under both vocabularies
        # and the full history reported them different. That is the vacuous
        # pass this script's refusals exist to prevent, arriving through the
        # clone rather than through the substitution.
        sys.exit(
            "cannot measure a population from a shallow clone: `git log` "
            "would report the grafted fragment as the whole history. Run "
            "`git fetch --unshallow origin` first."
        )
    return [b.strip("\n") for b in out.split("\x00") if b.strip()]


def is_shallow_clone():
    """Whether this checkout's history is truncated.

    Probed after the log read rather than before it, so a missing `git` or
    an unreadable ref is still reported by the handlers above, which name
    the actual remedy. A `git` too old for `--is-shallow-repository` (before
    2.15) exits non-zero; that reads as not-shallow, which keeps the script
    usable and is the direction that loses only this guard rather than the
    whole measurement.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return out == "true"


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
    if NARROW == mod.CARDINALITY_COUNT:
        # The substitution guard in `claims_per_body` cannot see this case:
        # for the narrow call `vocabulary != mod.CARDINALITY_COUNT` is False,
        # so a no-op substitution passes it. Both columns would then measure
        # one vocabulary twice and report perfect stability -- which is what
        # a REVERT of the widening looks like from here, and is the reading
        # this script exists to make impossible.
        sys.exit(
            "CARDINALITY_COUNT is byte-identical to this script's NARROW "
            "baseline, so there are not two vocabularies to compare. Either "
            "the widening was reverted, or NARROW needs updating to whatever "
            "baseline the comparison is now against."
        )
    bodies = commit_bodies(args.ref)
    multi = [b for b in bodies if len(b.strip().splitlines()) > 1]
    if not multi:
        sys.exit(f"no multi-line commit bodies reachable from {args.ref}")

    narrow = claims_per_body(mod, multi, NARROW)
    wide = claims_per_body(mod, multi, mod.CARDINALITY_COUNT)

    # The SETS, not their sizes -- see the module docstring.
    narrow_set = {i for i, c in enumerate(narrow) if c}
    wide_set = {i for i, c in enumerate(wide) if c}
    if not wide_set and not narrow_set:
        # Two empty sets compare equal, so a detector that matches nothing
        # reports perfect stability over a population it never examined.
        # The `multi` guard above catches an empty CORPUS; this catches an
        # empty DETECTION, which is what a hook refactor actually produces.
        #
        # BOTH sets, because the message asserts about both. Gating on
        # `wide_set` alone fires in the commonest case -- a refactor that
        # breaks the current vocabulary while the hard-coded NARROW literal
        # still works -- and then says something false about the narrow one,
        # while preempting the direction report below, which would have named
        # the loss correctly.
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

    # The vocabulary in force, printed rather than named. `WIDE_LABEL` is
    # deliberately generic so a later widening does not leave every row
    # naming a vocabulary nobody runs, and that genericness removes the one
    # output signal that would show which vocabulary was actually measured.
    print(f"\n  {WIDE_LABEL} vocabulary: {mod.CARDINALITY_COUNT}")

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
            f"{len(no_longer_flagged)} no longer flagged: each is either a "
            "recall loss or a false positive the wider vocabulary corrected "
            "-- this corpus's own `six lines`, quoted out of `thirty-six "
            "lines`, is the second shape -- which only reading them settles."
        )
    report.append(
        "Re-derive the precision claim in "
        "hooks/flag-uncounted-comment-claims.py either way."
    )
    print("\n".join(report), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
