#!/usr/bin/env python3
r"""Predict how `check-pr-fully-clean.py` will classify a review body.

WHY THIS EXISTS
---------------
`check-pr-fully-clean.py` decides whether a posted review counts as a clean
verdict, and its rules are strict in ways that are invisible from the outside.
A body can carry `Verdict: Ready for merge`, be posted by the right account,
and still be ignored entirely -- or, worse, be read as NOT clean.

Measured 2026-09-03 on ucdavis/hac.sap#37. Three self-reviews were posted
before one was counted:

  1. Headings, a verdict, no `Reviewed-Commit` line. IGNORED. For a non-bot
     author a clean body must pass `_is_structured_review_body`, which needs a
     report heading AND a fingerprint. The stale `Needs work` from hours
     earlier kept standing, and the PR read not-clean with nothing explaining
     why.
  2. Fingerprint added. COUNTED, and classified NOT CLEAN -- because the body
     had a `## Findings` heading, which `_FINDINGS_HEADING_PATTERN` matches
     whatever the section says beneath it. The section said zero findings.
  3. Heading dropped, `[FINDINGS_COUNT: 0]` used instead. Counted, clean.

Each round cost a comment on a real PR and a re-query. The classifier was two
imports away the whole time, which is `deterministic-tools.md`'s case exactly:
never spend a guess on what an algorithm already decides.

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
import re
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
    """The four body-level questions, plus the verdict they imply."""
    not_clean = []
    for pat in getattr(mod, "VERDICT_NOT_CLEAN_PATTERNS", []):
        if not isinstance(pat, str):
            continue
        m = re.search(pat, body, re.I)
        if m:
            not_clean.append({"pattern": pat, "matched": m.group(0).strip()})

    findings_pat = getattr(mod, "_FINDINGS_HEADING_PATTERN", None)
    findings_m = re.search(findings_pat, body) if findings_pat else None

    clean_hit = any(
        re.search(p, body, re.I)
        for p in getattr(mod, "VERDICT_CLEAN_PATTERNS", [])
        if isinstance(p, str)
    )

    result = {
        "has_review_marker": bool(mod.has_review_body_marker(body)),
        "is_structured_review_body": bool(mod._is_structured_review_body(body)),
        "findings_heading": findings_m.group(0) if findings_m else None,
        "not_clean_matches": not_clean,
        "clean_phrase_present": clean_hit,
    }

    # The order mirrors the checker's own precedence: a body with no marker is
    # never examined; findings and not-clean patterns win over a clean phrase;
    # and a non-bot clean needs the structure the fingerprint provides.
    if not result["has_review_marker"]:
        result["verdict"] = "IGNORED"
        result["why"] = "no review marker, so the scanner never examines it"
    elif not_clean or findings_m:
        result["verdict"] = "NOT-CLEAN"
        result["why"] = (
            "a findings heading matches" if findings_m and not not_clean
            else "a not-clean pattern matches")
    elif not clean_hit:
        result["verdict"] = "NO-VERDICT"
        result["why"] = "no clean phrase, so it neither clears nor blocks"
    elif not result["is_structured_review_body"]:
        result["verdict"] = "IGNORED"
        result["why"] = (
            "clean, but not structured: a non-bot clean body needs a report "
            "heading AND a `Reviewed-Commit:` line")
    else:
        result["verdict"] = "CLEAN"
        result["why"] = "structured, clean, and nothing matches not-clean"
    return result


def render(r):
    lines = [
        f"  review marker present : {r['has_review_marker']}",
        f"  structured report     : {r['is_structured_review_body']}",
        f"  findings heading      : {r['findings_heading'] or 'none'}",
        f"  clean phrase present  : {r['clean_phrase_present']}",
    ]
    if r["not_clean_matches"]:
        lines.append("  not-clean matches     :")
        for m in r["not_clean_matches"]:
            lines.append(f"      {m['matched']!r}  (pattern {m['pattern']})")
    else:
        lines.append("  not-clean matches     : none")
    lines.append("")
    lines.append(f"  would classify as     : {r['verdict']} -- {r['why']}")
    lines.append("")
    lines.append("  Body-level only. Quorum, reviewer identity and head-SHA")
    lines.append("  matching are not checked here; a CLEAN body can still")
    lines.append("  leave a PR not fully clean.")
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
