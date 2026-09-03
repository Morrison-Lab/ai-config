#!/usr/bin/env python3
"""Tests for `check-review-body.py`.

Every positive case is one of the three real bodies posted to
ucdavis/hac.sap#37 on 2026-09-03, in the order they were posted. The tool
earns its keep only if it reproduces that sequence, so those are the cases
that matter; the rest guard the edges.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
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
            "_is_structured_review_body", "is_non_review_notice",
            "is_ard_disposition_summary"):
    check(f"classifier exposes {sym}", hasattr(MOD, sym), True)

# `analyse`'s docstring states this count in prose -- not the module
# docstring, which is where a reader would check first. Pinned rather than
# timestamped, because `FINDING_PATTERNS` is edited whenever a new not-clean
# shape is added and nothing else would notice the prose going stale.
check("the finding-pattern count the docstring states",
      len(MOD.FINDING_PATTERNS), 18)
check("the findings heading is one of them",
      MOD._FINDINGS_HEADING_PATTERN in MOD.FINDING_PATTERNS, True)

# --- the two the delegating version still got wrong ----------------------
# Both were the SAME error as the four before them: a gate re-derived here
# rather than taken from the checker.

# `unreadable` is truthy and is not "not-clean", so it fell through to CLEAN.
# The checker counts it toward no quorum, so the PR reports "No valid clean
# review found" -- a body that BLOCKS reported as clean.
check("an agent body the classifier cannot parse is not clean", verdict(
    f"**Claude finished review**\n\n## Summary\n\nSome notes.\n\n{FINGERPRINT}\n"),
    "UNREADABLE")

# `has_review_body_marker` is not a branch in `check_review_comments`. It is
# still reached during admission, inside `is_non_review_notice`, and this tool
# does not compute it either way -- the point of the case below is the second
# half of that sentence. A
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

# The gate that runs BEFORE the notice skip. Every ARD round posts a
# disposition summary, so a driving session's own round-up must not be read as
# a verdict on its own PR.
check("an ARD disposition summary is skipped, not classified", verdict(
    f"## ARD Review Disposition Summary\n\n## Summary\n\nAll findings "
    f"addressed.\n\n## Verdict\n\nVerdict: Ready for merge\n{FINGERPRINT}\n"),
    "IGNORED")

# A finding blocks only once the item is ADMITTED. The suite's other
# finding-driven case has `classify_verdict == "not-clean"` directly, so it
# never isolated the `or finding` fallback -- which is how an
# admission-independent trigger survived four rounds.
check("a bare finding section with no verdict is not admitted, so it blocks nothing",
      verdict("## Nits\n\n- a small thing\n"), "NO-VERDICT")
check("the same finding inside an ADMITTED clean body does block", verdict(
    f"## Summary\n\nfine\n\n## Nits\n\n- a small thing\n\n## Verdict\n\n"
    f"Verdict: Ready for merge\n{FINGERPRINT}\n"),
    "NOT-CLEAN")

# The `why` string must not claim "blocks nothing" flatly when a finding is
# present: a marker-carrying body IS a standing not-clean in the checker, and
# `delegate-to-codex` / `delegate-to-opencode` post exactly that shape under
# the user's own OWNER account. The label stays UNREADABLE -- this tool models
# a non-bot author on purpose -- but the explanation has to say so.
_marked = "**Claude finished review**\n\n## Nits\n\n- a small thing\n"
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("crb2", TOOL)
_crb = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_crb)
_r = _crb.analyse(_marked, MOD)
check("a marker-carrying finding body is still labelled UNREADABLE",
      _r["verdict"], "UNREADABLE")
check("but its explanation does not claim it blocks nothing",
      "UNLESS posted under a bot identity" in _r["why"], True)
check("and it names the finding that would block",
      "Nits" in _r["why"], True)

# The NO-VERDICT branch carries the same caveat and needs its own probe. All
# three checks above build a MARKER-carrying body, which routes to UNREADABLE
# -- so the NO-VERDICT caveat was unpinned and could be flattened back to the
# false claim with a green suite. Second time in two commits that a case
# exercised the right feature and never isolated the clause under test.
_bare = _crb.analyse("## Nits\n\n- a small thing\n", MOD)
check("a marker-free finding body is NO-VERDICT", _bare["verdict"], "NO-VERDICT")
check("and its explanation carries the caveat too",
      "UNLESS posted under a bot identity" in _bare["why"], True)

# The `structured` conjunct of the admitted-finding branch, which was also
# unpinned -- a clean verdict plus a finding but NO fingerprint. The checker
# never admits an unstructured clean body from a non-bot author, so its finding
# blocks nothing. Third round running that a two-part fix got a probe on one
# part only; the reviewer found this one by mutating every branch condition,
# which is the check worth keeping rather than the case.
check("a clean body with a finding but no fingerprint is not admitted", verdict(
    "## Summary\n\nfine\n\n## Nits\n\n- a small thing\n\n## Verdict\n\n"
    "Verdict: Ready for merge\n"),
    "IGNORED")

# The `else` arms of both caveat ternaries. Cheap, and without them an
# unconditional caveat emits "the finding None is a standing not-clean" on a
# finding-free body with the suite green.
_plain_unreadable = _crb.analyse(
    "**Claude finished review**\n\n## Summary\n\nSome notes.\n"
    f"{FINGERPRINT}\n", MOD)
check("a finding-free UNREADABLE body says blocks nothing, plainly",
      _plain_unreadable["why"].endswith("blocks nothing"), True)
_plain_noverdict = _crb.analyse("## Summary\n\nSome notes on the diff.\n", MOD)
check("a finding-free NO-VERDICT body says blocks nothing, plainly",
      _plain_noverdict["why"].endswith("blocks nothing"), True)

# The `verdict == "clean"` conjunct of the same branch, the last live mutation
# of 25. A STRUCTURED body carrying a finding and a non-clean verdict was a
# combination no probe covered, so `elif structured and finding:` passed green
# -- and would report a drafter's own body as a standing veto on their PR when
# it is not, inverting the distinction BOT_FINDING_CAVEAT exists to preserve.
# `main()` returns 1 either way, so the exit status hides it.
_structured_unreadable = (
    "**Claude finished review**\n\n## Summary\n\nnotes\n\n## Nits\n\n"
    f"- a small thing\n{FINGERPRINT}\n")
check("a STRUCTURED agent body with a finding and no readable verdict",
      verdict(_structured_unreadable), "UNREADABLE")
check("and its caveat arm fires on a structured body too",
      "UNLESS posted under a bot identity"
      in _crb.analyse(_structured_unreadable, MOD)["why"], True)

# --- the call site, which the extraction alone does not cover ------------
# The deleted `ast` guard caught one thing the extraction does not: whether
# the checker still CALLS the helper, ahead of admission. Measured after the
# extraction, deleting the skip outright left both suites green -- so the
# refactor closed the literal-drift problem and traded this away. Restored
# here behaviourally, which is stronger than the guard was: it pins the
# outcome rather than the syntax, so any relocation, gating, or removal that
# admits an ARD summary fails, and any refactor that preserves the skip
# passes.
#
# The checker's OWN suite still does not cover this (754 pass with the helper
# neutered). Filed as Morrison-Lab/ai-config#3122 rather than fixed there,
# since the gap pre-dates this PR.

class _FakeComment:
    def __init__(self, body, login="someuser", assoc="OWNER"):
        self.author_login = login
        self.created_at = "2026-09-03T00:00:00Z"
        self.body = body
        self.author_association = assoc


class _FakePR:
    def __init__(self, comments):
        self.pr_num = "1"
        self.head_sha = "78c3eb0d0e0bb23165225166cfabdb3393876d01"
        self.repo = "o/r"
        self.review_decision = ""
        self.branch = "b"
        self._comments = comments

    def get_comments(self):
        return self._comments

    def get_reviews(self):
        return []


_ARD_NOT_CLEAN = (
    "## ARD Review Disposition Summary\n\n"
    "Addressed findings from review of 78c3eb0d.\n\n"
    "## Verdict\n\nVerdict: Needs work\n"
    "Reviewed-Commit: 78c3eb0d0e0bb23165225166cfabdb3393876d01\n")


def _checker_issues(body):
    # The checker narrates its verdict scan to stdout; silenced so the suite's
    # own output stays readable.
    with contextlib.redirect_stdout(io.StringIO()):
        _, issues = MOD.check_review_comments(_FakePR([_FakeComment(body)]))
    return " | ".join(issues)


# The skip working looks like the checker finding NO review at all.
check("the checker still skips an ARD summary before admitting it",
      "No automated review" in _checker_issues(_ARD_NOT_CLEAN), True)
check("so its quoted verdict never becomes a standing not-clean",
      "NOT clean" in _checker_issues(_ARD_NOT_CLEAN), False)
# Control: the same body without the ARD heading IS admitted, which proves
# the assertion above is reading the skip rather than an empty pipeline.
check("control -- the same body without the ARD heading is admitted",
      "No automated review" in _checker_issues(
          _ARD_NOT_CLEAN.replace("## ARD Review Disposition Summary", "## Round 3")),
      False)

# --- the two skip reasons, reported apart as well as together -----------
# A conflated boolean says a body is ignored without saying which remedy
# applies, so both halves are pinned in isolation. Each case must be positive
# for exactly ONE of them: a pair of assertions that only ever moved together
# would pass under a version that never split them.

def skips(body):
    r = crb.analyse(body, MOD)
    return (r["ard_disposition_summary"], r["checker_non_review_notice"],
            r["is_non_review_notice"])


_ARD = (f"## ARD Review Disposition Summary\n\n## Summary\n\nAll findings "
        f"addressed.\n\n## Verdict\n\nVerdict: Ready for merge\n{FINGERPRINT}\n")
_NOTICE = ("Claude Review Dispatched\n\nThe review workflow has started; "
           "no verdict yet.\n")

check("the extracted helper matches the phrase case-insensitively",
      MOD.is_ard_disposition_summary("## ARD Review Disposition Summary"), True)
check("and does not match an ordinary review",
      MOD.is_ard_disposition_summary("## Summary\n\nAll good.\n"), False)

check("an ARD summary is the ARD skip alone", skips(_ARD), (True, False, True))
check("a workflow notice is the checker skip alone", skips(_NOTICE),
      (False, True, True))
check("an ordinary review is neither skip", skips(
    f"## Summary\n\n`[FINDINGS_COUNT: 0]`\n\n## Verdict\n\n"
    f"Verdict: Ready for merge\n{FINGERPRINT}\n"),
    (False, False, False))

# What a drafter actually reads is `render`'s output, and the assertions above
# pin only the dict. Swapping the two labels behind their values inverts the
# whole diagnostic -- pointing an ARD-heading problem at the notice test --
# and left the suite green, so the rendered lines are pinned too.
check("the ARD sub-line renders under its own label",
      "ARD disposition summary : True" in crb.render(crb.analyse(_ARD, MOD)),
      True)
check("the notice sub-line does not claim the ARD skip fired",
      "ARD disposition summary : False" in crb.render(crb.analyse(_NOTICE, MOD)),
      True)
check("the notice sub-line renders under its own label",
      "checker notice          : True" in crb.render(crb.analyse(_NOTICE, MOD)),
      True)

# The `why` distinguishes them too, since that string is what a drafter reads.
check("the ARD skip names the phrase in its reason",
      "ARD-disposition phrase" in crb.analyse(_ARD, MOD)["why"], True)
check("the ARD reason does not assert the body IS one",
      "is an ARD" in crb.analyse(_ARD, MOD)["why"], False)
check("the notice skip does not mention the ARD skip at all",
      "ARD" in crb.analyse(_NOTICE, MOD)["why"], False)

# The positionless match, stated in the code comment and unasserted until now.
# A review that merely QUOTES the phrase is skipped as well, unlike a review
# that quotes a workflow notice -- which is a real trap for this corpus, whose
# reviews discuss the phrase routinely.
_QUOTES_ARD = (f"## Summary\n\nThe checker skips any body containing "
               f"\"ARD Review Disposition Summary\" outright.\n\n"
               f"## Verdict\n\nVerdict: Ready for merge\n{FINGERPRINT}\n")
check("a review that merely quotes the ARD phrase is skipped too",
      verdict(_QUOTES_ARD), "IGNORED")
check("and its reason does not tell the drafter to rename a heading",
      "heading" in crb.analyse(_QUOTES_ARD, MOD)["why"], False)

if failures:
    print("FAILED:")
    for line in failures:
        print("  " + line)
    sys.exit(1)
print("all tests passed")
