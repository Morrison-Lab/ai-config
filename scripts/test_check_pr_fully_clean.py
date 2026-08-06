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
        clean_ok, clean_issues = checker.check_review_comments("1167", "sha123", "2026-08-05T18:12:00Z")
        check("clean review comment passes check_review_comments", clean_ok and clean_issues == [])

    # Test 2: Findings review comment returns False
    mock_findings_data = json.dumps({"comments": [findings_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_findings_data):
        findings_ok, findings_issues = checker.check_review_comments("1167", "sha123", "2026-08-05T18:12:00Z")
        check("findings review comment fails check_review_comments", not findings_ok and len(findings_issues) > 0)

    # Test 3: Formal review with empty comments list and CHANGES_REQUESTED state fails
    mock_formal_review_data = json.dumps({"comments": [], "reviews": [formal_changes_requested_review]})
    with patch.object(checker, "run_cmd", return_value=mock_formal_review_data):
        formal_ok, formal_issues = checker.check_review_comments("1167", "sha123", "2026-08-05T18:12:00Z")
        check("formal CHANGES_REQUESTED review with empty comments fails check_review_comments", not formal_ok and len(formal_issues) > 0)

    # Test 4: Review with 'No major changes requested' passes check_review_comments
    mock_no_major_data = json.dumps({"comments": [no_major_changes_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_no_major_data):
        no_major_ok, no_major_issues = checker.check_review_comments("1167", "sha123", "2026-08-05T18:12:00Z")
        check("review with 'No major changes requested' passes check_review_comments", no_major_ok and no_major_issues == [])

    # Test 5: Payload with None author in reviews does not raise exception
    mock_none_author_data = json.dumps({"comments": [], "reviews": [none_author_review]})
    with patch.object(checker, "run_cmd", return_value=mock_none_author_data):
        none_author_ok, none_author_issues = checker.check_review_comments("1167", "sha123", "2026-08-05T18:12:00Z")
        check("payload with None author handles safely", none_author_ok and none_author_issues == [])

    # Test 6: Plain human APPROVED review without bot review fails criterion 2
    mock_human_data = json.dumps({"comments": [], "reviews": [human_approved_review]})
    with patch.object(checker, "run_cmd", return_value=mock_human_data):
        human_ok, human_issues = checker.check_review_comments("1167", "sha123", "2026-08-05T18:12:00Z")
        check("human APPROVED review without bot review fails criterion 2", not human_ok and any("No automated review" in i for i in human_issues))

    # Regression: a stale review posted AFTER the commit, carrying a marker
    # word but NOT referencing the HEAD SHA, must NOT be accepted as evaluating
    # HEAD (the fail-open timing-race guarded by fully-clean.md). It is a slow
    # review of an earlier commit landing after a newer push.
    stale_no_sha_comment = {
        "createdAt": "2026-08-05T18:30:00Z",  # well after commit_date
        "body": "### \ud83e\udd16 Antigravity Agent Report\n\nAnalysis of an older commit.\n\nVerdict: Clean / Ready for merge."
    }
    mock_stale_data = json.dumps({"comments": [stale_no_sha_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_stale_data):
        stale_ok, stale_issues = checker.check_review_comments("1167", "sha123", "2026-08-05T18:12:00Z")
        check("stale review not referencing HEAD SHA is rejected (fail-closed)", (not stale_ok) and len(stale_issues) > 0)

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
