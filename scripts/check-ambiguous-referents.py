#!/usr/bin/env python3
"""Flag sentences carrying several referring expressions as ambiguous-reference candidates.

Morrison-Lab/ai-config, 2026-09-09, manuscript-review session.

`shared/writing/ambiguous-reference.md` already says the check has to be
grammatical rather than semantic -- find the nearest noun phrase before a
pronoun and ask whether it is the intended referent -- and that nothing
decides that mechanically, because "is the nearest antecedent the intended
one" has no decidable condition.  This script does not attempt that
judgment.  It narrows the search instead, per that same fragment's own
positional heuristic: risk concentrates where a sentence already carries
several referring expressions (`it`, `this`, `that`, `these`, `those`, a
comma-`which`), because each one adds a candidate antecedent for every
other one in the same sentence.

A single incident is what motivated it: a drafted sentence carried four
referring expressions -- "that probability", "its complement", "that
interval", and a bare "It is Equation (4)" -- and passed self-review
because each pronoun read fluently on its own.  Self-review reads a
sentence for meaning and stops once it resolves; it does not count how many
referring expressions the sentence is asking it to resolve at once.  A
mechanical count is the check self-review structurally cannot perform.

This is a CANDIDATE finder, not a decider.  It flags a sentence; a human
(or a further pass) still has to read each flagged pronoun against its
nearest antecedent and judge whether that antecedent is the intended one --
exactly the grammatical check the fragment describes.  Advisory only:
always exits 0, and is never run against the corpus in CI.  Its tests do
run there, pinning the measured incident; the checker itself is run by
hand after drafting prose, the way `scripts/check-user-quote.py` is.

Usage:
  python3 scripts/check-ambiguous-referents.py <file> [<file> ...]
  python3 scripts/check-ambiguous-referents.py --threshold 3 <file>
  python3 scripts/check-ambiguous-referents.py --self-test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Whole-word referring expressions this tool counts. Deliberately narrow:
# widening it (e.g. to "they") would need re-measuring the false-positive
# rate against real prose, which this script has not done.
_REFERENT_RE = re.compile(
    r"\b(it|its|this|that|these|those)\b|,\s*which\b", re.IGNORECASE
)

# A rough sentence splitter. Not CommonMark-aware and not abbreviation-aware
# -- this tool is advisory, so an over-split or under-split sentence costs a
# human a moment re-reading a candidate, never a missed defect elsewhere in
# the corpus. Splits on '.', '?', '!' followed by whitespace and a capital
# letter or end of string, which is enough to isolate the sentence a flagged
# referent lives in without needing a full parser.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z]|$)")

# Strip fenced and inline code, which quotes syntax rather than writing
# prose -- the same reasoning strip-non-invoking-markup.sh in Morrison-Lab/gha
# applies to a different matcher.
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def strip_code(text: str) -> str:
    text = _FENCE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    return text


def sentences(paragraph: str) -> list[str]:
    paragraph = " ".join(paragraph.split())
    if not paragraph:
        return []
    return [s for s in _SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]


def find_candidates(text: str, threshold: int = 2) -> list[tuple[str, int]]:
    """Return (sentence, count) for each sentence at or above threshold."""
    text = strip_code(text)
    out: list[tuple[str, int]] = []
    for paragraph in text.split("\n\n"):
        for sent in sentences(paragraph):
            count = len(_REFERENT_RE.findall(sent))
            if count >= threshold:
                out.append((sent.strip(), count))
    return out


def scan_file(path: Path, threshold: int) -> list[tuple[str, int]]:
    return find_candidates(path.read_text(errors="ignore"), threshold)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument(
        "--threshold",
        type=int,
        default=2,
        help="minimum referring expressions in one sentence to flag (default 2)",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not args.files:
        parser.print_usage()
        return 2

    total = 0
    for path in args.files:
        candidates = scan_file(path, args.threshold)
        for sent, count in candidates:
            total += 1
            print(f"{path}: {count} referring expressions in one sentence:")
            print(f"  {sent}")
    print(f"\n{total} candidate sentence(s) examined across {len(args.files)} file(s).")
    print("Advisory only: read each flagged pronoun against its nearest "
          "antecedent (shared/writing/ambiguous-reference.md) before editing.")
    return 0


# --- self-test -------------------------------------------------------------

_KNOWN_BAD = (
    "Integrate over 0 <= t <= a to that probability and to its complement "
    "respectively, so the bracket is itself a probability density on that "
    "interval, and it is Equation (4)."
)

_KNOWN_GOOD_SINGLE = (
    "The log-likelihood is maximized at the same lambda, and it is easier "
    "to work with because the logarithm turns products into sums."
)

_KNOWN_GOOD_NO_REFERENT = (
    "The estimator converges to the true parameter value as sample size "
    "grows, which is the standard consistency result."
)


def run_self_test() -> int:
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        status = "PASS" if cond else "FAIL"
        print(f"{status}: {name}")
        if not cond:
            failures += 1

    # Positive: the actual measured incident sentence must be flagged at the
    # default threshold. This is the sentence containing "that probability",
    # "its complement", "that interval", and "It" -- four referents.
    bad_hits = find_candidates(_KNOWN_BAD, threshold=2)
    check(
        "known-bad sentence (4 referents) is flagged at threshold=2",
        len(bad_hits) == 1 and bad_hits[0][1] == 4,
    )

    # Mutation: raising the threshold above the sentence's own count must
    # stop it being flagged -- confirms the threshold is load-bearing rather
    # than a check that always fires.
    check(
        "known-bad sentence is NOT flagged once threshold exceeds its count",
        len(find_candidates(_KNOWN_BAD, threshold=5)) == 0,
    )

    # Negative control 1: a sentence with exactly one referring expression
    # (the "which" clause-referring case shared/writing/ambiguous-reference.md
    # says is normal here) must not be flagged at the default threshold.
    check(
        "single-referent sentence is not flagged at threshold=2",
        len(find_candidates(_KNOWN_GOOD_SINGLE, threshold=2)) == 0,
    )

    # Negative control 2: a sentence with one clause-referring "which" and no
    # other referent stays quiet too.
    check(
        "clause-referring 'which' alone is not flagged",
        len(find_candidates(_KNOWN_GOOD_NO_REFERENT, threshold=2)) == 0,
    )

    # Code spans and fences must not contribute referents -- a code sample
    # quoting "this that these" is not prose.
    fenced = "Some prose.\n\n```\nthis that these those\n```\n\nMore prose."
    check(
        "fenced code contributes no referents",
        len(find_candidates(fenced, threshold=2)) == 0,
    )

    print(f"\n{failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
