#!/usr/bin/env python3
"""Regression and unit tests for scripts/check-pr-fully-clean.py.

Tests:
1. CI check run status filtering (completed with success/neutral/skipped vs in_progress/failure).
2. Review comment parsing (clean verdict vs finding pattern matching).
3. Formal GitHub review parsing with empty top-level comments (state: CHANGES_REQUESTED vs APPROVED/COMMENTED).
4. Review prose containing modifier variations like "No major changes requested".
5. Robust handling of None author objects in review payloads.
"""
import importlib.util
import json
from unittest.mock import patch
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "checker", Path(__file__).parent / "check-pr-fully-clean.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

# Deliberately NOT Morrison-Lab/ai-config. A test run against this repo's own
# name passes under both the hardcoded and the parameterized version, so it
# would be vacuous -- the population holds no positive instance of the class it
# is supposed to catch (Morrison-Lab/ai-config#1243).
TEST_REPO = "octocat/example"
HARDCODED = "Morrison-Lab/ai-config"

passes = 0
failures = 0


class CmdRecorder:
    """Stand in for run_cmd, recording every argv it is handed.

    The recorded argv is what makes the repo-threading testable at all: the
    defect was in which repository a command NAMED, which no return value
    reveals.
    """

    def __init__(self, result: str = "{}"):
        self.result = result
        self.calls = []

    def __call__(self, cmd):
        self.calls.append(list(cmd))
        return self.result

    @property
    def flat(self) -> str:
        return " ".join(" ".join(c) for c in self.calls)


def check(name: str, condition: bool):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def main() -> int:
    print("Testing check-pr-fully-clean.py...")

    clean_comment = {
        "createdAt": "2026-08-05T18:14:14Z",
        "body": "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\nEverything looks great! No issues found.\n\nReviewed HEAD sha123.\n\nVerdict: Clean / Ready for merge."
    }

    findings_comment = {
        "createdAt": "2026-08-05T18:14:37Z",
        "body": "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\nReviewed HEAD sha123.\n\n## Actionable Findings\n\n### 1. Link Syntax Error\n**Location:** memories/tools.md:L843"
    }

    formal_changes_requested_review = {
        "submittedAt": "2026-08-05T18:20:00Z",
        "body": "",
        "state": "CHANGES_REQUESTED",
        "commit": {"oid": "sha123"}
    }

    no_major_changes_comment = {
        "createdAt": "2026-08-05T18:14:14Z",
        "body": "### \ud83e\udd16 Antigravity Agent Report\n\nReviewed HEAD sha123.\n\nNo major changes requested. Everything looks clean and ready for merge."
    }

    none_author_review = {
        "submittedAt": "2026-08-05T18:14:14Z",
        "body": "### \ud83e\udd16 Code Review\n\nLooks clean.",
        "state": "COMMENTED",
        "author": None,
        "commit": {"oid": "sha123"}
    }

    human_approved_review = {
        "submittedAt": "2026-08-05T18:14:14Z",
        "body": "LGTM, thanks!",
        "state": "APPROVED",
        "author": {"login": "d-morrison"},
        "commit": {"oid": "sha123"}
    }

    # Test 1: Clean review comment returns True
    mock_clean_data = json.dumps({"comments": [clean_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_clean_data):
        clean_ok, clean_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("clean review comment passes check_review_comments", clean_ok and clean_issues == [])

    # Test 2: Findings review comment returns False
    mock_findings_data = json.dumps({"comments": [findings_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_findings_data):
        findings_ok, findings_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("findings review comment fails check_review_comments", not findings_ok and len(findings_issues) > 0)

    # Test 3: Formal review with empty comments list and CHANGES_REQUESTED state fails
    mock_formal_review_data = json.dumps({"comments": [], "reviews": [formal_changes_requested_review]})
    with patch.object(checker, "run_cmd", return_value=mock_formal_review_data):
        formal_ok, formal_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("formal CHANGES_REQUESTED review with empty comments fails check_review_comments", not formal_ok and len(formal_issues) > 0)

    # Test 4: Review with 'No major changes requested' passes check_review_comments
    mock_no_major_data = json.dumps({"comments": [no_major_changes_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_no_major_data):
        no_major_ok, no_major_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("review with 'No major changes requested' passes check_review_comments", no_major_ok and no_major_issues == [])

    # Test 5: Payload with None author in reviews does not raise (reaching the
    # check at all proves no exception), and a None-author review is NOT admitted
    # as automated -- author identity, not the bot-looking body, is what qualifies
    # a review as automated (round 12). A deleted-account (None-author) review
    # cannot be confirmed automated, so it fails criterion 2 (fail-closed).
    mock_none_author_data = json.dumps({"comments": [], "reviews": [none_author_review]})
    with patch.object(checker, "run_cmd", return_value=mock_none_author_data):
        none_author_ok, none_author_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("None-author review handled safely and not admitted as automated",
              (not none_author_ok) and any("No automated review" in i for i in none_author_issues))

    # Test 6: Plain human APPROVED review without bot review fails criterion 2
    mock_human_data = json.dumps({"comments": [], "reviews": [human_approved_review]})
    with patch.object(checker, "run_cmd", return_value=mock_human_data):
        human_ok, human_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("human APPROVED review without bot review fails criterion 2", not human_ok and any("No automated review" in i for i in human_issues))

    # Regression: a bot-authored review comment that omits the HEAD SHA is now
    # accepted when its "View run" link resolves to a run whose head_sha matches
    # the target (#1520, #1213). The run proves the reviewer was dispatched
    # against this commit.
    stale_no_sha_comment = {
        "createdAt": "2026-08-05T18:30:00Z",
        "body": "### \ud83e\udd16 Antigravity Agent Report\n\nEverything looks great.\n\nVerdict: Clean / Ready for merge.\n\n[View run](https://github.com/test/repo/actions/runs/99999)",
        "author": {"login": "claude[bot]"},
    }
    mock_pr_data = json.dumps({"comments": [stale_no_sha_comment], "reviews": []})
    mock_run_data = json.dumps({"head_sha": "sha123", "event": "push", "head_branch": "main"})
    with patch.object(checker, "run_cmd", side_effect=[mock_pr_data, mock_run_data]):
        stale_ok, stale_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("bot comment without SHA accepted when run head_sha matches (#1520)",
              stale_ok and stale_issues == [])

    # New: a bot comment without SHA must be rejected when its run's head_sha
    # does NOT match the target.
    mock_pr_data2 = json.dumps({"comments": [stale_no_sha_comment], "reviews": []})
    mock_run_data2 = json.dumps({"head_sha": "other_sha", "event": "push", "head_branch": "main"})
    with patch.object(checker, "run_cmd", side_effect=[mock_pr_data2, mock_run_data2]):
        stale_no_match_ok, stale_no_match_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("bot comment without SHA rejected when run head_sha does not match",
              (not stale_no_match_ok) and len(stale_no_match_issues) > 0)

    # New: a workflow_dispatch run with head_branch matching the PR branch is
    # accepted (dispatcher passed explicit --ref).
    mock_pr_data_disp = json.dumps({"comments": [stale_no_sha_comment], "reviews": []})
    mock_run_data_disp = json.dumps({"head_sha": "sha123", "event": "workflow_dispatch", "head_branch": "my-branch"})
    with patch.object(checker, "run_cmd", side_effect=[mock_pr_data_disp, mock_run_data_disp]):
        disp_ok, disp_issues = checker.check_review_comments("1167", "sha123", TEST_REPO, branch="my-branch")
        check("workflow_dispatch run with matching head_branch is accepted",
              disp_ok and disp_issues == [])

    # New: a workflow_dispatch run with head_branch NOT matching the PR branch
    # is rejected (dispatcher defaulted to main, head_sha is unreliable).
    mock_pr_data_disp2 = json.dumps({"comments": [stale_no_sha_comment], "reviews": []})
    mock_run_data_disp2 = json.dumps({"head_sha": "sha123", "event": "workflow_dispatch", "head_branch": "main"})
    with patch.object(checker, "run_cmd", side_effect=[mock_pr_data_disp2, mock_run_data_disp2]):
        disp_no_ok, disp_no_issues = checker.check_review_comments("1167", "sha123", TEST_REPO, branch="my-branch")
        check("workflow_dispatch run with non-matching head_branch is rejected",
              (not disp_no_ok) and len(disp_no_issues) > 0)

    # New: a bot comment without SHA and without a run link must be rejected.
    no_link_comment = {
        "createdAt": "2026-08-05T18:30:00Z",
        "body": "### \ud83e\udd16 Antigravity Agent Report\n\nVerdict: Clean / Ready for merge.",
        "author": {"login": "claude[bot]"},
    }
    mock_pr_data3 = json.dumps({"comments": [no_link_comment], "reviews": []})
    with patch.object(checker, "run_cmd", side_effect=[mock_pr_data3]):
        no_link_ok, no_link_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("bot comment without SHA and without run link is rejected",
              (not no_link_ok) and len(no_link_issues) > 0)

    # New: a non-bot comment without SHA must still require SHA in the body,
    # even when a matching run exists.
    human_no_sha = {
        "createdAt": "2026-08-05T18:30:00Z",
        "body": "Looks good to me!",
        "author": {"login": "d-morrison"},
    }
    mock_pr_data4 = json.dumps({"comments": [human_no_sha], "reviews": []})
    with patch.object(checker, "run_cmd", side_effect=[mock_pr_data4]):
        human_after_ok, human_after_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check("non-bot comment without SHA rejected even with matching run",
              (not human_after_ok) and len(human_after_issues) > 0)

    # Regression (round 12): a plain human formal review whose body merely
    # contains an automated-review marker phrase ("verdict:", "code review", ...)
    # must NOT satisfy criterion 2 on its own. Reviews carry a real commit.oid, so
    # once admitted they attribute to HEAD with no body check -- admission must
    # therefore key on author identity, never body content. Two independent
    # phrasings, both colliding with a marker, from a non-bot author.
    human_marker_verdict = {
        "submittedAt": "2026-08-05T18:14:14Z",
        "body": "My verdict: this looks great, ship it!",
        "state": "COMMENTED",
        "author": {"login": "d-morrison"},
        "commit": {"oid": "sha123"},
    }
    mock_hmv = json.dumps({"comments": [], "reviews": [human_marker_verdict]})
    with patch.object(checker, "run_cmd", return_value=mock_hmv):
        hmv_ok, hmv_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "human review whose body contains 'verdict:' does not satisfy criterion 2",
            (not hmv_ok) and any("No automated review" in i for i in hmv_issues),
        )

    human_marker_codereview = {
        "submittedAt": "2026-08-05T18:14:14Z",
        "body": "Thanks for the code review process improvements here, LGTM overall.",
        "state": "APPROVED",
        "author": {"login": "d-morrison"},
        "commit": {"oid": "sha123"},
    }
    mock_hmc = json.dumps({"comments": [], "reviews": [human_marker_codereview]})
    with patch.object(checker, "run_cmd", return_value=mock_hmc):
        hmc_ok, hmc_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "human APPROVED review whose body contains 'code review' does not satisfy criterion 2",
            (not hmc_ok) and any("No automated review" in i for i in hmc_issues),
        )

    # Regression (#1202): a CLEAN verdict that merely quotes finding vocabulary
    # inside a code span or double-quotes must NOT be read as raising a finding.
    # Both were live false positives on PRs about the review tooling itself.

    # #1160: clean verdict quoting `**Location:**` inside an inline code span.
    location_codespan_clean = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": (
            "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD sha123.\n\n"
            "Ready for merge. No new findings. The gha#412 inline tag examples "
            "use `**Location:** [file.py:L12]`.\n\nVerdict: Clean / Ready for merge."
        ),
    }
    mock_loc = json.dumps({"comments": [location_codespan_clean], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_loc):
        loc_ok, loc_issues = checker.check_review_comments("1160", "sha123", TEST_REPO)
        check(
            "clean verdict quoting `**Location:**` in a code span passes (#1202)",
            loc_ok and loc_issues == [],
        )

    # #1167: clean verdict discussing "Needs more work" in double quotes.
    needs_work_quoted_clean = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": (
            "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD sha123.\n\n"
            "Ready for merge. No new findings. This PR improves the "
            "`finding_patterns` coverage of \"Needs more work\" verdicts."
        ),
    }
    mock_nwq = json.dumps({"comments": [needs_work_quoted_clean], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_nwq):
        nwq_ok, nwq_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "clean verdict quoting \"Needs more work\" in double quotes passes (#1202)",
            nwq_ok and nwq_issues == [],
        )

    # Positive control (#1202): a REAL bold `**Location:**` finding label, with no
    # findings heading, must still be detected -- proving the strip removes cited
    # vocabulary only, not genuine (unquoted, uncode-spanned) finding labels.
    location_real_finding = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": (
            "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD sha123.\n\n"
            "**Location:** memories/tools.md:L843 -- broken link syntax."
        ),
    }
    mock_locreal = json.dumps({"comments": [location_real_finding], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_locreal):
        locreal_ok, locreal_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "real bold **Location:** finding (not quoted) still fails the check (#1202)",
            (not locreal_ok) and len(locreal_issues) > 0,
        )

    # Adversarial (#1231 review): a genuine `**Location:**` finding that happens
    # to fall inside a double-quoted span on the same line must still be detected.
    # The strip preserves a quoted span carrying a bold finding label, so blanking
    # it cannot silently hide a real finding (the unsafe direction).
    quoted_real_finding = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": (
            "### 🤖 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD sha123.\n\n"
            "He said \"hi. **Location:** foo.py:1 -- bug\" and left."
        ),
    }
    mock_qrf = json.dumps({"comments": [quoted_real_finding], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_qrf):
        qrf_ok, qrf_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "genuine **Location:** inside a double-quoted span is still detected (#1231 review)",
            (not qrf_ok) and len(qrf_issues) > 0,
        )

    # Adversarial (#1567): an unclosed fence must NOT swallow subsequent text to EOF,
    # ensuring a genuine finding after an unclosed code block is still detected.
    unclosed_fence_finding = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": (
            "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD sha123.\n\n"
            "```python\n"
            "def foo():\n"
            "    pass\n\n"
            "**Location:** foo.py:1 -- real bug after unclosed fence."
        ),
    }
    mock_uff = json.dumps({"comments": [unclosed_fence_finding], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_uff):
        uff_ok, uff_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "genuine finding after unclosed fence is still detected (#1567)",
            (not uff_ok) and len(uff_issues) > 0,
        )

    # --- Criterion 4: the latest verdict-bearing statement (#1275) ---------
    # Unit-level classification first, so a failure below is attributable.
    check(
        "classify_verdict: 'Needs more work' is not-clean",
        checker.classify_verdict("Round 2: **Needs more work** -- 8 findings.") == "not-clean",
    )
    check(
        "classify_verdict: 'Ready for merge' is clean",
        checker.classify_verdict("Verdict: Clean / Ready for merge.") == "clean",
    )
    check(
        "classify_verdict: a long verification section with no verdict is NEITHER",
        checker.classify_verdict(
            "### Verification\n\nI re-derived every figure. The counts agree. "
            "Every one of the eight items checks out.\n\nNot merging."
        ) == "",
    )
    check(
        "classify_verdict: a QUOTED 'Needs more work' is not a verdict (#1202 strip)",
        checker.classify_verdict(
            "Ready for merge. This PR widens coverage of \"Needs more work\" verdicts."
        ) == "clean",
    )
    # A bold-labeled citation of a PAST verdict's SHA, in the exact shape
    # from ai-config#1752 that #1760 fixes. Neither the code-span nor the
    # quote handling touches this -- there are no quotes, and stripping the
    # backticks first would hide the SHA gate this relies on.
    check(
        "classify_verdict: a bold-plus-SHA PAST-verdict citation is not a "
        "verdict (#1760 strip, verbatim #1752 shape)",
        checker.classify_verdict(
            "The one finding from the previous review round "
            "(**Needs more work**, reviewed at `53f9acbf`) is now Addressed."
            "\n\n### Verdict\n**Ready for merge** -- no new issues found."
        ) == "clean",
    )
    # #1762's finding 1: an EARLIER version of this gate keyed only on
    # citation-shaped WORDING co-occurring anywhere in the parenthetical, and
    # blanked the WHOLE span -- so a genuine, still-unaddressed finding that
    # mentions "the previous round" in its own text was silently erased
    # along with the citation. The bold span here is NOT immediately
    # followed by "reviewed at `sha`" (it's followed by ordinary prose), so
    # the tightened adjacency-based gate must leave it alone.
    check(
        "classify_verdict: a LIVE finding mentioning 'the previous round' "
        "in its own text is NOT erased (#1762 round-1 finding regression test)",
        checker.classify_verdict(
            "### Verdict\n**Ready for merge**\n\n"
            "(**Needs more work:** src/a.py:10 was flagged in the previous "
            "round and is still unfixed)"
        ) == "not-clean",
    )
    # #1762's round-2 finding: the adjacency-only gate (no resolution-wording
    # requirement) ALSO regressed -- a still-unresolved finding re-raised
    # across rounds naturally cites the commit it was first flagged at, in
    # the identical "**bold**, reviewed at `sha`" syntax as a genuinely
    # resolved citation. Only the trailing prose ("is now Addressed" vs "is
    # still present") distinguishes the two.
    check(
        "classify_verdict: a LIVE finding using the SAME citation syntax as "
        "a resolved one, but with 'still present/unaddressed' wording, is "
        "NOT erased (#1762 round-2 finding regression test)",
        checker.classify_verdict(
            "The one finding from the previous review round "
            "(**Needs more work**, reviewed at `53f9acbf`) is still present "
            "and unaddressed in this diff."
            "\n\n### Verdict\n**Ready for merge** -- no new issues found."
        ) == "not-clean",
    )
    check(
        "classify_verdict: 'has been fixed' is also recognized as "
        "resolution wording, not just 'is now Addressed'",
        checker.classify_verdict(
            "The prior finding (**Needs more work**, reviewed at "
            "`abc1234`) has been fixed in this round."
            "\n\nVerdict: Ready for merge."
        ) == "clean",
    )
    check(
        "classify_verdict: a bold-in-parens finding with NO citation wording "
        "is still a real finding (#1760 safety direction)",
        checker.classify_verdict(
            "Found an issue (**Location:** foo.py:42) that still needs "
            "fixing. Needs more work before merge."
        ) == "not-clean",
    )
    check(
        "classify_verdict: a bold-in-parens finding citing a SHA that is NOT "
        "immediately adjacent to 'reviewed at' is still a real finding "
        "(#1760/#1762 safety direction)",
        checker.classify_verdict(
            "Found a regression (**Bug:** off-by-one, introduced in "
            "`abc1234`). Needs more work."
        ) == "not-clean",
    )
    check(
        "classify_verdict: 'reviewed' elsewhere in the sentence, not "
        "adjacent to the bold span, does not trigger the strip",
        checker.classify_verdict(
            "(**Bug:** foo.py:10) -- this was reviewed at length and still "
            "needs more work."
        ) == "not-clean",
    )
    check(
        "classify_verdict: findings win over a clean line in the same body",
        checker.classify_verdict("Ready for merge. But: Needs more work on the tests.") == "not-clean",
    )
    # A bare clean phrase survives intact inside a sentence that says the
    # opposite. Classifying one of these as clean would let it supersede a
    # standing "Needs more work" -- the exact failure criterion 4 exists to
    # stop, arriving through the check meant to stop it (found by the round-1
    # review of this PR, #1278). Negations sit BEFORE the phrase, conditions
    # AFTER it, so both sides are exercised.
    #
    # The primary guard is POSITION though, not this vocabulary: a bare phrase
    # counts only where the comment marks it as the verdict. The unmarked
    # cases below pin that, and they are what makes the word lists a second
    # line rather than the only one.
    check(
        "classify_verdict: 'not ready for merge' states NO clean verdict",
        checker.classify_verdict(
            "This PR is not ready for merge until the two remaining findings are fixed."
        ) == "",
    )
    check(
        "classify_verdict: 'still not approved for merge' states NO clean verdict",
        checker.classify_verdict("Still not approved for merge; two findings remain.") == "",
    )
    check(
        "classify_verdict: 'not yet ready for merge' (two words between) is NOT clean",
        checker.classify_verdict("It is not yet ready for merge.") == "",
    )
    check(
        "classify_verdict: a CONDITIONAL 'ready for merge once ...' is NOT clean",
        checker.classify_verdict(
            "Ready for merge once the following items are addressed: the two nits above."
        ) == "",
    )
    check(
        "classify_verdict: 'approved for merge pending CI' is NOT clean",
        checker.classify_verdict("Approved for merge pending a green CI run.") == "",
    )
    # NEGATIVE CONTROLS -- the guard must not swallow a genuine sign-off, or
    # criterion 4 never passes and the gate becomes unusable.
    check(
        "classify_verdict: a plain 'Ready for merge' is still clean",
        checker.classify_verdict("### Verdict\n\n**Ready for merge** -- all findings fixed.") == "clean",
    )
    check(
        "classify_verdict: a negated mention does not veto a genuine verdict elsewhere",
        checker.classify_verdict(
            "Round 1 said it was not ready for merge.\n\n### Verdict\n\n**Ready for merge**"
        ) == "clean",
    )
    check(
        "classify_verdict: 'Verdict: Ready' needs no guard (adjacency already binds it)",
        checker.classify_verdict("Verdict: Ready") == "clean",
    )
    check(
        "classify_verdict: 'Verdict: Not Ready' is not clean",
        checker.classify_verdict("Verdict: Not Ready") == "",
    )
    # Adversative connectors, which the round-1 word lists missed entirely.
    # Note two of them separate the qualifier with a comma or a dash rather
    # than a space, so a whitespace-only anchor does not see it.
    check(
        "classify_verdict: 'Ready for merge, but not until ...' is NOT clean",
        checker.classify_verdict(
            "Ready for merge, but not until it addresses the following: item A, item B."
        ) == "",
    )
    check(
        "classify_verdict: 'Ready for merge -- however, ...' is NOT clean",
        checker.classify_verdict(
            "Ready for merge -- however, two items still need attention first."
        ) == "",
    )
    check(
        "classify_verdict: 'Ready for merge except for ...' is NOT clean",
        checker.classify_verdict("Ready for merge except for the two remaining items below.") == "",
    )
    check(
        "classify_verdict: a hedged 'Almost ready for merge' is NOT clean",
        checker.classify_verdict(
            "Almost ready for merge; still needs the following two items addressed."
        ) == "",
    )
    # POSITION, the primary guard. An unmarked mention mid-sentence is not a
    # verdict however friendly its wording, and this is the case no vocabulary
    # list would ever have reached.
    check(
        "classify_verdict: an unmarked mid-sentence mention is NOT a verdict",
        checker.classify_verdict(
            "I mentioned it was ready for merge in passing, mid-sentence."
        ) == "",
    )
    check(
        "classify_verdict: a heading-marked verdict IS clean",
        checker.classify_verdict("### Ready for merge") == "clean",
    )
    # The NOT-CLEAN list needs the same negation handling the clean list has,
    # and it needs it per-list rather than per-pattern. Widening the `Needs
    # ... work` filler to admit intervening words also admitted the words that
    # INVERT the phrase, so a positive per-section remark anywhere in a long
    # review forced the whole comment to not-clean and could suppress a genuine
    # clean verdict indefinitely.
    for phrase in (
        "This section needs no work.",
        "The implementation is solid and needs no more work before merging.",
        "Nothing here needs any further work.",
        "No changes requested.",
        "There are no changes requested on this round.",
    ):
        check(
            f"classify_verdict: a NEGATED not-clean phrase is not a verdict -- {phrase!r}",
            checker.classify_verdict(phrase) == "",
        )
    # The other direction, which is the dangerous one: a negator belonging to
    # an EARLIER clause must not discharge the signal. Punctuation is what
    # separates them, and the guard's filler cannot cross it.
    for phrase, why in (
        ("This is not done. Needs work.", "a negator in the previous sentence"),
        ("It is not ready; needs more work.", "a negator before a semicolon"),
        ("Needs minor work", "the bare widened form still matches"),
        ("Needs a little more work", "multi-word filler still matches"),
        ("Verdict: Changes requested", "a labelled not-clean verdict"),
    ):
        check(
            f"classify_verdict: still not-clean -- {why}",
            checker.classify_verdict(phrase) == "not-clean",
        )
    check(
        "classify_verdict: a bullet-marked verdict IS clean",
        checker.classify_verdict("- **Approved for merge**") == "clean",
    )
    check(
        "classify_verdict: a line-initial verdict IS clean",
        checker.classify_verdict("Ready for merge.") == "clean",
    )
    # Where the vocabulary guards are still load-bearing after the position
    # guard: this corpus writes semantic line breaks, so a negation or hedge
    # routinely sits at the END of the PREVIOUS line, leaving the phrase itself
    # line-initial and therefore "marked". Position cannot see across the
    # break; the prefix scan can.
    check(
        "classify_verdict: a negation on the PREVIOUS line still blocks",
        checker.classify_verdict(
            "The PR is not\nready for merge until the findings are fixed."
        ) == "",
    )
    check(
        "classify_verdict: a hedge on the previous line still blocks",
        checker.classify_verdict("It is almost\nready for merge.") == "",
    )
    # A `Verdict:` label was exempted from every guard on the reasoning that
    # adjacency after the label already binds the phrase. That is true of what
    # PRECEDES it and says nothing about what FOLLOWS, so the labelled form was
    # the one path a trailing qualifier still walked straight through.
    check(
        "classify_verdict: 'Verdict: Ready, but ...' is NOT clean",
        checker.classify_verdict("Verdict: Ready, but two items remain.") == "",
    )
    check(
        "classify_verdict: 'Verdict: Clean once ...' is NOT clean",
        checker.classify_verdict("Verdict: Clean once the findings are fixed.") == "",
    )
    check(
        "classify_verdict: 'Verdict: Approved except for ...' is NOT clean",
        checker.classify_verdict("Verdict: Approved except for the nit below.") == "",
    )
    check(
        "classify_verdict: 'Verdict: Ready -- however, ...' is NOT clean",
        checker.classify_verdict("Verdict: Ready -- however, one item stands.") == "",
    )
    check(
        "classify_verdict: a bare 'Verdict: Ready' IS still clean",
        checker.classify_verdict("Verdict: Ready") == "clean",
    )
    # Where a match ENDS is an artifact of which pattern matched: two patterns
    # hit the same text at the same position with different lengths, so an
    # anchored suffix check on the shorter one lands past the qualifier and
    # sees nothing. Scanning the rest of the sentence does not depend on the
    # match length.
    check(
        "classify_verdict: 'Verdict: Ready for merge once ...' is NOT clean",
        checker.classify_verdict(
            "Verdict: Ready for merge once the following items are addressed: item A."
        ) == "",
    )
    check(
        "classify_verdict: 'Verdict: Approved for merge, but ...' is NOT clean",
        checker.classify_verdict("Verdict: Approved for merge, but two items remain.") == "",
    )
    # ...and sentence scope is what stops that from over-reaching: a qualifier
    # in the NEXT sentence is a separate statement, not a retraction.
    check(
        "classify_verdict: a qualifier in the NEXT sentence does not retract",
        checker.classify_verdict(
            "Ready for merge. The tests pass, but coverage is unchanged."
        ) == "clean",
    )
    # The not-clean side had the mirror gap, found by running this classifier
    # over real verdict bodies rather than over invented ones: three rounds of
    # "Needs MINOR work" on ai-config#1293 each classified as NO verdict, so a
    # genuine not-clean verdict neither blocked nor superseded anything.
    check(
        "classify_verdict: 'Needs minor work' is not-clean",
        checker.classify_verdict("Needs minor work") == "not-clean",
    )
    check(
        "classify_verdict: 'Needs a little more work' is not-clean",
        checker.classify_verdict("Needs a little more work") == "not-clean",
    )
    # A bare newline does not end a sentence in a semantic-line-break corpus,
    # so a qualifier starting the next line still retracts. Same corpus
    # property the negation guard is built around, mirrored to the other side.
    check(
        "classify_verdict: a qualifier on the NEXT line still retracts",
        checker.classify_verdict("**Ready for merge**\nonce the two findings are fixed.") == "",
    )
    check(
        "classify_verdict: an adversative on the next line still retracts",
        checker.classify_verdict("Ready for merge,\nbut two items remain.") == "",
    )
    # ...bounded, because a qualifier only RETRACTS when it sits close. A real
    # sign-off continues past the verdict with ordinary prose that may contain
    # `but` far downstream; retracting on that makes criterion 4 unsatisfiable
    # for a clean PR. Taken from an actual verdict body on ai-config#1293.
    check(
        "classify_verdict: a distant 'but' in a long sign-off does NOT retract",
        checker.classify_verdict(
            "**Ready for merge** -- all three carried-over nits are fixed, the two new "
            "worked-example additions are correctly sourced against the live threads, "
            "but I noted one wording nit for later."
        ) == "clean",
    )

    # --- #1524: unreadable-format detection ---
    # Antigravity reviews that use "### Conclusion" with prose (no "### Verdict"
    # heading and no classifiable phrase) must be detected as "unreadable" rather
    # than falling through to "" (no verdict) which would trigger self-review
    # fallback and waste a round.
    antigravity_conclusion = (
        "### \U0001f916 Antigravity Agent Report (Code-Review)\n\n"
        "The PR is complete, robust, well-documented, and thoroughly tested.\n\n"
        "### Conclusion\n\n"
        "The PR is complete, robust, well-documented, and thoroughly tested."
    )
    check(
        "classify_verdict: Antigravity conclusion prose returns 'unreadable'",
        checker.classify_verdict(antigravity_conclusion) == "unreadable",
    )
    # But an Antigravity review WITH a classifiable verdict still works.
    antigravity_with_verdict = (
        "### \U0001f916 Antigravity Agent Report (Code-Review)\n\n"
        "Verdict: Clean / Ready for merge."
    )
    check(
        "classify_verdict: Antigravity with Verdict heading still classifies as clean",
        checker.classify_verdict(antigravity_with_verdict) == "clean",
    )
    # A Jules review with "VERDICT: block" is a not-clean verdict, not unreadable.
    jules_block = "VERDICT: block -- two findings must be addressed."
    check(
        "classify_verdict: Jules 'VERDICT: block' is not-clean, not unreadable",
        checker.classify_verdict(jules_block) == "not-clean",
    )
    # A non-bot comment with no verdict is still "" (not unreadable).
    check(
        "classify_verdict: a human comment with no verdict stays ''",
        checker.classify_verdict("Looks good to me!") == "",
    )
    # _detect_review_agent unit tests
    check(
        "_detect_review_agent: Claude marker detected",
        checker._detect_review_agent("**Claude finished** -- adversarial review") == "Claude",
    )
    check(
        "_detect_review_agent: Antigravity marker detected",
        checker._detect_review_agent("### \U0001f916 Antigravity Agent Report (Code-Review)") == "Antigravity",
    )
    check(
        "_detect_review_agent: unknown body returns None",
        checker._detect_review_agent("Just a regular comment.") is None,
    )

    # POSITIVE CONTROL -- the exact #1267 shape that bypassed the gate.
    # An explicit "Needs more work" at an EARLIER commit (so it never enters
    # matching_items), followed by a rich, evidence-dense comment at HEAD that
    # states no verdict at all. Every pre-existing criterion passes on this
    # payload; only criterion 4 catches it. The test asserts BOTH halves, so it
    # cannot go vacuous if a future edit makes some other check fail instead.
    needs_work_earlier_sha = {
        "createdAt": "2026-08-07T21:56:00Z",
        "body": (
            "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD oldsha0.\n\n"
            "Verdict: Needs more work -- 8 findings below."
        ),
    }
    verification_no_verdict_at_head = {
        "createdAt": "2026-08-07T23:05:00Z",
        "body": (
            "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD sha123.\n\n"
            "### Verification\n\nI re-derived each figure against the source. "
            "The line counts agree, the citations resolve, and the reflow "
            "preserved every word.\n\nNot merging."
        ),
    }
    mock_1267 = json.dumps({
        "comments": [needs_work_earlier_sha, verification_no_verdict_at_head],
        "reviews": [],
    })
    with patch.object(checker, "run_cmd", return_value=mock_1267):
        v_ok, v_issues = checker.check_review_comments("1267", "sha123", TEST_REPO)
        check(
            "POSITIVE CONTROL: verdict-less comment at HEAD does not clear an earlier "
            "'Needs more work' (#1267/#1275)",
            (not v_ok) and any("Latest verdict-bearing" in i for i in v_issues),
        )
        check(
            "POSITIVE CONTROL is non-vacuous: criterion 4 is the ONLY thing that fires",
            len(v_issues) == 1,
        )

    # NEGATIVE CONTROL -- the ordinary ARDI flow the check must not break:
    # the same earlier "Needs more work", superseded by a real clean verdict
    # at HEAD. If this fails, the check is over-blocking every iterated PR.
    clean_verdict_at_head = {
        "createdAt": "2026-08-07T23:05:00Z",
        "body": (
            "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD sha123.\n\n"
            "All eight findings are addressed.\n\nVerdict: Clean / Ready for merge."
        ),
    }
    mock_superseded = json.dumps({
        "comments": [needs_work_earlier_sha, clean_verdict_at_head],
        "reviews": [],
    })
    with patch.object(checker, "run_cmd", return_value=mock_superseded):
        s_ok, s_issues = checker.check_review_comments("1267", "sha123", TEST_REPO)
        check(
            "NEGATIVE CONTROL: a later clean verdict DOES supersede an earlier 'Needs more work'",
            s_ok and s_issues == [],
        )

    # Ordering, not payload order: the chronology must come from the timestamps,
    # so a clean verdict listed first but dated EARLIER still loses to a later
    # not-clean one.
    mock_out_of_order = json.dumps({
        "comments": [clean_verdict_at_head, {
            "createdAt": "2026-08-07T23:30:00Z",
            "body": "### \ud83e\udd16 Report\n\nReviewed HEAD sha123.\n\nVerdict: Needs more work.",
        }],
        "reviews": [],
    })
    with patch.object(checker, "run_cmd", return_value=mock_out_of_order):
        o_ok, o_issues = checker.check_review_comments("1267", "sha123", TEST_REPO)
        check(
            "latest verdict is chosen by timestamp, not by payload order",
            (not o_ok) and any("Latest verdict-bearing" in i for i in o_issues),
        )

    # REAL-INPUT CONTROL -- the fixtures above all carry a "\ud83e\udd16" marker, which
    # enters the pipeline downstream of the admission gate and so proves nothing
    # about it. These reproduce #1267's ACTUAL comment shapes: posted under a
    # human login, no robot glyph, the verdict carried under a "### Verdict"
    # heading. Against the pre-fix marker list all four were rejected, all_items
    # was empty, and criterion 4 could never fire on the very PR it was built
    # for. See algorithmatize-checks.md, "A negative control must enter at the
    # real input".
    real_round1 = {
        "createdAt": "2026-08-07T21:56:09Z",
        "body": (
            "**Claude finished** --- adversarial review of the whole diff.\n\n"
            "### Verdict\n\n**Needs more work** --- 8 findings below."
        ),
    }
    real_round2 = {
        "createdAt": "2026-08-07T22:49:12Z",
        "body": (
            "**Round-2 verification** --- adversarial re-check of all eight findings.\n\n"
            "### Verdict\n\n**Needs more work** --- the two items above are the only "
            "outstanding ones. I am correcting both in the next push."
        ),
    }
    real_round3_no_verdict = {
        "createdAt": "2026-08-07T23:05:32Z",
        "body": (
            "## Round 3 --- two corrections, three new learnings\n\n"
            "Head is now sha123.\n\n"
            "### Verification\n\nEvery figure re-derived against the source; the "
            "counts agree.\n\nNot merging."
        ),
    }
    mock_real = json.dumps({
        "comments": [real_round1, real_round2, real_round3_no_verdict],
        "reviews": [],
    })
    with patch.object(checker, "run_cmd", return_value=mock_real):
        r_ok, r_issues = checker.check_review_comments("1267", "sha123", TEST_REPO)
        check(
            "REAL-INPUT CONTROL: #1267's actual comment shapes are admitted and "
            "criterion 4 fires on them",
            (not r_ok) and any("Latest verdict-bearing" in i for i in r_issues),
        )

    # Test 6: CI check runs filtering
    mock_ci_success = json.dumps({
        "check_runs": [
            {"name": "build", "status": "completed", "conclusion": "success"},
            {"name": "test", "status": "completed", "conclusion": "skipped"}
        ]
    })
    with patch.object(checker, "run_cmd", return_value=mock_ci_success):
        ci_ok, ci_issues = checker.check_ci_runs("sha123", TEST_REPO)
        check("completed success/skipped CI check runs pass", ci_ok and ci_issues == [])

    mock_ci_failure = json.dumps({
        "check_runs": [
            {"name": "build", "status": "completed", "conclusion": "failure"}
        ]
    })
    with patch.object(checker, "run_cmd", return_value=mock_ci_failure):
        ci_ok_fail, ci_issues_fail = checker.check_ci_runs("sha123", TEST_REPO)
        check("failed CI check run fails check_ci_runs", not ci_ok_fail and len(ci_issues_fail) == 1)

    # Test 7: the repository is threaded, not hardcoded (#1243, #1338, #1346, #1391)
    #
    # Every case below asserts on the argv the script BUILDS, because that is
    # where the defect lived: the return values were fine, and the commands
    # named the wrong repository.

    rec = CmdRecorder(json.dumps({"check_runs": [
        {"name": "build", "status": "completed", "conclusion": "success"}]}))
    with patch.object(checker, "run_cmd", rec):
        checker.check_ci_runs("sha123", TEST_REPO)
    check(
        "check_ci_runs queries the repo it was given, not a literal",
        f"repos/{TEST_REPO}/commits/sha123" in rec.flat and HARDCODED not in rec.flat,
    )

    rec = CmdRecorder(json.dumps({
        "headRefOid": "sha123", "headRefName": "b", "state": "OPEN",
        "commits": [{"committedDate": "2026-08-14T00:00:00Z"}], "reviewDecision": "",
    }))
    with patch.object(checker, "run_cmd", rec):
        checker.get_pr_info("445", TEST_REPO)
    check(
        "get_pr_info names the repo explicitly rather than relying on the cwd",
        ["--repo", TEST_REPO] == rec.calls[0][rec.calls[0].index("--repo"):][:2]
        if "--repo" in rec.calls[0] else False,
    )

    rec = CmdRecorder(json.dumps({"comments": [clean_comment], "reviews": []}))
    with patch.object(checker, "run_cmd", rec):
        checker.check_review_comments("445", "sha123", TEST_REPO)
    check(
        "check_review_comments names the repo explicitly too",
        "--repo" in rec.calls[0] and TEST_REPO in rec.calls[0],
    )

    # The discrimination case #1391 asks for: one PR number, two repos, two
    # different answers. Pre-fix, check_ci_runs ignored its repo entirely, so
    # both calls returned whatever the hardcoded repo held and this failed.
    per_repo = {
        "owner/green": json.dumps({"check_runs": [
            {"name": "ci", "status": "completed", "conclusion": "success"}]}),
        "owner/red": json.dumps({"check_runs": [
            {"name": "ci", "status": "completed", "conclusion": "failure"}]}),
    }

    def fake_by_repo(cmd):
        joined = " ".join(cmd)
        for name, payload in per_repo.items():
            if f"repos/{name}/" in joined:
                return payload
        # A command naming neither repo (the pre-fix hardcoded path) returns an
        # empty result rather than raising, so this case FAILS its own
        # assertion instead of aborting the suite. A mutation that crashes the
        # run hides every test after it, which makes the rest of the matrix
        # unreadable.
        return json.dumps({"check_runs": []})

    with patch.object(checker, "run_cmd", fake_by_repo):
        green_ok, _ = checker.check_ci_runs("shaX", "owner/green")
        red_ok, red_issues = checker.check_ci_runs("shaX", "owner/red")
    check(
        "the same PR SHA yields per-repo verdicts, not one shared answer",
        green_ok and not red_ok and len(red_issues) == 1,
    )

    # Test 8: resolve_repo defaults, overrides, and fails loudly
    with patch.object(checker, "run_cmd", CmdRecorder("owner/from-cwd")):
        check("resolve_repo defaults to the current checkout",
              checker.resolve_repo() == "owner/from-cwd")
        check("an explicit --repo wins over the checkout",
              checker.resolve_repo("owner/explicit") == "owner/explicit")

    def boom(cmd):
        raise RuntimeError("not a git repository")

    def exit_code_of(fn):
        """The SystemExit code a call raises, or None if it did not exit.

        The code is asserted rather than the mere fact of exiting, because
        `raise SystemExit("msg")` exits 1 -- this script's "not clean" code --
        so an unchecked exit would report a usage error as a verdict about the
        PR. That distinction is stated in the module docstring, and this is
        what keeps the statement true.
        """
        try:
            fn()
        except SystemExit as exc:
            return exc.code
        except BaseException as exc:
            # Returned rather than propagated, so a guard that stops converting
            # an exception into an exit code FAILS this assertion instead of
            # aborting the suite and hiding every test after it.
            return exc
        return None

    with patch.object(checker, "run_cmd", boom):
        check("an unresolvable repo exits 2, not 1 ('not clean')",
              exit_code_of(checker.resolve_repo) == 2)

    with patch.object(checker, "run_cmd", CmdRecorder("owner/from-cwd")):
        # Accepted by `gh pr view --repo`, rejected by the check-runs API path
        # -- the shape mismatch that lets the two halves disagree.
        check("a URL is refused rather than interpolated into the API path",
              exit_code_of(lambda: checker.resolve_repo("https://github.com/owner/name")) == 2)

    # A missing `gh` must exit 2 from EVERY call site, not just the one
    # resolve_repo happens to make. Measured live: with -R supplied,
    # resolve_repo succeeded without needing `gh` at all, and the next call
    # raised a raw FileNotFoundError traceback and exited 1 -- "not clean".
    # Guarding one sibling path and leaving the others is the partial guard
    # fail-fast.md describes, so this asserts the guard where it was absent
    # rather than where it already existed.
    with patch.object(checker, "subprocess") as fake_sub:
        fake_sub.run.side_effect = FileNotFoundError(2, "No such file or directory", "gh")
        check("a missing gh exits 2 from get_pr_info, not 1 ('not clean')",
              exit_code_of(lambda: checker.get_pr_info("445", TEST_REPO)) == 2)
        check("a missing gh exits 2 from check_ci_runs too",
              exit_code_of(lambda: checker.check_ci_runs("sha123", TEST_REPO)) == 2)

    # Test 9: -R is parsed rather than silently ignored (#1391's repro)
    args = checker.parse_args(["445", "-R", "Morrison-Lab/gha"])
    check("-R is parsed, not silently ignored",
          args.pr_number == "445" and args.repo == "Morrison-Lab/gha")
    check("a bare PR number still works, with no repo override",
          checker.parse_args(["445"]).repo == "")

    check("--help exits 0 instead of being read as a PR number",
          exit_code_of(lambda: checker.parse_args(["--help"])) == 0)
    check("a missing PR number exits 2, distinct from 'not clean'",
          exit_code_of(lambda: checker.parse_args([])) == 2)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
