#!/usr/bin/env python3
"""Tests for `check-review-body.py`.

Every positive case is one of the three real bodies posted to
ucdavis/hac.sap#37 on 2026-09-03, in the order they were posted. The tool
earns its keep only if it reproduces that sequence, so those are the cases
that matter; the rest guard the edges.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, "check-review-body.py")

spec = importlib.util.spec_from_file_location("crb", TOOL)
crb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crb)
MOD = crb.load_classifier()

failures = []


def check(label, got, want):
    if got != want:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def verdict(body):
    return crb.analyse(body, MOD)["verdict"]


FINGERPRINT = "Reviewed-Commit: 78c3eb0d0e0bb23165225166cfabdb3393876d01"

# --- the three real bodies, in the order they were posted ----------------

# 1. Headings and a verdict, no fingerprint. Was IGNORED, and the stale
#    not-clean from hours earlier kept standing.
check("round 1: no fingerprint is ignored", verdict(
    "## Self-review\n\nAll good here.\n\n**Verdict: Ready for merge.**\n"),
    "IGNORED")

# 2. Fingerprint added, but a `## Findings` heading saying zero findings.
#    Was COUNTED and classified NOT-CLEAN -- the heading matches whatever
#    the section says beneath it.
check("round 2: a Findings heading reads as not-clean", verdict(
    f"## Summary\n\nfine\n\n## Findings\n\nNone. Zero findings.\n\n"
    f"## Verdict\n\nVerdict: Ready for merge\n{FINGERPRINT}\n"),
    "NOT-CLEAN")

# 3. Heading dropped, `[FINDINGS_COUNT: 0]` instead. Counted, clean.
check("round 3: no Findings heading classifies clean", verdict(
    f"## Summary\n\nNo actionable items. `[FINDINGS_COUNT: 0]`\n\n"
    f"## Verdict\n\nVerdict: Ready for merge\n{FINGERPRINT}\n"),
    "CLEAN")

# --- edges ---------------------------------------------------------------

check("a body with no marker at all is ignored",
      verdict("Looks fine to me, merging shortly.\n"), "IGNORED")
check("a genuine not-clean is not-clean", verdict(
    f"## Summary\n\ntrouble\n\n## Verdict\n\nVerdict: Needs work\n{FINGERPRINT}\n"),
    "NOT-CLEAN")
check("a nonzero FINDINGS_COUNT is not-clean", verdict(
    f"## Summary\n\n`[FINDINGS_COUNT: 3]`\n\n## Verdict\n\n"
    f"Verdict: Ready for merge\n{FINGERPRINT}\n"),
    "NOT-CLEAN")
check("a marker but no verdict phrase yields NO-VERDICT", verdict(
    f"## Summary\n\nSome notes on the diff.\n\nverdict: pending\n{FINGERPRINT}\n"),
    "NO-VERDICT")
# A zero count must NOT read as findings -- the checker's own pattern is
# `[1-9]\d*`, and a tool that got this backwards would send every clean
# review back for a rewrite.
check("FINDINGS_COUNT 0 does not trip the not-clean pattern", verdict(
    f"## Summary\n\n`[FINDINGS_COUNT: 0]`\n\n## Verdict\n\n"
    f"Verdict: Ready for merge\n{FINGERPRINT}\n"),
    "CLEAN")

# --- exit statuses -------------------------------------------------------

def run(body, *extra):
    return subprocess.run([sys.executable, TOOL, "-", *extra], input=body,
                          capture_output=True, text=True, timeout=60)


_clean = (f"## Summary\n\nfine `[FINDINGS_COUNT: 0]`\n\n## Verdict\n\n"
          f"Verdict: Ready for merge\n{FINGERPRINT}\n")
check("clean exits 0", run(_clean).returncode, 0)
check("not-clean exits 1", run("## Summary\n\n## Verdict\n\nVerdict: Needs work\n"
                               + FINGERPRINT).returncode, 1)
check("an unreadable classifier exits 2",
      subprocess.run([sys.executable, TOOL, "-", "--classifier", "/nonexistent.py"],
                     input=_clean, capture_output=True, text=True,
                     timeout=60).returncode, 2)
check("a missing file exits 2",
      subprocess.run([sys.executable, TOOL, "/nonexistent/draft.md"],
                     capture_output=True, text=True, timeout=60).returncode, 2)
check("--json emits parseable JSON",
      __import__("json").loads(run(_clean, "--json").stdout)["verdict"], "CLEAN")

# --- the anti-drift property --------------------------------------------
# The whole point is that this reads the checker's OWN symbols. If it ever
# reimplements them, this fails.
for sym in ("VERDICT_NOT_CLEAN_PATTERNS", "VERDICT_CLEAN_PATTERNS",
            "_FINDINGS_HEADING_PATTERN", "_is_structured_review_body",
            "has_review_body_marker"):
    check(f"classifier exposes {sym}", hasattr(MOD, sym), True)

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
