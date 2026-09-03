#!/usr/bin/env python3
r"""Predict how `check-pr-fully-clean.py` will classify a review body.

WHY THIS EXISTS
---------------
`check-pr-fully-clean.py` decides whether a posted review counts as a clean
verdict, and its rules are strict in ways that are invisible from the outside.
A body can carry `Verdict: Ready for merge`, be posted by the right account,
and still be ignored entirely -- or, worse, be read as NOT clean.

Measured 2026-09-03 on ucdavis/hac.sap#37. Three self-reviews were posted
before one counted:

  1. Headings, a verdict, no `Reviewed-Commit` line. IGNORED -- for a non-bot
     author a clean body must pass `_is_structured_review_body`, which needs a
     report heading AND a fingerprint. The stale `Needs work` from hours
     earlier kept standing, and the PR read not-clean with nothing saying why.
  2. Fingerprint added. Still not counted as clean.
  3. Restructured around `[FINDINGS_COUNT: 0]`. Counted, clean.

Note what is NOT claimed about round 2. An earlier version of this docstring
said a `## Findings` heading forced not-clean regardless of its contents. That
is false: `_findings_section_resolves_empty` exists precisely to exempt a
heading whose section says none, and the classifier reads that round-2 body as
CLEAN. The round-2 rejection had another cause, and rather than guess at it a
second time this tool now just asks the classifier.

That is the actual lesson, and it is `deterministic-tools.md`'s: the classifier
was two imports away throughout, and three comments were spent guessing at
rules it would have answered for free.

WHAT IT REPORTS
---------------
The four questions that decide a body's fate, each answered from
`check-pr-fully-clean.py`'s OWN code rather than a copy:

  * does it carry a review marker at all;
  * is it structurally a report (heading plus fingerprint);
  * does anything match the findings-heading pattern;
  * which not-clean patterns match, quoted.

It reports on the BODY alone. Quorum, identity, per-reviewer supersession and
head-SHA matching are the caller's business and are deliberately out of scope
-- a body can pass every check here and still not clear a PR, and saying so is
better than implying a body-level pass is a merge signal.

USAGE
-----
    python3 scripts/check-review-body.py draft.md
    python3 scripts/check-review-body.py --json draft.md
    cat draft.md | python3 scripts/check-review-body.py -

Exit status: 0 when the body would classify CLEAN, 1 when it would classify
not-clean or be ignored, 2 when the file cannot be read or the classifier
cannot be imported. The three are distinct because "would be ignored" and
"would be read as not-clean" need different fixes, and both differ from the
check having failed to answer.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
_CLASSIFIER = os.path.join(_HERE, "check-pr-fully-clean.py")


def load_classifier(path=_CLASSIFIER):
    """Import `check-pr-fully-clean.py` as a module.

    Imported rather than reimplemented, deliberately. A copy of the patterns
    here would drift from the checker the moment either side changed, and a
    predictor that disagrees with the thing it predicts is worse than none --
    it would be trusted.
    """
    spec = importlib.util.spec_from_file_location("_pr_clean", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def analyse(body, mod):
    """Ask the classifier itself, rather than re-deriving its precedence.

    An earlier version reimplemented the decision from the classifier's parts
    -- the pattern lists, the findings-heading regex, the structure test -- and
    got the precedence wrong in four ways, each saying CLEAN where the real
    checker does not. It missed the structured `review-data` payload the
    classifier consults FIRST and the adversarial-reviewer persona is required
    to emit; it modelled neither the clean-qualifier gate (`Ready for merge
    once the tests pass` records NO verdict, so it supersedes nothing) nor the
    bare-pattern marking gate; and it checked one of eighteen finding patterns,
    so a `## Nits` heading -- which vetoes merge under fully-clean.md -- read
    as clean.

    Every one of those is a `check-purpose-before-reusing` failure: the parts
    were reused correctly and the thing they compose was not. Calling
    `classify_verdict` and `_unresolved_finding_pattern` is both correct and
    smaller, and it cannot drift from the checker because it IS the checker.
    """
    verdict = mod.classify_verdict(body)
    finding = mod._unresolved_finding_pattern(body)
    structured = bool(mod._is_structured_review_body(body))
    # The checker skips this BEFORE it reaches `is_non_review_notice`
    # (check-pr-fully-clean.py:2555). Every ARD round posts one of these, per
    # skills/ard/SKILL.md, so a driving session's own summary must not read as
    # a verdict.
    ard_summary = "ard review disposition summary" in body.lower()
    notice = ard_summary or bool(mod.is_non_review_notice(body))

    result = {
        "is_non_review_notice": notice,
        "is_structured_review_body": structured,
        "classifier_verdict": verdict or "none",
        "unresolved_finding_pattern": finding,
    }

    # Ordering follows `check_review_comments`'s admission branches. WHAT IS
    # AND IS NOT MODELLED, stated precisely, because an earlier version of this
    # comment claimed the order was complete and it was not -- which is the
    # worst possible place to overclaim, since a reader checking for a
    # re-derived gate is told by the code itself that none remains.
    #
    # Modelled: the ARD-disposition skip, the notice skip, the fail-closed
    # not-clean branch (admitted from ANY author), and the structure gate.
    #
    # NOT modelled, because they need the comment's metadata rather than its
    # body: whether the author is a bot, and `_reviewer_identity`. The
    # structure gate is therefore applied unconditionally here while the
    # checker applies it only on the non-bot clean branch -- so an UNSTRUCTURED
    # clean body from a bot reads IGNORED here and CLEAN there. That
    # disagreement is deliberate and conservative: this tool is for drafting a
    # body before posting it, where assuming bot privileges you may not have is
    # the direction that misleads.
    #
    # The identity conjunct diverges the OTHER way, and saying so is the point
    # of this paragraph. The checker's clean branch is a three-way conjunction
    # of structure AND `_reviewer_identity(body, login) == login`. A structured
    # clean body whose first or last line carries a review-agent marker, posted
    # under a non-OWNER/MEMBER login, resolves its identity to the AGENT rather
    # than the poster -- so it reads CLEAN here and is DROPPED there.
    # `_reviewer_identity`'s own docstring names the shape: CLI agents like
    # Codex and OpenCode append their marker on the last line. A CLEAN answer
    # from this tool is therefore not a guarantee of admission.
    #
    # Both halves are stated because an earlier version gave the conservative
    # divergence its consequence and left the unsafe one implicit -- in the one
    # paragraph whose job is to make the next gap findable.
    #
    # Three gates were re-derived across three rounds before this list existed
    # -- `has_review_body_marker` (not in the admission path at all), the
    # missing `unreadable` state, and the ARD skip. Naming the boundary is what
    # makes the next one findable.
    if notice:
        result["verdict"] = "IGNORED"
        result["why"] = "a non-review notice, which the checker skips"
    elif verdict == "not-clean":
        # `not-clean` admits from ANY author, fail-closed, so this needs no
        # structure test.
        result["verdict"] = "NOT-CLEAN"
        result["why"] = "the classifier reads this as not-clean"
    elif verdict == "clean" and structured and finding:
        # A finding blocks only once the item is ADMITTED. An earlier version
        # made `finding` an admission-independent trigger, so a bare
        # `## Nits` section with no verdict and no fingerprint reported
        # NOT-CLEAN -- while the real checker never admits it, so it never
        # blocks. Reproduced: `printf '## Nits\n\n- a small thing\n'`.
        result["verdict"] = "NOT-CLEAN"
        result["why"] = f"admitted as clean, but a finding pattern matches: {finding}"
    elif verdict == "unreadable":
        # Explicit, because falling through to CLEAN is what the previous
        # version did. The checker routes this to `unreadable_items`, a NOTE
        # that never sets `latest_verdict`, and filters it out of the
        # per-provider quorum -- so the PR reports "No valid clean review found
        # for HEAD SHA". A body that blocks a merge must never read as clean.
        result["verdict"] = "UNREADABLE"
        result["why"] = (
            "a known review agent posted this and the classifier cannot read "
            "its verdict: it clears nothing, blocks nothing, and counts toward "
            "no quorum")
    elif not verdict:
        result["verdict"] = "NO-VERDICT"
        result["why"] = (
            "the classifier states no verdict, so this neither clears nor "
            "blocks -- an earlier not-clean would keep standing")
    elif not structured:
        result["verdict"] = "IGNORED"
        result["why"] = (
            "clean, but not structured: a non-bot clean body needs a report "
            "heading AND a `Reviewed-Commit:` line")
    else:
        result["verdict"] = "CLEAN"
        result["why"] = "structured, and the classifier reads it as clean"
    return result


def render(r):
    lines = [
        f"  non-review notice       : {r['is_non_review_notice']}",
        f"  structured report       : {r['is_structured_review_body']}",
        f"  classifier verdict      : {r['classifier_verdict']}",
        f"  unresolved finding      : {r['unresolved_finding_pattern'] or 'none'}",
        "",
        f"  would classify as       : {r['verdict']} -- {r['why']}",
        "",
        "  Body-level only. Quorum, reviewer identity and head-SHA matching",
        "  are not checked here; a CLEAN body can still leave a PR not fully",
        "  clean.",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Predict how check-pr-fully-clean.py classifies a review body.")
    ap.add_argument("path", help="file containing the review body, or - for stdin")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--classifier", default=_CLASSIFIER,
                    help="path to check-pr-fully-clean.py")
    args = ap.parse_args(argv)

    try:
        if args.path == "-":
            body = sys.stdin.read()
        else:
            with open(args.path, encoding="utf-8") as fh:
                body = fh.read()
    except OSError as exc:
        print(f"cannot read {args.path}: {exc}", file=sys.stderr)
        return 2

    try:
        mod = load_classifier(args.classifier)
    except Exception as exc:
        print(f"cannot load the classifier ({exc}); not answering", file=sys.stderr)
        return 2

    r = analyse(body, mod)
    print(json.dumps(r, indent=2) if args.json else render(r))
    return 0 if r["verdict"] == "CLEAN" else 1


if __name__ == "__main__":
    sys.exit(main())
