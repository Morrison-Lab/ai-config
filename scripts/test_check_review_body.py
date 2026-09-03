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

# --- the real sequence, and the premise that turned out false -----------

# Round 1: headings and a verdict, no fingerprint. IGNORED -- a non-bot clean
# body must pass `_is_structured_review_body`, which needs heading AND
# fingerprint. This is the round that let a stale not-clean keep standing.
check("no fingerprint is ignored", verdict(
    "## Self-review\n\nAll good here.\n\n**Verdict: Ready for merge.**\n"),
    "IGNORED")

# Round 2 is NOT asserted as not-clean, because it is not. An earlier version
# of this suite pinned that, on the theory that a `## Findings` heading forces
# not-clean whatever its section says. `_findings_section_resolves_empty`
# exists precisely to exempt that shape, and the classifier reads this body as
# clean. Pinned in the true direction so the false premise cannot come back.
check("a Findings heading whose section resolves empty is not a finding",
      verdict(f"## Summary\n\nfine\n\n## Findings\n\nNone. Zero findings.\n\n"
              f"## Verdict\n\nVerdict: Ready for merge\n{FINGERPRINT}\n"),
      "CLEAN")

# Round 3: the body that actually landed.
check("a structured clean body with a zero count classifies clean", verdict(
    f"## Summary\n\nNo actionable items. `[FINDINGS_COUNT: 0]`\n\n"
    f"## Verdict\n\nVerdict: Ready for merge\n{FINGERPRINT}\n"),
    "CLEAN")

# --- the four the first implementation got wrong, all toward CLEAN -------
# Each was measured against the classifier: predictor said CLEAN, checker did
# not. They are the reason this delegates instead of re-deriving precedence.

check("a review-data payload with findings is not clean", verdict(
    f"## Summary\n\nfine\n\n## Verdict\n\nVerdict: Ready for merge\n{FINGERPRINT}\n\n"
    '<!-- review-data:\n{"schema_version":"1.0","reviewer":"adversarial-reviewer",'
    '"commit_sha":"78c3eb0d","verdict":"NOT_CLEAN","findings":[{"file":"a.py",'
    '"line":1,"category":"bug","message":"m"}]}\n-->\n'),
    "NOT-CLEAN")
check("a conditional sign-off states no verdict", verdict(
    f"## Summary\n\nfine\n\n## Verdict\n\n"
    f"Verdict: Ready for merge once the tests pass\n{FINGERPRINT}\n"),
    "NO-VERDICT")
# NO-VERDICT rather than IGNORED. Both expectations here previously encoded
# the re-derived marker gate; with the checker's own admission logic these
# bodies are examined and simply state nothing, which is the accurate answer --
# `classify_verdict` returns '' for each, so neither clears nor blocks.
check("bare prose states no verdict", verdict(
    f"## Summary\n\nI think this is ready for merge, honestly.\n{FINGERPRINT}\n"),
    "NO-VERDICT")
check("a Nits heading with real items vetoes", verdict(
    f"## Summary\n\nfine\n\n## Nits\n\n- a small thing\n\n## Verdict\n\n"
    f"Verdict: Ready for merge\n{FINGERPRINT}\n"),
    "NOT-CLEAN")

# --- edges ---------------------------------------------------------------

check("casual prose states no verdict",
      verdict("Looks fine to me, merging shortly.\n"), "NO-VERDICT")
check("a genuine not-clean is not-clean", verdict(
    f"## Summary\n\ntrouble\n\n## Verdict\n\nVerdict: Needs work\n{FINGERPRINT}\n"),
    "NOT-CLEAN")
# Both spellings, because the classifier blanks code spans before scanning and
# the difference is invisible from the rendered comment. My first version of
# this case asserted NOT-CLEAN for the backticked form and was wrong -- the
# predictor was right and the test was not, which is worth pinning in both
# directions so neither can drift back.
check("a bare nonzero FINDINGS_COUNT is not-clean", verdict(
    f"## Summary\n\n[FINDINGS_COUNT: 3]\n\n## Verdict\n\n"
    f"Verdict: Ready for merge\n{FINGERPRINT}\n"),
    "NOT-CLEAN")
check("the same count inside a code span is blanked, so it is clean", verdict(
    f"## Summary\n\n`[FINDINGS_COUNT: 3]`\n\n## Verdict\n\n"
    f"Verdict: Ready for merge\n{FINGERPRINT}\n"),
    "CLEAN")
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
for sym in ("classify_verdict", "_unresolved_finding_pattern",
            "_is_structured_review_body", "is_non_review_notice"):
    check(f"classifier exposes {sym}", hasattr(MOD, sym), True)

# --- the two the delegating version still got wrong ----------------------
# Both were the SAME error as the four before them: a gate re-derived here
# rather than taken from the checker.

# `unreadable` is truthy and is not "not-clean", so it fell through to CLEAN.
# The checker counts it toward no quorum, so the PR reports "No valid clean
# review found" -- a body that BLOCKS reported as clean.
check("an agent body the classifier cannot parse is not clean", verdict(
    f"**Claude finished review**\n\n## Summary\n\nSome notes.\n\n{FINGERPRINT}\n"),
    "UNREADABLE")

# `has_review_body_marker` is not in the checker's admission path at all. A
# marker-free body carrying a real not-clean signal is admitted from any
# author through the fail-closed branch, and became a standing veto.
check("a marker-free body with a real finding is still not-clean", verdict(
    f"## Summary\n\n[FINDINGS_COUNT: 3]\n\n{FINGERPRINT}\n"),
    "NOT-CLEAN")

# The notice gate, which survived mutation until this case existed. A workflow
# status notice is skipped outright -- and the shape that matters is a notice
# that ALSO carries verdict-ish words, since without the gate it would be
# classified rather than skipped.
check("a workflow status notice is skipped, not classified", verdict(
    "Claude Review Dispatched\n\nThe review workflow has started; "
    "no verdict yet.\n"),
    "IGNORED")
# The precedence the classifier documents: a real review that DISCUSSES a
# notice stays a review. Without it, any review of this corpus quoting
# "Claude Review Dispatched" would be excluded outright.
check("a review that merely mentions a notice is still a review", verdict(
    f"**Claude finished review**\n\n## Summary\n\nThis PR changes how "
    f"`Claude Review Dispatched` notices are handled. "
    f"`[FINDINGS_COUNT: 0]`\n\n## Verdict\n\n"
    f"Verdict: Ready for merge\n{FINGERPRINT}\n"),
    "CLEAN")

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
