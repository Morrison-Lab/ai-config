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

passes = 0
failures = 0


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
        clean_ok, clean_issues = checker.check_review_comments("1167", "sha123")
        check("clean review comment passes check_review_comments", clean_ok and clean_issues == [])

    # Test 2: Findings review comment returns False
    mock_findings_data = json.dumps({"comments": [findings_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_findings_data):
        findings_ok, findings_issues = checker.check_review_comments("1167", "sha123")
        check("findings review comment fails check_review_comments", not findings_ok and len(findings_issues) > 0)

    # Test 3: Formal review with empty comments list and CHANGES_REQUESTED state fails
    mock_formal_review_data = json.dumps({"comments": [], "reviews": [formal_changes_requested_review]})
    with patch.object(checker, "run_cmd", return_value=mock_formal_review_data):
        formal_ok, formal_issues = checker.check_review_comments("1167", "sha123")
        check("formal CHANGES_REQUESTED review with empty comments fails check_review_comments", not formal_ok and len(formal_issues) > 0)

    # Test 4: Review with 'No major changes requested' passes check_review_comments
    mock_no_major_data = json.dumps({"comments": [no_major_changes_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_no_major_data):
        no_major_ok, no_major_issues = checker.check_review_comments("1167", "sha123")
        check("review with 'No major changes requested' passes check_review_comments", no_major_ok and no_major_issues == [])

    # Test 5: Payload with None author in reviews does not raise (reaching the
    # check at all proves no exception), and a None-author review is NOT admitted
    # as automated -- author identity, not the bot-looking body, is what qualifies
    # a review as automated (round 12). A deleted-account (None-author) review
    # cannot be confirmed automated, so it fails criterion 2 (fail-closed).
    mock_none_author_data = json.dumps({"comments": [], "reviews": [none_author_review]})
    with patch.object(checker, "run_cmd", return_value=mock_none_author_data):
        none_author_ok, none_author_issues = checker.check_review_comments("1167", "sha123")
        check("None-author review handled safely and not admitted as automated",
              (not none_author_ok) and any("No automated review" in i for i in none_author_issues))

    # Test 6: Plain human APPROVED review without bot review fails criterion 2
    mock_human_data = json.dumps({"comments": [], "reviews": [human_approved_review]})
    with patch.object(checker, "run_cmd", return_value=mock_human_data):
        human_ok, human_issues = checker.check_review_comments("1167", "sha123")
        check("human APPROVED review without bot review fails criterion 2", not human_ok and any("No automated review" in i for i in human_issues))

    # Regression: a stale review posted AFTER the commit, carrying a marker
    # word but NOT referencing the HEAD SHA, must NOT be accepted as evaluating
    # HEAD (the fail-open timing-race guarded by fully-clean.md). It is a slow
    # review of an earlier commit landing after a newer push.
    stale_no_sha_comment = {
        "createdAt": "2026-08-05T18:30:00Z",  # posted after the commit, references no HEAD SHA
        "body": "### \ud83e\udd16 Antigravity Agent Report\n\nAnalysis of an older commit.\n\nVerdict: Clean / Ready for merge."
    }
    mock_stale_data = json.dumps({"comments": [stale_no_sha_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_stale_data):
        stale_ok, stale_issues = checker.check_review_comments("1167", "sha123")
        check("stale review not referencing HEAD SHA is rejected (fail-closed)", (not stale_ok) and len(stale_issues) > 0)

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
        hmv_ok, hmv_issues = checker.check_review_comments("1167", "sha123")
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
        hmc_ok, hmc_issues = checker.check_review_comments("1167", "sha123")
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
        loc_ok, loc_issues = checker.check_review_comments("1160", "sha123")
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
        nwq_ok, nwq_issues = checker.check_review_comments("1167", "sha123")
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
        locreal_ok, locreal_issues = checker.check_review_comments("1167", "sha123")
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
            "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD sha123.\n\n"
            "He said \"hi. **Location:** foo.py:1 -- bug\" and left."
        ),
    }
    mock_qrf = json.dumps({"comments": [quoted_real_finding], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_qrf):
        qrf_ok, qrf_issues = checker.check_review_comments("1167", "sha123")
        check(
            "genuine **Location:** inside a double-quoted span is still detected (#1231 review)",
            (not qrf_ok) and len(qrf_issues) > 0,
        )

    # Test 6: CI check runs filtering
    mock_ci_success = json.dumps({
        "check_runs": [
            {"name": "build", "status": "completed", "conclusion": "success"},
            {"name": "test", "status": "completed", "conclusion": "skipped"}
        ]
    })
    with patch.object(checker, "run_cmd", return_value=mock_ci_success):
        ci_ok, ci_issues = checker.check_ci_runs("sha123")
        check("completed success/skipped CI check runs pass", ci_ok and ci_issues == [])

    mock_ci_failure = json.dumps({
        "check_runs": [
            {"name": "build", "status": "completed", "conclusion": "failure"}
        ]
    })
    with patch.object(checker, "run_cmd", return_value=mock_ci_failure):
        ci_ok_fail, ci_issues_fail = checker.check_ci_runs("sha123")
        check("failed CI check run fails check_ci_runs", not ci_ok_fail and len(ci_issues_fail) == 1)

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
