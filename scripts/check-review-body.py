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
The four body-level facts that decide a body's fate, each computed by
`check-pr-fully-clean.py`'s OWN code rather than a copy:

  * whether the checker skips it outright -- an ARD disposition summary, or a
    workflow notice `is_non_review_notice` recognises. The two are reported
    separately as well as combined, because they are different mistakes to
    have made and the combined boolean alone does not say which one fired.
    Both come from the checker: `is_ard_disposition_summary` and
    `is_non_review_notice`. The first was inlined in `check_review_comments`
    until this tool needed it, and was extracted rather than retyped here --
    a copy drifts silently, and the AST guard written to catch that drift
    took six adversarial rounds and still had holes;
  * whether `_is_structured_review_body` reads it as a report -- a report
    heading AND a `Reviewed-Commit:` fingerprint;
  * what `classify_verdict` makes of it: clean, not-clean, unreadable, or no
    verdict at all;
  * which pattern `_unresolved_finding_pattern` matches, quoted.

Those four decide the predicted classification, reported on the
`would classify as` line together with the reason that settled it.

An earlier version of this list named a review-marker check and a
findings-heading pattern instead. Neither is computed here, and the
findings heading is one of the patterns `_unresolved_finding_pattern` folds
together, so neither could be reported separately.

Note what is NOT being said about the marker check, because an earlier
revision of THIS paragraph said it and it is false. `has_review_body_marker`
is not a branch in `check_review_comments`, and it is reached during
admission all the same: `is_non_review_notice` calls it as a precedence
guard, and it decides that function's answer.
Measured -- `Claude Review Dispatched` followed by
`Verdict: Ready for merge` SURVIVES the notice skip, the same notice without
the verdict line is skipped outright, and `has_review_body_marker` is the only
difference to `is_non_review_notice`'s answer. So the reason the marker check
is absent from the list above is that this tool does not compute it, not that
the checker never consults it.

Surviving the skip is not admission, and the distinction matters here rather
than being a quibble. That body is clean and unstructured, so for the non-bot
author this tool models it is DROPPED a few lines later at the clean branch;
only a bot author admits it. Adding the verdict line also flips
`classify_verdict` from nothing to clean, which is why the "only difference"
above is scoped to one function rather than to the outcome.

Documenting a debugging tool as reporting something it does not is the one
docstring error that costs a reader an hour -- and asserting a gate is
unreachable when it decides the case is the one that costs them two.

It reports on the BODY alone. Quorum, identity, per-reviewer supersession and
head-SHA matching are the caller's business and are deliberately out of scope
-- a body can pass every check here and still not clear a PR, and saying so is
better than implying a body-level pass is a merge signal.

USAGE
-----
    python3 scripts/check-review-body.py draft.md
    python3 scripts/check-review-body.py --json draft.md
    cat draft.md | python3 scripts/check-review-body.py -

Exit status: 0 when the body would classify CLEAN; 1 for every other
classification -- NOT-CLEAN, IGNORED, NO-VERDICT and UNREADABLE alike; 2 when
the file cannot be read or the classifier cannot be imported. Only the last is
distinguished, because failing to answer differs in kind from answering "not
clean". The four non-clean outcomes need different fixes from each other and
the exit status does not separate them, so read the `would classify as` line
(or the `verdict` key under `--json`) rather than branching on 1.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

# Appended to the two "blocks nothing" answers when a finding pattern IS
# present. Those answers are right for the non-bot author this tool models and
# wrong for a bot: the bot branch admits with no verdict and no structure test,
# and `check_latest_verdict` then says so in its own words -- "a known-agent
# body with ## Nits and no classifiable verdict line is a standing not-clean,
# not a NOTE". An earlier revision asserted "blocks nothing" unconditionally,
# which told a drafter delegating through `delegate-to-codex` or
# `delegate-to-opencode` -- whose footers are review-agent markers, posted
# under the user's own OWNER account -- that a body vetoing the PR was inert.
BOT_FINDING_CAVEAT = (
    ", and it blocks nothing UNLESS posted under a bot identity or carrying a "
    "review-agent marker, in which case the finding {finding} is a standing "
    "not-clean")

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
    # The checker applies this BEFORE it reaches `is_non_review_notice`.
    ard_summary = bool(mod.is_ard_disposition_summary(body))
    checker_notice = bool(mod.is_non_review_notice(body))
    # Called, not copied. This was the one duplicated literal in the file:
    # the checker inlined its ARD test, so the phrase was retyped here and a
    # test parsed the checker to detect drift. That guard took six adversarial
    # rounds and still had holes -- an `if` relocated past admission, a decoy
    # loop in a nested `def`, `body_lower` rebound to something that is not
    # the body -- each of which broke the skip while the suite stayed green.
    # Extracting `is_ard_disposition_summary` closed all of them at once and
    # deleted the guard, which is the shape `deterministic-tools.md` asks for:
    # dissolve the coupling rather than instrument it.
    #
    # Reported separately as well as combined. They are two different skips
    # with two different remedies, and a single conflated boolean tells a
    # drafter their body is ignored without saying which to fix.
    #
    # Note the asymmetry between them. `is_non_review_notice` carries a
    # precedence guard, so a real review DISCUSSING a notice stays a review.
    # The ARD test has none: it is a bare substring match over the whole
    # lowercased body, with no heading, position or fence test, so a review
    # that merely QUOTES the phrase is skipped too. That is the checker's
    # behaviour rather than this tool's, and it is why the reason string below
    # says the body contains the phrase rather than that it is one.
    notice = ard_summary or checker_notice

    result = {
        "ard_disposition_summary": ard_summary,
        "checker_non_review_notice": checker_notice,
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
    # A THIRD consequence, from the same un-modelled bot gap: the bot branch
    # admits with no verdict and no structure test, so a marker-carrying body
    # with a finding and no readable verdict is a standing not-clean there
    # while it reads UNREADABLE or NO-VERDICT here. The verdict LABELS stay as
    # they are -- this tool models a non-bot author deliberately -- but the
    # `why` strings say so rather than asserting "blocks nothing" flatly.
    #
    # All three are stated because an earlier version gave the conservative
    # divergence its consequence and left the unsafe one implicit -- in the one
    # paragraph whose job is to make the next gap findable. The third was then
    # added by a later commit without being stated, which is the same lapse a
    # second time.
    #
    # Three gates were re-derived across three rounds before this list existed
    # -- `has_review_body_marker` (not a branch here, though the checker does
    # reach it inside `is_non_review_notice`), the
    # missing `unreadable` state, and the ARD skip. Naming the boundary is what
    # makes the next one findable.
    if notice:
        result["verdict"] = "IGNORED"
        result["why"] = (
            "it contains the ARD-disposition phrase, which the checker "
            "skips on a positionless substring match, before it reaches the "
            "notice test" if ard_summary else
            "a non-review notice, which the checker skips")
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
            "its verdict: it clears nothing and counts toward no quorum"
            + (BOT_FINDING_CAVEAT.format(finding=finding) if finding
               else ", and blocks nothing"))
    elif not verdict:
        result["verdict"] = "NO-VERDICT"
        result["why"] = (
            "the classifier states no verdict, so this clears nothing and an "
            "earlier not-clean would keep standing"
            + (BOT_FINDING_CAVEAT.format(finding=finding) if finding
               else ", and it blocks nothing"))
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
        f"  skipped as a notice     : {r['is_non_review_notice']}",
        f"    ARD disposition summary : {r['ard_disposition_summary']}",
        f"    checker notice          : {r['checker_non_review_notice']}",
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
