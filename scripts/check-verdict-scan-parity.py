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
import re
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
    result = subprocess.run(
        ["git", "show", f"{rev}:scripts/check-pr-fully-clean.py"],
        cwd=REPO, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"cannot read scripts/check-pr-fully-clean.py at '{rev}': "
            f"{result.stderr.strip()}\n"
            "A shallow or single-branch checkout will not have origin/main; "
            "fetch it, or pass --base-rev with a revision this clone has."
        )
    src = result.stdout
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
         "**[Defect]** Needs more work", "**Location:** a.py:1",
         # ai-config#2668's two mechanisms, absent from this corpus when that
         # change first ran the tool -- its zero was a coverage statement.
         # These five new entries (two here, two in NEGATION, one in LEAD)
         # roughly double the sweep, since the product crosses every list
         # with every other: 338,688 raw combinations before, 688,128
         # after. Kept, because dropping them makes the instrument quieter
         # rather than better; the runtime is tracked as ai-config#2702.
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**)",
         "round-2 blocking findings (x overclaim, y.qmd caption) are "
         "resolved by this round's diff"]
NEGATION = ["", ": none elsewhere.", " No other findings.", " none blocking.",
            " is still there; nothing fixed.", " remains open.",
            " still stands.", " must be fixed before merge."]
LEAD = ["", "No ", 'The body says "', "## Nits ", "The previously-blocking ",
        "> ", "## ", "In response to [round 6](https://x) "]
# Marker-only span contents. BARE_CLEAN_MARKED accepts [ \t] and [#>*_+-], so a
# span holding only one of those decides whether a bare rejection counts as
# marked -- a shape the first version of this corpus could not generate at all,
# which is why its "0 off axis" was a coverage statement rather than a result.
FILLER_EXTRA = ["-", "#", ">", "_", "+", "a.py:10", "**Location:**", "[Defect]"]


# Structured `review-data` payload bodies (ai-config#2736).  A SEPARATE,
# bounded arm rather than new entries in the lists above, because those are
# crossed with every other list and one more entry roughly doubles the sweep
# (the runtime cost VOCAB's own comment already records, tracked as #2702).
#
# `main` appends this arm AFTER `--limit` is applied, so every body here is
# always examined.  Neither placement inside `generated_bodies` works: yielded
# last, the first payload body sat at index 241,920 and no hand-run limit
# reached it; yielded FIRST, `--limit`'s STRIDED sample (see its comment in
# `main`) still selected roughly one of the 57.  Both reported a zero that was
# a coverage statement -- the exact trap this arm exists to close, twice.
#
# The corpus carried no payload fragment when #2736 first ran this tool, so its
# "0 widened" was a coverage statement -- the same failure VOCAB's comment
# records for #2668.  These bodies cross the three axes a payload can be wrong
# on: WHERE it sits (bare, fenced, unclosed-fence, code span, indented block),
# WHICH of several payloads is authoritative (a quoted template before the real
# one), and whether its verdict and its findings AGREE.
# ACCEPTED WIDENING, stated here because this tool's docstring requires a human
# to state one and nothing else in the repo will surface it (the tool is not in
# `validate.yml`). Against `origin/main` this arm reports one OFF-AXIS widening:
#
#   ('unreadable', False) -> ('clean', False)
#   '**Claude finished** review\n\nReviewed-Commit: abc1234\n\n<!-- review-data: {"verdict": "CLEAN", "findings": []} -->\n'
#
# That is the feature, not a regression: a review whose ONLY verdict is a
# structured payload used to be `unreadable` (a known agent in a format the
# classifier could not parse) and now reads as the clean verdict it states.
# It is accepted on three grounds -- the payload must be unfenced, unquoted and
# whitespace-prefixed only; it must carry an explicit empty `findings` list, so
# a payload omitting the key still cannot clear; and `classify_verdict` checks
# every prose not-clean pattern BEFORE consulting it, so prose findings still
# win.
#
# The arm also produces five NARROWINGS, all intended and all fail-closed:
# a payload carrying findings now blocks whatever its verdict string says
# (four of them, two from `clean` and two from `unreadable`), and a `findings`
# field present but not a list blocks rather than clearing (one).
#
# So this tool exits 1 on this branch, which is its documented read-and-justify
# mode rather than a gate ("Exits 1 if any widening is found ... so a change
# with an accepted widening is expected to be run and read rather than gated
# on"). It is not in `validate.yml`, so nothing else will surface it.
_P_CLEAN = '<!-- review-data: {"verdict": "CLEAN", "findings": []} -->'
_P_BLOCK = ('<!-- review-data: {"verdict": "NOT_CLEAN", "findings": '
            '[{"file": "a.py", "message": "boom"}]} -->')
_P_CONTRADICT = ('<!-- review-data: {"verdict": "CLEAN", "findings": '
                 '[{"file": "a.py", "message": "boom"}]} -->')
# `findings` present but not a list: must block, never clear.
_P_MALFORMED = ('<!-- review-data: {"verdict": "CLEAN", "findings": '
                '"3 defects listed above"} -->')
# No `findings` key at all: the verdict alone decides.
_P_NO_FINDINGS = '<!-- review-data: {"verdict": "CLEAN"} -->'

PAYLOAD_PLACEMENTS = {
    "bare": "{p}",
    "fenced": "```json\n{p}\n```",
    "unclosed-fence": "```json\n{p}",
    "code-span": "the schema is `{p}` appended last",
    "indented": "    {p}",
}


def payload_bodies():
    """Bodies exercising the structured-payload path, in every placement."""
    for payload in (_P_CLEAN, _P_BLOCK, _P_CONTRADICT):
        for placement in PAYLOAD_PLACEMENTS.values():
            rendered = placement.format(p=payload)
            for verdict_line in ("## Verdict: Ready for merge",
                                 "## Verdict: Needs more work"):
                yield (f"**Claude finished** review\n\n{verdict_line}\n\n"
                       f"Reviewed-Commit: abc1234\n\n{rendered}\n")
    # A quoted template BEFORE the reviewer's own payload: the authoritative
    # one is last, so first-match-wins inverts the verdict.
    for real in (_P_BLOCK, _P_CLEAN):
        yield ("**Claude finished** review\n\n"
               f"The template reads {_P_CLEAN} and you append your own.\n\n"
               "## Verdict: Needs more work\n\nReviewed-Commit: abc1234\n\n"
               f"{real}\n")

    # NO prose verdict line, deliberately. `classify_verdict` decides on the
    # prose scan before control reaches `payload_is_clean`, so every body above
    # -- each of which carries an explicit `## Verdict:` line -- leaves the only
    # acceptance-WIDENING branch unreached, and a zero from them alone is a
    # coverage statement rather than a result. These bodies are the ones that
    # can turn a base rejection into `clean`, so they are what makes the arm an
    # instrument.
    for payload in (_P_CLEAN, _P_BLOCK, _P_CONTRADICT, _P_MALFORMED, _P_NO_FINDINGS):
        for placement in PAYLOAD_PLACEMENTS.values():
            yield ("**Claude finished** review\n\n"
                   "Reviewed-Commit: abc1234\n\n"
                   f"{placement.format(p=payload)}\n")


def generated_bodies(exhaustive=False):
    seen = set()

    if exhaustive:
        leads, vocabs, negs = LEAD, VOCAB, NEGATION
    else:
        # Fast default tier: include the baseline, the negation guards, quote placement,
        # and complex finding shapes, while dropping redundant variations.
        leads = [LEAD[0], LEAD[1], LEAD[2], LEAD[6]]
        vocabs = [VOCAB[0], VOCAB[4], VOCAB[5]]
        negs = [NEGATION[0], NEGATION[2], NEGATION[5]]

    for lead, d1, f1, v, d2, f2, neg in itertools.product(
        leads, DELIMS, FILLER + FILLER_EXTRA, vocabs, DELIMS, FILLER, negs
    ):
        core = f"{lead}{d1}{f1} {v} {d2}{f2}{neg}"
        for template in (
            "## Verdict: Ready for merge\n\n{core}\n",
            "## Verdict: Ready for merge\n\nReviewed-Commit: abc1234\n\n{core}\n",
            "Verdict: Ready for merge\n\n{core}\n\n### Findings\n\nNone.\n",
            "## Verdict: Ready for merge\n\n## Findings\n\nNone.\n{core}\n",
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


# classify_verdict returns four values, not three: "unreadable" is what a body
# from a known agent in an unparsed format yields. Omitting it raised KeyError
# on exactly the input this tool is meant to be run on -- a --corpus of real
# review comments. It ranks with "" : neither states a verdict, and neither is
# an acceptance.
RANK = {"not-clean": 2, "unreadable": 1, "": 1, "clean": 0}


def is_widening(base_verdict, new_verdict):
    """True when the candidate accepts something the base rejected."""
    return (
        RANK[new_verdict[0]] < RANK[base_verdict[0]]
        or (base_verdict[1] and not new_verdict[1])
    )


def _normalize(text: str) -> str:
    """Collapse whitespace, so a scan whose inner spans were blanked still
    compares against the original span content it came from."""
    return " ".join(text.split()).lower()


def span_contents(body: str):
    """Contents of every closed 2+ backtick code span, scanned independently.

    Deliberately NOT the module's own mask. The point of the triage is to check
    the mask machinery -- the fence handling, and the offset carried through
    four substitutions -- against a computation that shares none of it.
    """
    from fences import CODE_SPAN_RE
    contents = []
    for line in body.split("\n"):
        for match in CODE_SPAN_RE.finditer(line):
            run = len(match.group(1))
            if run >= 2:
                contents.append(_normalize(match.group(0)[run:-run]))
    return contents


def ignored_matches(new, body):
    """Every match the candidate's citation filter suppresses, with offsets."""
    scan, mask = new.strip_cited_finding_vocab_with_mask(body)
    patterns = list(new.VERDICT_NOT_CLEAN_PATTERNS) + list(new.FINDING_PATTERNS)
    suppressed = []
    for pattern in patterns:
        for match in re.finditer(pattern, scan, re.IGNORECASE | re.MULTILINE):
            if new.match_is_cited(mask, match.start(), match.end()):
                suppressed.append((match.start(), match.end()))
    return scan, mask, suppressed


def independent_mask(new, body) -> bytearray:
    """Recompute the citation mask WITHOUT the module's own carrying code.

    The module threads its mask through four substitutions and a fence strip.
    That carrying is where an off-by-one would hide, and comparing the module's
    mask against itself would never show one. So this rebuilds the mask from
    the other end: tag each source offset that lies in a 2+ span, then run the
    same pipeline over a parallel string in which tagged offsets carry a
    sentinel, and read the sentinel positions out of the result.

    Uses the module's own pipeline on purpose -- what is being cross-checked is
    the OFFSET BOOKKEEPING, not the span definition, so the span scan here is
    independent while the transformations deliberately are not.
    """
    from fences import CODE_SPAN_RE

    tagged = bytearray(len(body))
    per_line = bytearray(len(body))
    offset = 0
    for line in body.split("\n"):
        for match in CODE_SPAN_RE.finditer(line):
            if len(match.group(1)) >= 2:
                begin, finish = match.span()
                per_line[offset + begin:offset + finish] = b"\x01" * (finish - begin)
        offset += len(line) + 1
    for match in CODE_SPAN_RE.finditer(body):
        if len(match.group(1)) >= 2:
            begin, finish = match.span()
            for i in range(begin, finish):
                tagged[i] = per_line[i]
    return tagged


def widening_is_on_axis(new, body) -> bool:
    """True when a widening is explained by the citation filter alone.

    Two ways to fail:

    A. The candidate suppressed no match at all, yet its verdict changed. Then
       something OTHER than the filter moved -- a negation window, a marking
       check, a sentence gate, the quoted-span guard. That is off axis by
       construction, and it is what four rounds of review kept finding.

    B. It suppressed a match at offsets the module's mask claims are cited but
       an independent span scan does not agree on. Checked by OFFSET rather
       than by matching the suppressed TEXT against span contents: the text
       test could neither see a mask extended past its span onto a live finding
       elsewhere in the body, nor tell that apart from a correct suppression
       whose inner single-backtick span had already been blanked.
    """
    scan, mask, suppressed = ignored_matches(new, body)
    if not suppressed:
        return False
    source = independent_mask(new, body)
    # Every masked run in the scan must correspond to a masked run in the
    # source, and there are never more masked characters than the source has.
    if sum(mask) > sum(source):
        return False
    return all(
        end > start and all(mask[start:end]) for start, end in suppressed
    )


class ReachAssertionError(ValueError):
    """Raised when a generator arm or sampling branch produces zero cases."""
    pass


def assert_arm_reach(arm_counts: dict[str, int]) -> None:
    """Verify that every generator arm or sampling branch produced >= 1 case.

    A sampling instrument's zero is a coverage statement unless the reach of
    every arm is verified (Pattern 32). Zero cases on any generator arm means
    the run cannot establish parity.
    """
    zero_arms = [name for name, count in arm_counts.items() if count <= 0]
    if zero_arms:
        raise ReachAssertionError(
            f"Generator arm reach assertion failed: {', '.join(zero_arms)} "
            f"produced 0 cases (cannot establish parity with 0 coverage)"
        )


def build_corpus(
    args: argparse.Namespace,
    generator_arms: dict[str, callable] | None = None,
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """Assemble corpus from all arms and verify reach."""
    arm_counts: dict[str, int] = {}
    corpus: list[tuple[str, str]] = []

    if getattr(args, "corpus", None):
        real_bodies = []
        for path in args.corpus:
            for record in json.loads(Path(path).read_text()):
                real_bodies.append(record["body"])
        arm_counts["real"] = len(real_bodies)
        corpus.extend([("real", b) for b in real_bodies])

    if generator_arms is None:
        # Default generator arms: prose combinatorics and structured payloads
        prose = list(generated_bodies(getattr(args, "exhaustive", False)))
        limit = getattr(args, "limit", 0)
        if limit and limit < len(prose):
            # Strided, not a prefix. The generator varies its last fragment fastest,
            # so a contiguous head shares one leading fragment throughout and is a
            # biased sample -- measured: the first 8,000 bodies contain no shape the
            # negative control can even detect, so a capped run reported itself
            # blind. A stride spreads the sample across the product space.
            # Index by a fractional step rather than a slice stride. An integer
            # stride collapses to 1 for any limit above half the corpus, which
            # silently degenerates to exactly the contiguous prefix the comment
            # above says was measured to leave the negative control blind.
            step = len(prose) / limit
            prose = [prose[int(i * step)] for i in range(limit)]
        arm_counts["prose"] = len(prose)
        corpus.extend([("generated", b) for b in prose])

        # AFTER the limit, unconditionally: the payload arm is bounded (57 bodies)
        # and every one of them must be examined on every run, including a capped
        # smoke run. See `payload_bodies`'s own comment for the two placements
        # inside `generated_bodies` that each silently dropped it.
        payload = list(payload_bodies())
        arm_counts["payload"] = len(payload)
        corpus.extend([("generated", b) for b in payload])
    else:
        for name, arm_gen in generator_arms.items():
            bodies = list(arm_gen(args))
            arm_counts[name] = len(bodies)
            corpus.extend([("generated", b) for b in bodies])

    assert_arm_reach(arm_counts)
    return corpus, arm_counts


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
        "--exhaustive", action="store_true",
        help="Generate the exhaustive product instead of a fast default tier.",
    )
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

    try:
        corpus, arm_counts = build_corpus(args)
    except ReachAssertionError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    # THE primary invariant, checked before anything else. Every fail-open the
    # four rejected designs produced was a downstream pass reading text
    # origin/main would not have produced. If the scan is byte-identical, that
    # entire class is unreachable, and the acceptance diff below is then
    # attributable to the citation filter alone.
    scan_mismatches = [
        body for _, body in corpus
        if new.strip_cited_finding_vocab(body)
        != base.strip_cited_finding_vocab(body)
    ]

    widened, narrowed = [], []
    for origin, body in corpus:
        before, after = classify(base, body), classify(new, body)
        if before == after:
            continue
        (widened if is_widening(before, after) else narrowed).append(
            (origin, before, after, body)
        )

    # Negative control. Printed first because it decides whether to believe
    # the rest; computed here, after the sweep it qualifies. A deliberately
    # over-broad strip must produce
    # divergences. A zero from a detector that never fires is indistinguishable
    # from a zero from a change that never widens.

    # Patch the function the finding scans actually call. An earlier version
    # patched strip_cited_finding_vocab, which the mask refactor took off that
    # path -- so the control silently measured nothing and reported a healthy
    # number only because the two revisions differed anyway. CI caught it; a
    # local run did not, because locally the revisions were never identical.
    real_strip = new.strip_cited_finding_vocab_with_mask

    def _greedy(text):
        stripped = re.sub(r"`[\s\S]*`", " ", text)
        return stripped, bytearray(len(stripped))

    new.strip_cited_finding_vocab_with_mask = _greedy
    control = sum(
        1 for _, body in corpus if classify(base, body) != classify(new, body)
    )
    new.strip_cited_finding_vocab_with_mask = real_strip

    print(f"base revision      : {args.base_rev}")
    print(f"bodies examined    : {len(corpus)} "
          f"({sum(1 for o, _ in corpus if o == 'real')} real, "
          f"{sum(1 for o, _ in corpus if o == 'generated')} generated)")
    arm_summary = ", ".join(f"{name}={count}" for name, count in arm_counts.items())
    print(f"arm reach counts   : {arm_summary}")
    print(f"negative control   : {control} divergences -> "
          f"{'DISCRIMINATES' if control else 'BLIND, do not trust this run'}")
    on_axis = [w for w in widened if widening_is_on_axis(new, w[3])]
    off_axis = [w for w in widened if not widening_is_on_axis(new, w[3])]

    scan_note = (
        "  <== the change edits the scan; every downstream pass is exposed"
        if scan_mismatches else ""
    )
    print(f"scan identity      : {len(scan_mismatches)} bodies whose scan text "
          f"differs from {args.base_rev}'s{scan_note}")
    print(f"WIDENED  (base rejected, candidate accepts) : {len(widened)}")
    print(f"   on axis  (every finding phrase inside a 2+ span) : {len(on_axis)}")
    print(f"   OFF AXIS (a finding phrase outside every span)   : {len(off_axis)}")
    print(f"NARROWED (candidate rejects, base accepted) : {len(narrowed)}")
    for origin, before, after, body in off_axis[:args.max_report]:
        print(f"  ! [{origin}] {before} -> {after}\n      {body[:200]!r}")
    if len(off_axis) > args.max_report:
        print(f"  ... {len(off_axis) - args.max_report} more off-axis")
    return 1 if off_axis or scan_mismatches or not control else 0


if __name__ == "__main__":
    sys.exit(main())
