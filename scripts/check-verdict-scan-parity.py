#!/usr/bin/env python3
"""Diff the ACCEPTANCE sets of two revisions of check-pr-fully-clean.py.

Change-time instrument for `strip_cited_finding_vocab` and everything it feeds,
per `memories/mistake-patterns.md` Pattern 15: before shipping a change to a
fail-closed verdict scanner, run the old and new versions over the same
adversarial corpus and diff what each ACCEPTS, rather than reasoning about the
diff.

Why this measures acceptance and not blanking
---------------------------------------------
An earlier version of this proof asked "does every extra blanked character lie
inside a code span the change is meant to blank?" That question cannot fail for
any implementation of that shape: the extra-blanked set IS the span set, so it
reports zero whatever the downstream passes then do with it. Two real fail-opens
lived exactly there -- a collapsed span pulling an anchored negation across a
live finding, and a blanked `**` defeating the quoted-span guard -- and both
scored a clean zero under it (ai-config#2515, review rounds 1-3).

So this tool compares only what the instrument CONCLUDES:

    (classify_verdict(body), _unresolved_finding_pattern(body) is not None)

A WIDENING is any body the base rejects and the candidate accepts. Every
widening needs a justification a human states; the tool does not decide.

Usage
-----
    python3 scripts/check-verdict-scan-parity.py [--base-rev origin/main]
                                                 [--corpus FILE ...]
                                                 [--max-report N]

--corpus takes a JSON array of objects with a "body" key (a harvest of real
review comments), and may be repeated. Generated cases are always included.
Exits 1 if any widening is found, 0 otherwise, so a change with an accepted
widening is expected to be run and read rather than gated on.
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BT = chr(96)


def load_module(path: Path, name: str):
    sys.path.insert(0, str(REPO / "scripts" / "lib"))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rev(rev: str, name: str = "base_checker"):
    """Materialize `rev`'s copy of the checker and import it."""
    src = subprocess.run(
        ["git", "show", f"{rev}:scripts/check-pr-fully-clean.py"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout
    tmp = Path(tempfile.mkdtemp()) / "base_checker.py"
    tmp.write_text(src)
    return load_module(tmp, name)


# Fragments chosen to exercise the axes that have actually produced defects:
# delimiter run length, unclosed runs, odd interior backtick counts (which shift
# consecutive pairing), quote placement, bold finding labels, and negation
# wording near a finding.
DELIMS = ["", BT, BT * 2, BT * 3]
FILLER = ["a.py", "x", f"a {BT}b", f"a {BT}{BT}b", f" {BT} ", ""]
VOCAB = ["Needs more work", "Changes requested", "Blocking", "Rejected",
         "**[Defect]** Needs more work", "**Location:** a.py:1"]
NEGATION = ["", ": none elsewhere.", " No other findings.", " none blocking."]
LEAD = ["", "No ", 'The body says "', "## Nits "]


def generated_bodies():
    seen = set()
    for lead, d1, f1, v, d2, f2, neg in itertools.product(
        LEAD, DELIMS, FILLER, VOCAB, DELIMS, FILLER, NEGATION
    ):
        core = f"{lead}{d1}{f1} {v} {d2}{f2}{neg}"
        for template in (
            "## Verdict: Ready for merge\n\n{core}\n",
            "## Verdict: Ready for merge\n\nReviewed-Commit: abc1234\n\n{core}\n",
            "Verdict: Ready for merge\n\n{core}\n\n### Findings\n\nNone.\n",
            "## Verdict: Ready for merge\n\nSee {a}\n{b} here.\n",
        ):
            body = (
                template.format(a=f"{lead}{d1}{f1}", b=f"{v} {d2}{f2}{neg}")
                if "{a}" in template else template.format(core=core)
            )
            if body not in seen:
                seen.add(body)
                yield body


def classify(module, body):
    return (
        module.classify_verdict(body),
        module._unresolved_finding_pattern(body) is not None,
    )


RANK = {"not-clean": 2, "": 1, "clean": 0}


def is_widening(base_verdict, new_verdict):
    """True when the candidate accepts something the base rejected."""
    return (
        RANK[new_verdict[0]] < RANK[base_verdict[0]]
        or (base_verdict[1] and not new_verdict[1])
    )


VOCAB_RE = __import__("re").compile(
    r"Needs\s+more\s+work|Changes\s+requested|Blocking|Rejected|Unapproved"
    r"|Actionable\s+findings|\*\*Location:\*\*",
    __import__("re").IGNORECASE,
)


def widening_is_on_axis(base, new, body) -> bool:
    """True when a widening is explained by span blanking alone.

    Applied to members of the acceptance-set diff, and precise about WHICH
    occurrence mattered, which the first version of this triage was not: keying
    on "any finding phrase anywhere sits outside a span" flagged thousands of
    bodies whose flip had nothing to do with the phrase it found.

    Two cases, and only one of them can be justified by this change:

    A. The phrase disappeared from the candidate's scan. That is blanking, and
       it is on axis exactly when the phrase sat inside a closed 2+ code span in
       the text the reviewer wrote -- i.e. it really was a citation.

    B. The phrase is still in the candidate's scan and the verdict flipped
       anyway. Then a FILTER changed, not the blanking: a negation window, a
       marking check, the quoted-span guard. This change is only ever supposed
       to blank citations, so every case B is off axis by construction and wants
       a human's eye. Both fail-opens found in review of ai-config#2515 were
       case B or a blanking whose phrase was never in a span.
    """
    from collections import Counter

    from fences import CODE_SPAN_RE

    base_counts = Counter(
        m.group(0).lower()
        for m in VOCAB_RE.finditer(base.strip_cited_finding_vocab(body))
    )
    new_counts = Counter(
        m.group(0).lower()
        for m in VOCAB_RE.finditer(new.strip_cited_finding_vocab(body))
    )
    # Counts, not sets: one line can carry the same phrase twice, once cited
    # inside a span and once live outside it, and a set comparison reports the
    # phrase as still present and calls a legitimate blanking a filter move.
    lost = {
        phrase: base_counts[phrase] - new_counts.get(phrase, 0)
        for phrase in base_counts
        if base_counts[phrase] > new_counts.get(phrase, 0)
    }
    if not lost:
        return False  # case B: nothing was blanked, so a filter moved

    in_span = Counter()
    for line in body.split("\n"):
        spans = [
            m.span() for m in CODE_SPAN_RE.finditer(line)
            if len(m.group(1)) >= 2
        ]
        for occurrence in VOCAB_RE.finditer(line):
            if any(
                start <= occurrence.start() and occurrence.end() <= end
                for start, end in spans
            ):
                in_span[occurrence.group(0).lower()] += 1
    # Every phrase that stopped being counted must be covered by that many
    # occurrences which really were inside a span.
    return all(in_span[phrase] >= count for phrase, count in lost.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-rev", default="origin/main")
    parser.add_argument(
        "--candidate-rev", default="",
        help="Compare a committed revision instead of the working tree. "
             "Use it to confirm the triage FLAGS a revision known to be "
             "fail-open, which is this tool's own negative control.",
    )
    parser.add_argument("--corpus", action="append", default=[])
    parser.add_argument("--max-report", type=int, default=10)
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Cap the generated corpus. For a fast smoke run only: a "
             "capped sweep is not a parity proof.",
    )
    args = parser.parse_args(argv)

    base = load_rev(args.base_rev)
    new = (
        load_rev(args.candidate_rev, "candidate_checker")
        if args.candidate_rev
        else load_module(
            REPO / "scripts" / "check-pr-fully-clean.py", "new_checker"
        )
    )

    corpus = []
    for path in args.corpus:
        for record in json.loads(Path(path).read_text()):
            corpus.append(("real", record["body"]))
    generated = generated_bodies()
    if args.limit:
        generated = itertools.islice(generated, args.limit)
    corpus += [("generated", b) for b in generated]

    widened, narrowed = [], []
    for origin, body in corpus:
        before, after = classify(base, body), classify(new, body)
        if before == after:
            continue
        (widened if is_widening(before, after) else narrowed).append(
            (origin, before, after, body)
        )

    # Negative control, run FIRST: a deliberately over-broad strip must produce
    # divergences. A zero from a detector that never fires is indistinguishable
    # from a zero from a change that never widens.
    import re as _re
    real_strip = new.strip_cited_finding_vocab
    new.strip_cited_finding_vocab = lambda t: _re.sub(r"`[\s\S]*`", " ", t)
    control = sum(
        1 for _, body in corpus if classify(base, body) != classify(new, body)
    )
    new.strip_cited_finding_vocab = real_strip

    print(f"base revision      : {args.base_rev}")
    print(f"bodies examined    : {len(corpus)} "
          f"({sum(1 for o, _ in corpus if o == 'real')} real, "
          f"{sum(1 for o, _ in corpus if o == 'generated')} generated)")
    print(f"negative control   : {control} divergences -> "
          f"{'DISCRIMINATES' if control else 'BLIND, do not trust this run'}")
    on_axis = [w for w in widened if widening_is_on_axis(base, new, w[3])]
    off_axis = [w for w in widened if not widening_is_on_axis(base, new, w[3])]

    print(f"WIDENED  (base rejected, candidate accepts) : {len(widened)}")
    print(f"   on axis  (every finding phrase inside a 2+ span) : {len(on_axis)}")
    print(f"   OFF AXIS (a finding phrase outside every span)   : {len(off_axis)}")
    print(f"NARROWED (candidate rejects, base accepted) : {len(narrowed)}")
    for origin, before, after, body in off_axis[:args.max_report]:
        print(f"  ! [{origin}] {before} -> {after}\n      {body[:200]!r}")
    if len(off_axis) > args.max_report:
        print(f"  ... {len(off_axis) - args.max_report} more off-axis")
    return 1 if off_axis or not control else 0


if __name__ == "__main__":
    sys.exit(main())
