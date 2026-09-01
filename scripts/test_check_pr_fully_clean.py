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
import re
import time
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

# Backtick, built rather than typed: a doubled-backslash/backtick literal is
# not reliably preserved across every tool transport this repo is edited
# through (see CLAUDE.md, "Tool transport collapses doubled backslashes").
B = chr(96)


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


seen_check_names = set()

def check(name: str, condition: bool):
    global passes, failures
    if name in seen_check_names:
        print(f"FAIL: duplicated check name: {name}")
        failures += 1
        return
    seen_check_names.add(name)
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1



# Compatibility wrappers for refactored check_ci_runs and check_review_comments
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.lib.pull_request import PullRequest

original_check_ci_runs = checker.check_ci_runs
def wrapped_check_ci_runs(sha, repo, *args, **kwargs):
    pr = PullRequest.__new__(PullRequest)
    pr.pr_num = "123"
    pr.repo = repo
    pr._fetcher = checker.run_cmd
    pr._data = {"headRefOid": sha}
    pr._check_runs = None
    return original_check_ci_runs(pr)

original_check_review_comments = checker.check_review_comments
def wrapped_check_review_comments(pr_num, sha, repo, review_decision="", branch="", quorum=1):
    pr = PullRequest.__new__(PullRequest)
    pr.pr_num = pr_num
    pr.repo = repo
    pr._fetcher = checker.run_cmd
    import json
    out = checker.run_cmd(["gh", "pr", "view", pr_num, "--repo", repo, "--json", "comments,reviews"])
    if isinstance(out, str):
        data = json.loads(out)
    else:
        data = {}
    data["headRefOid"] = sha
    data["reviewDecision"] = review_decision
    data["headRefName"] = branch
    pr._data = data
    pr._check_runs = None
    return original_check_review_comments(pr, quorum)

checker.check_ci_runs = wrapped_check_ci_runs
checker.check_review_comments = wrapped_check_review_comments

def best_of_three(fn, *args):
    """Fastest of three runs, with the last return value.

    A timing check is about complexity, not about how busy the machine
    is, so a single sample makes it flaky: one of these failed under
    contention at 6.7x headroom while measuring 0.148s standalone.
    Taking the minimum keeps the threshold tight enough to catch a
    quadratic -- which misses by orders of magnitude, not by noise --
    without failing on a loaded runner.
    """
    best = None
    value = None
    for _ in range(3):
        start = time.time()
        value = fn(*args)
        elapsed = time.time() - start
        if best is None or elapsed < best:
            best = elapsed
    return best, value


def main() -> int:
    print("Testing check-pr-fully-clean.py...")

    clean_comment = {
        "createdAt": "2026-08-05T18:14:14Z",
        "author": {"login": "github-actions"},
        "body": "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\nEverything looks great! No issues found.\n\nReviewed HEAD sha123.\n\nVerdict: Clean / Ready for merge."
    }

    findings_comment = {
        "createdAt": "2026-08-05T18:14:37Z",
        "author": {"login": "github-actions"},
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
        "author": {"login": "github-actions"},
        "body": "### \ud83e\udd16 Antigravity Agent Report\n\nReviewed HEAD sha123.\n\n### Verdict\n\n**Ready for merge**\n\nNo major changes requested."
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
        "author": {"login": "example-maintainer"},
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
        "author": {"login": "example-maintainer"},
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
        "author": {"login": "example-maintainer"},
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
        "author": {"login": "example-maintainer"},
        "commit": {"oid": "sha123"},
    }
    mock_hmc = json.dumps({"comments": [], "reviews": [human_marker_codereview]})
    with patch.object(checker, "run_cmd", return_value=mock_hmc):
        hmc_ok, hmc_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "human APPROVED review whose body contains 'code review' does not satisfy criterion 2",
            (not hmc_ok) and any("No automated review" in i for i in hmc_issues),
        )

    # Regression (PR #2180 round 5): non-bot comment containing review marker
    # and HEAD SHA DOES NOT satisfy review admission if the author is not authorized!
    spoofed_passerby_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": "**Claude finished** review\n\n### Verdict\n\n**Ready for merge**\n\n(reviewed at `sha123`)",
        "author": {"login": "random-passerby"},
        "authorAssociation": "NONE"
    }
    mock_spoofed = json.dumps({"comments": [spoofed_passerby_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_spoofed):
        sp_ok, sp_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "non-bot comment with marker and HEAD SHA does not satisfy review admission if unauthorized",
            (not sp_ok) and any("No automated review" in i for i in sp_issues),
        )

    # CLI agents post under human accounts, but MUST have an authorized association.
    authorized_cli_agent_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": "**Claude finished** review\n\n### Verdict\n\n**Ready for merge**\n\n(reviewed at `sha123`)",
        "author": {"login": "the-repo-owner"},
        "authorAssociation": "OWNER"
    }
    mock_authorized = json.dumps({"comments": [authorized_cli_agent_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_authorized):
        auth_ok, auth_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "authorized human comment with agent marker DOES satisfy review admission (CLI agents)",
            auth_ok and len(auth_issues) == 0,
        )

    # Regression (PR #2180 round 6): comment with author: None (deleted account) cannot spoof review
    spoofed_null_author_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": "code review\n\n### Verdict\n\n**Ready for merge**\n\n(reviewed at `sha123`)",
        "author": None,
    }
    mock_null_author = json.dumps({"comments": [spoofed_null_author_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_null_author):
        null_ok, null_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "null-author comment with marker and HEAD SHA does not satisfy review admission",
            (not null_ok) and any("No automated review" in i for i in null_issues),
        )

    # Regression (PR #2180 round 6): author with null login {"author": {"login": None}} does not crash _is_bot_author
    spoofed_null_login_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": "code review\n\n### Verdict\n\n**Ready for merge**\n\n(reviewed at `sha123`)",
        "author": {"login": None},
    }
    mock_null_login = json.dumps({"comments": [spoofed_null_login_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_null_login):
        nlog_ok, nlog_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "author with null login does not crash and does not satisfy review admission",
            (not nlog_ok) and any("No automated review" in i for i in nlog_issues),
        )

    # Regression (PR #2180 round 5): bot review with negated rejection phrased as
    # "not approved" fails check_review_comments as not-clean.
    negated_rejection_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "body": (
            "**Claude finished** review\n\n### Verdict\n\n"
            "This PR is **not approved** yet, several blocking findings remain.\n\n"
            "(reviewed at `sha123`)"
        ),
        "author": {"login": "github-actions"},
    }
    mock_negated = json.dumps({"comments": [negated_rejection_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_negated):
        neg_ok, neg_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "bot review with 'not approved' rejection is classified as not-clean and fails",
            (not neg_ok) and len(neg_issues) > 0,
        )

    # Regression (PR #2180 round 6): clean review mentioning resolved blocker in prose passes
    resolved_blocker_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "All prior findings addressed. The earlier round was blocked on a missing test fixture, "
            "which is now resolved.\n\n"
            "### Verdict\n\n**Ready for merge**\n\n(reviewed at `sha123`)"
        ),
    }
    mock_res_blk = json.dumps({"comments": [resolved_blocker_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_res_blk):
        rblk_ok, rblk_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "clean review mentioning resolved blocker in prose passes check_review_comments",
            rblk_ok and rblk_issues == [],
        )

    # Regression (PR #2180 round 6): clean review mentioning resolved impasse in prose passes
    resolved_impasse_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "No deadlock or impasse here -- the prior rebuttal convinced the reviewer.\n\n"
            "### Verdict\n\n**Ready for merge**\n\n(reviewed at `sha123`)"
        ),
    }
    mock_res_imp = json.dumps({"comments": [resolved_impasse_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_res_imp):
        rimp_ok, rimp_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
        check(
            "clean review mentioning resolved impasse in prose passes check_review_comments",
            rimp_ok and rimp_issues == [],
        )

    # Regression (PR #2180 round 8): standard bolded rejection verdicts must fail check_review_comments
    for rejected_word in ["Rejected", "Blocked", "Unapproved", "Impasse", "Deadlock", "Changes requested"]:
        rej_body = (
            f"**Claude finished** review\n\n### Verdict\n\n**{rejected_word}** -- several blocking findings remain.\n\n(reviewed at `sha123`)"
        )
        check(
            f"classify_verdict: '### Verdict\\n\\n**{rejected_word}**' classifies as not-clean",
            checker.classify_verdict(rej_body) == "not-clean",
        )
        rej_comment = {
            "createdAt": "2026-08-06T00:00:00Z",
            "author": {"login": "github-actions"},
            "body": rej_body,
        }
        mock_rej_data = json.dumps({"comments": [rej_comment], "reviews": []})
        with patch.object(checker, "run_cmd", return_value=mock_rej_data):
            rej_ok, rej_issues = checker.check_review_comments("1167", "sha123", TEST_REPO)
            check(
                f"check_review_comments: '### Verdict\\n\\n**{rejected_word}**' fails as not clean",
                (not rej_ok) and len(rej_issues) > 0,
            )

    # Regression (PR #2180 round 9): non-HEAD negated rejection caught by check_latest_verdict
    non_head_round1 = {
        "createdAt": "2026-08-05T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n### Verdict\n\n"
            "**Not approved** -- several blocking findings remain.\n\n"
            "(reviewed at `abc1234`)"
        ),
    }
    non_head_round2 = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "I examined the diff and left some notes below, but got cut short before concluding.\n\n"
            "(reviewed at `def5678f`)"
        ),
    }
    items_non_head = [
        ("comment", non_head_round1["createdAt"], non_head_round1["body"], "", "", non_head_round1["author"]["login"]),
        ("comment", non_head_round2["createdAt"], non_head_round2["body"], "", "", non_head_round2["author"]["login"]),
    ]
    nh_ok, nh_issues = checker.check_latest_verdict(items_non_head)
    check(
        "check_latest_verdict: non-HEAD marked rejection blocks clean verdict",
        (not nh_ok) and any("NOT clean" in i for i in nh_issues),
    )

    # ai-config#2482: an EXPIRED driver ledger from an exclusive-login bot
    # stops standing as that reviewer's verdict; anything short of the full
    # positive signature (exclusive login + Disposition table + hold phrase
    # + >2h idle) stays a verdict.
    ledger_body = (
        "Addressed GitHub Claude of `9508454e` (Needs more work). "
        "Pushed `8af4edc9`.\n\n"
        "| # | Tag | Disposition |\n|---|---|---|\n"
        "| 1 conflated cases | **Address** | Recreate rule is MERGED only. |\n\n"
        "Do not merge. Blocked on review of `8af4edc9`.\n"
    )
    stale = "2026-08-26T20:52:56Z"
    ledger_items = [
        ("comment", stale, ledger_body, "", "", "cursor"),
        ("comment", "2026-08-26T21:15:09Z",
         "**Claude finished review**\n\n### Verdict\n**Ready for merge**\n",
         "", "", "github-actions"),
    ]
    lv_ok, lv_issues = checker.check_latest_verdict(ledger_items)
    check(
        "an expired exclusive-login driver ledger is excluded, with a NOTE",
        lv_ok and any("expired driver ledger" in i for i in lv_issues),
    )
    shared_items = [("comment", stale, ledger_body, "", "", "github-actions")]
    sv_ok, _ = checker.check_latest_verdict(shared_items)
    check(
        "the same ledger under a shared login stays a verdict",
        not sv_ok,
    )
    check(
        "a cursor item without the ledger shape stays a verdict",
        not checker.check_latest_verdict(
            [("comment", stale,
              "### Verdict\n**Needs more work** -- real finding.\n",
              "", "", "cursor")])[0],
    )
    from datetime import datetime, timezone, timedelta
    fresh_now = datetime.fromisoformat(stale.replace("Z", "+00:00")) \
        + timedelta(minutes=30)
    check(
        "a ledger from a login active within 2h stays a verdict",
        checker._is_expired_driver_ledger(
            ledger_body, "cursor", stale, {"cursor": stale}, now=fresh_now)
        is False,
    )
    check(
        "a zone-naive timestamp is read as UTC rather than crashing",
        checker._is_expired_driver_ledger(
            ledger_body, "cursor", "2026-08-26T20:52:56",
            {"cursor": "2026-08-26T20:52:56"}) is True,
    )
    check(
        "commit activity keeps a quietly-pushing driver's ledger standing",
        not checker.check_latest_verdict(
            ledger_items[:1],
            commit_activity={"cursor": datetime.now(timezone.utc)
                             .strftime("%Y-%m-%dT%H:%M:%SZ")})[0],
    )

    # Regression (PR #2180 round 10): non-HEAD unmarked prose rejection under ### Verdict
    non_head_prose_round1 = {
        "createdAt": "2026-08-05T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n### Verdict\n\n"
            "This PR is not approved -- several blocking findings remain.\n\n"
            "(reviewed at `abc1234`)"
        ),
    }
    items_non_head_prose = [
        ("comment", non_head_prose_round1["createdAt"], non_head_prose_round1["body"], "", "", non_head_prose_round1["author"]["login"]),
        ("comment", non_head_round2["createdAt"], non_head_round2["body"], "", "", non_head_round2["author"]["login"]),
    ]
    nhp_ok, nhp_issues = checker.check_latest_verdict(items_non_head_prose)
    check(
        "check_latest_verdict: non-HEAD unmarked prose rejection under ### Verdict blocks clean verdict",
        (not nhp_ok) and any("NOT clean" in i for i in nhp_issues),
    )

    # Regression: check_latest_verdict sorts by createdAt timestamp (field index 1),
    # not by author login or other fields.
    items_diff_login = [
        ("comment", "2026-08-05T00:00:00Z", "**Claude finished** review\n\n### Verdict\n\n**Ready for merge**", "", "", "zzz-bot"),
        ("comment", "2026-08-06T00:00:00Z", "**Claude finished** review\n\n### Verdict\n\n**Not approved**, blocking.", "", "", "aaa-bot"),
    ]
    dl_ok, dl_issues = checker.check_latest_verdict(items_diff_login)
    check(
        "check_latest_verdict: sorts by timestamp when later item has alphabetically earlier login",
        (not dl_ok) and any("NOT clean" in i for i in dl_issues),
    )

    # ai-config#2274: a later all-clear from a DIFFERENT reviewer must not
    # supersede an earlier not-clean. Both comments use the same bot login,
    # which is why identity is taken from the agent marker, not the author.
    items_cross_reviewer = [
        (
            "comment",
            "2026-08-26T00:00:00Z",
            (
                "**Claude finished** review\n\n### Verdict\n\n"
                "**Needs more work** -- two findings remain.\n\n"
                "(reviewed at `oldsha00`)"
            ),
            "",
            "",
            "github-actions",
        ),
        (
            "comment",
            "2026-08-26T01:00:00Z",
            (
                "### \U0001f916 Antigravity Agent Report (Code-Review)\n\n"
                "Reviewed HEAD sha123.\n\n"
                "Verdict: Clean / Ready for merge."
            ),
            "",
            "",
            "github-actions",
        ),
    ]
    xr_ok, xr_issues = checker.check_latest_verdict(items_cross_reviewer)
    check(
        "check_latest_verdict: later all-clear from a different reviewer does not "
        "supersede an earlier not-clean (#2274)",
        (not xr_ok)
        and any("different reviewer" in i for i in xr_issues)
        and any("Claude" in i for i in xr_issues),
    )

    items_same_reviewer = [
        (
            "comment",
            "2026-08-26T00:00:00Z",
            (
                "**Claude finished** review\n\n### Verdict\n\n"
                "**Needs more work** -- two findings remain.\n\n"
                "(reviewed at `oldsha00`)"
            ),
            "",
            "",
            "github-actions",
        ),
        (
            "comment",
            "2026-08-26T01:00:00Z",
            (
                "**Claude finished** review\n\n### Verdict\n\n"
                "**Ready for merge**\n\n(reviewed at `sha123`)"
            ),
            "",
            "",
            "github-actions",
        ),
    ]
    sr_ok, sr_issues = checker.check_latest_verdict(items_same_reviewer)
    check(
        "check_latest_verdict: later clean from the SAME reviewer still supersedes",
        sr_ok and not any(
            ("NOT clean" in i and not i.startswith("NOTE:")) for i in sr_issues
        ),
    )
    check(
        "_reviewer_identity: Claude and Antigravity differ under the same bot login",
        checker._reviewer_identity(items_cross_reviewer[0][2], "github-actions")
        == "Claude"
        and checker._reviewer_identity(items_cross_reviewer[1][2], "github-actions")
        == "Antigravity",
    )

    quoted_claude_in_agy = (
        "### \U0001f916 Antigravity Agent Report (Code-Review)\n\n"
        "Reviewed HEAD sha123.\n\n"
        "Round 1 opened with **Claude finished** at the earlier SHA.\n\n"
        "Verdict: Clean / Ready for merge."
    )
    check(
        "_reviewer_identity: a later quote of Claude's opener does not inherit Claude",
        checker._reviewer_identity(quoted_claude_in_agy, "github-actions")
        == "Antigravity",
    )
    items_quoted = [
        items_cross_reviewer[0],
        (
            "comment",
            "2026-08-26T01:00:00Z",
            quoted_claude_in_agy,
            "",
            "",
            "github-actions",
        ),
    ]
    q_ok, q_issues = checker.check_latest_verdict(items_quoted)
    check(
        "check_latest_verdict: quoted Claude opener in an Antigravity all-clear "
        "does not collapse the two reviewers (#2274)",
        (not q_ok) and any("Claude" in i and "different reviewer" in i for i in q_issues),
    )

    quoted_claude_same_para = (
        "### \U0001f916 Antigravity Agent Report (Code-Review)\n"
        "Round 1 opened with **Claude finished** at the earlier SHA.\n\n"
        "Verdict: Clean / Ready for merge."
    )
    check(
        "_reviewer_identity: Claude quoted on line 2 of an Antigravity header "
        "does not inherit Claude",
        checker._reviewer_identity(quoted_claude_same_para, "github-actions")
        == "Antigravity",
    )
    quoted_claude_on_agy_first_line = (
        "### \U0001f916 Antigravity Agent Report --- see **Claude finished** "
        "from round 1"
    )
    check(
        "_reviewer_identity: leftmost marker on the first line wins, not "
        "REVIEW_AGENT_MARKERS dict order",
        checker._reviewer_identity(quoted_claude_on_agy_first_line, "github-actions")
        == "Antigravity",
    )
    items_first_line_quote = [
        items_cross_reviewer[0],
        (
            "comment",
            "2026-08-26T01:00:00Z",
            quoted_claude_on_agy_first_line + "\n\nVerdict: Clean / Ready for merge.",
            "",
            "",
            "github-actions",
        ),
    ]
    fl_ok, fl_issues = checker.check_latest_verdict(items_first_line_quote)
    check(
        "check_latest_verdict: Antigravity header quoting Claude on the same "
        "line does not collapse the two reviewers (#2274)",
        (not fl_ok) and any("Claude" in i and "different reviewer" in i for i in fl_issues),
    )
    unmarked_ga = (
        "**Round-2 verification** --- adversarial re-check.\n\n"
        "### Verdict\n\n**Ready for merge**"
    )
    check(
        "_reviewer_identity: a shared-login body with no first-line agent "
        "marker falls back to the login",
        checker._reviewer_identity(unmarked_ga, "github-actions") == "github-actions",
    )
    quoted_claude_multi_backtick = (
        "A quote of ``**Claude finished**`` on the first line.\n\n"
        "### Verdict\n\n**Ready for merge**"
    )
    check(
        "_reviewer_identity: multi-backtick quoted agent marker falls back to login (#2525)",
        checker._reviewer_identity(quoted_claude_multi_backtick, "github-actions") == "github-actions",
    )
    items_unmarked_after_claude = [
        items_cross_reviewer[0],
        (
            "comment",
            "2026-08-26T01:00:00Z",
            unmarked_ga,
            "",
            "",
            "github-actions",
        ),
    ]
    um_ok, um_issues = checker.check_latest_verdict(items_unmarked_after_claude)
    check(
        "check_latest_verdict: an unmarked later all-clear does not clear a "
        "marked Claude not-clean (#2274 residual: unmarked bodies share the "
        "login, which is a different identity from Claude)",
        (not um_ok) and any("Claude" in i and "different reviewer" in i for i in um_issues),
    )
    items_same_para = [
        items_cross_reviewer[0],
        (
            "comment",
            "2026-08-26T01:00:00Z",
            quoted_claude_same_para,
            "",
            "",
            "github-actions",
        ),
    ]
    sp_ok, sp_issues = checker.check_latest_verdict(items_same_para)
    check(
        "check_latest_verdict: same-paragraph Claude quote in an Antigravity "
        "all-clear does not collapse the two reviewers (#2274)",
        (not sp_ok) and any("Claude" in i and "different reviewer" in i for i in sp_issues),
    )

    check(
        "_reviewer_identity: Jules login is Jules on both block and approve",
        checker._reviewer_identity("VERDICT: block -- two findings.", "jules[bot]")
        == "Jules"
        and checker._reviewer_identity(
            "VERDICT: approve\n\nReady for merge.", "jules[bot]"
        )
        == "Jules",
    )
    items_jules = [
        (
            "comment",
            "2026-08-26T00:00:00Z",
            "VERDICT: block -- two findings must be addressed.",
            "",
            "",
            "jules[bot]",
        ),
        (
            "comment",
            "2026-08-26T01:00:00Z",
            "VERDICT: approve\n\nReady for merge.",
            "",
            "",
            "jules[bot]",
        ),
    ]
    ju_ok, ju_issues = checker.check_latest_verdict(items_jules)
    check(
        "check_latest_verdict: later Jules approve supersedes Jules block "
        "(same reviewer, #2274)",
        ju_ok and not any(
            ("NOT clean" in i and not i.startswith("NOTE:")) for i in ju_issues
        ),
    )

    copilot_cr = (
        "review",
        "2026-08-26T00:00:00Z",
        "Please rename the helper.",
        "oldsha00",
        "CHANGES_REQUESTED",
        "copilot-pull-request-reviewer[bot]",
    )
    claude_ready = items_same_reviewer[1]
    cr_ok, cr_issues = checker.check_latest_verdict([copilot_cr, claude_ready])
    check(
        "check_latest_verdict: Copilot CHANGES_REQUESTED is not cleared by a "
        "later Claude all-clear (#2274)",
        (not cr_ok) and any("copilot-pull-request-reviewer[bot]" in i for i in cr_issues),
    )
    cr_approved_ok, cr_approved_issues = checker.check_latest_verdict(
        [copilot_cr, claude_ready],
        approved_authors={"copilot-pull-request-reviewer[bot]"},
    )
    check(
        "check_latest_verdict: Copilot APPROVED supersedes Copilot's own "
        "earlier CHANGES_REQUESTED",
        cr_approved_ok and not any(
            ("NOT clean" in i and not i.startswith("NOTE:"))
            for i in cr_approved_issues
        ),
    )
    copilot_empty_approved = (
        "review",
        "2026-08-26T01:00:00Z",
        "",
        "sha123",
        "APPROVED",
        "copilot-pull-request-reviewer[bot]",
    )
    cr_then_approved_ok, cr_then_approved_issues = checker.check_latest_verdict(
        [copilot_cr, copilot_empty_approved],
        approved_authors={"copilot-pull-request-reviewer[bot]"},
    )
    check(
        "check_latest_verdict: Copilot empty APPROVED after CR is still "
        "cleared when Copilot is in approved_authors",
        cr_then_approved_ok and not any(
            ("NOT clean" in i and not i.startswith("NOTE:"))
            for i in cr_then_approved_issues
        ),
    )
    cr_then_approved_uncleared_ok, cr_then_approved_uncleared = (
        checker.check_latest_verdict([copilot_cr, copilot_empty_approved])
    )
    check(
        "check_latest_verdict: Copilot empty APPROVED does not clear CR "
        "without approved_authors",
        (not cr_then_approved_uncleared_ok)
        and any("Latest verdict-bearing review statement" in i for i in cr_then_approved_uncleared),
    )
    jules_cr = (
        "review",
        "2026-08-26T00:00:00Z",
        "VERDICT: block -- rename the helper.",
        "oldsha00",
        "CHANGES_REQUESTED",
        "jules[bot]",
    )
    jules_cr_ok, jules_cr_issues = checker.check_latest_verdict(
        [jules_cr, claude_ready],
    )
    check(
        "check_latest_verdict: Jules CHANGES_REQUESTED is not cleared by a "
        "later Claude all-clear (#2274)",
        (not jules_cr_ok) and any("Jules" in i for i in jules_cr_issues),
    )
    jules_approved_ok, jules_approved_issues = checker.check_latest_verdict(
        [jules_cr, claude_ready],
        approved_authors={"jules[bot]"},
    )
    check(
        "check_latest_verdict: Jules APPROVED supersedes Jules's own "
        "earlier CHANGES_REQUESTED",
        jules_approved_ok and not any(
            ("NOT clean" in i and not i.startswith("NOTE:"))
            for i in jules_approved_issues
        ),
    )
    ga_ok, ga_issues = checker.check_latest_verdict(
        items_cross_reviewer,
        approved_authors={"github-actions"},
    )
    check(
        "check_latest_verdict: a github-actions APPROVED does not clear Claude "
        "(shared login, #2274)",
        (not ga_ok) and any("Claude" in i and "different reviewer" in i for i in ga_issues),
    )

    # Regression (PR #2180 round 11): incidental prose negation outside verdict section does not fail
    incidental_negation_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "The working tree wasn't clean until I reran git status.\n\n"
            "### Verdict\n\n"
            "**Ready for merge** -- all findings addressed.\n\n"
            "(reviewed at `sha123`)\n\n"
            "Note: this isn't ready for python 2, but python 2 is deprecated."
        ),
    }
    mock_inc = json.dumps({"comments": [incidental_negation_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_inc):
        inc_ok, inc_issues = checker.check_review_comments("1160", "sha123", TEST_REPO)
        check(
            "check_review_comments: incidental prose negation outside verdict section does not raise finding",
            inc_ok and inc_issues == [],
        )
    check(
        "classify_verdict: incidental prose negation outside verdict section returns clean",
        checker.classify_verdict(incidental_negation_comment["body"]) == "clean",
    )
    check(
        "classify_verdict: unmarked prose rejection in verdict paragraph returns not-clean",
        checker.classify_verdict(non_head_prose_round1["body"]) == "not-clean",
    )

    # Regression (PR #2180 round 12): 'Needs more work: none identified' evaluates to clean
    needs_work_none_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n### Verdict\n\n"
            "Needs more work: none identified\n\n"
            "**Ready for merge**\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_nwn = json.dumps({"comments": [needs_work_none_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_nwn):
        nwn_ok, nwn_issues = checker.check_review_comments("1160", "sha123", TEST_REPO)
        check(
            "check_review_comments: 'Needs more work: none identified' evaluates to clean",
            nwn_ok and nwn_issues == [],
        )
    check(
        "classify_verdict: 'Needs more work: none identified' classifies as clean",
        checker.classify_verdict(needs_work_none_comment["body"]) == "clean",
    )

    # Regression (PR #2180 round 13): '### Findings\n\nNo new high-confidence bugs...' evaluates to clean
    findings_none_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "### Findings\n\n"
            "No new high-confidence bugs or CLAUDE.md violations found in this round's diff.\n\n"
            "### Verdict\n\n"
            "**Ready for merge** -- all findings addressed.\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_fn = json.dumps({"comments": [findings_none_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_fn):
        fn_ok, fn_issues = checker.check_review_comments("1160", "sha123", TEST_REPO)
        check(
            "check_review_comments: '### Findings\\n\\nNo new...' evaluates to clean",
            fn_ok and fn_issues == [],
        )

    # Regression (PR #2180 round 14): 'none of' after rejection keywords does NOT negate the rejection
    rej_none_of_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n### Verdict\n\n"
            "Rejected: none of the fixes from the last round were applied.\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_rno = json.dumps({"comments": [rej_none_of_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_rno):
        rno_ok, rno_issues = checker.check_review_comments("1160", "sha123", TEST_REPO)
        check(
            "check_review_comments: 'Rejected: none of...' fails as not clean",
            (not rno_ok) and any("contains findings" in i for i in rno_issues),
        )
    check(
        "classify_verdict: 'Rejected: none of...' classifies as not-clean",
        checker.classify_verdict(rej_none_of_comment["body"]) == "not-clean",
    )

    not_ready_none_of_comment = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n### Verdict\n\n"
            "This PR is not ready: none of the required tests pass.\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_nrn = json.dumps({"comments": [not_ready_none_of_comment], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_nrn):
        nrn_ok, nrn_issues = checker.check_review_comments("1160", "sha123", TEST_REPO)
        check(
            "check_review_comments: 'not ready: none of...' fails as not clean",
            (not nrn_ok) and any("contains findings" in i for i in nrn_issues),
        )
    check(
        "classify_verdict: 'not ready: none of...' classifies as not-clean",
        checker.classify_verdict(not_ready_none_of_comment["body"]) == "not-clean",
    )

    # Regression: an unmarked, mid-sentence 'ready for merge' mention inside a
    # ### Verdict paragraph that merely recaps or quotes an earlier comment while
    # findings remain open must NOT be classified as clean.
    unmarked_verdict_section_recap = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n### Verdict\n\n"
            "A teammate's earlier comment said this was ready for merge. "
            "I re-checked and both findings from round 1 are still open here.\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    check(
        "classify_verdict: unmarked mid-sentence 'ready for merge' in verdict paragraph does NOT classify as clean",
        checker.classify_verdict(unmarked_verdict_section_recap["body"]) != "clean",
    )

    # Regression (#1202): a CLEAN verdict that merely quotes finding vocabulary
    # inside a code span or double-quotes must NOT be read as raising a finding.
    # Both were live false positives on PRs about the review tooling itself.

    # #1160: clean verdict quoting `**Location:**` inside an inline code span.
    location_codespan_clean = {
        "createdAt": "2026-08-06T00:00:00Z",
        "author": {"login": "github-actions"},
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
        "author": {"login": "github-actions"},
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
        "author": {"login": "github-actions"},
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
        "author": {"login": "github-actions"},
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
        "author": {"login": "github-actions"},
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
        checker.classify_verdict("Verdict: Not Ready") in ("", "not-clean"),
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
    check(
        "classify_verdict: Anthropic code-review plugin clean comment is clean",
        checker.classify_verdict(
            "## Code review\n\nNo issues found. Checked for bugs and CLAUDE.md compliance."
        ) == "clean",
    )
    check(
        "classify_verdict: Anthropic code-review plugin clean comment with AGENTS.md is clean",
        checker.classify_verdict(
            "## Code review\n\nNo issues found. Checked for bugs and AGENTS.md compliance."
        ) == "clean",
    )
    check(
        "classify_verdict: code-review clean comment with trailing qualifier is NOT clean",
        checker.classify_verdict(
            "## Code review\n\nNo issues found. Checked for bugs and CLAUDE.md compliance once tests pass."
        ) == "",
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
        "author": {"login": "github-actions"},
        "body": (
            "### \ud83e\udd16 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD oldsha0.\n\n"
            "Verdict: Needs more work -- 8 findings below."
        ),
    }
    verification_no_verdict_at_head = {
        "createdAt": "2026-08-07T23:05:00Z",
        "author": {"login": "github-actions"},
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
            len(v_issues) == 1
        )

    # NEGATIVE CONTROL -- the ordinary ARDI flow the check must not break:
    # the same earlier "Needs more work", superseded by a real clean verdict
    # at HEAD. If this fails, the check is over-blocking every iterated PR.
    clean_verdict_at_head = {
        "createdAt": "2026-08-07T23:05:00Z",
        "author": {"login": "github-actions"},
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

    # ai-config#2274 through check_review_comments: Claude not-clean at an
    # earlier SHA, Antigravity all-clear at HEAD. Criterion 3 cannot see the
    # Claude comment (wrong SHA). Criterion 4 used to take the global latest
    # and report clean. The per-reviewer scan must still fail.
    claude_not_clean_earlier = {
        "createdAt": "2026-08-07T21:56:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n### Verdict\n\n"
            "**Needs more work** -- two findings remain.\n\n"
            "(reviewed at `oldsha00`)"
        ),
    }
    agy_clean_at_head = {
        "createdAt": "2026-08-07T23:05:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "### \U0001f916 Antigravity Agent Report (Code-Review)\n\n"
            "Reviewed HEAD sha123.\n\n"
            "All findings are addressed.\n\nVerdict: Clean / Ready for merge."
        ),
    }
    mock_disagree = json.dumps({
        "comments": [claude_not_clean_earlier, agy_clean_at_head],
        "reviews": [],
    })
    with patch.object(checker, "run_cmd", return_value=mock_disagree):
        d_ok, d_issues = checker.check_review_comments("2274", "sha123", TEST_REPO)
        check(
            "check_review_comments: later Antigravity all-clear does not clear "
            "an earlier Claude not-clean (#2274)",
            (not d_ok)
            and any("different reviewer" in i for i in d_issues)
            and any("Claude" in i for i in d_issues),
        )

    nits_at_head = {
        "createdAt": "2026-08-26T01:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "## Nits\n\n1. Rename the helper.\n\n"
            "### Verdict\n\n**Ready for merge**\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_nits = json.dumps({"comments": [nits_at_head], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_nits):
        nit_ok, nit_issues = checker.check_review_comments("2274", "sha123", TEST_REPO)
        check(
            "check_review_comments: a ## Nits heading at HEAD is a finding (#2274)",
            (not nit_ok) and any("Nits" in i for i in nit_issues),
        )

    nits_none_at_head = {
        "createdAt": "2026-08-26T01:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "## Nits\n\nnone identified\n\n"
            "### Verdict\n\n**Ready for merge**\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_nits_none = json.dumps({"comments": [nits_none_at_head], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_nits_none):
        nn_ok, nn_issues = checker.check_review_comments("2274", "sha123", TEST_REPO)
        check(
            "check_review_comments: '## Nits none identified' is not a finding",
            nn_ok and nn_issues == [],
        )

    # Bold-wrapped negations: '**None.**' under an empty section heading is the
    # commonest AI-reviewer phrasing for "nothing here", so the negation suffix
    # must see through leading emphasis markers (review finding on #2298).
    for label, section in (
        ("'## Nits' + '**None.**'", "## Nits\n\n**None.**\n\n"),
        ("'## Nits' + '**None identified.**'", "## Nits\n\n**None identified.**\n\n"),
        ("'## Non-blocking' + '**None.**'", "## Non-blocking\n\n**None.**\n\n"),
    ):
        bold_none_at_head = {
            "createdAt": "2026-08-26T01:00:00Z",
            "author": {"login": "github-actions"},
            "body": (
                "**Claude finished** review\n\n"
                + section
                + "### Verdict\n\n**Ready for merge**\n\n"
                "(reviewed at `sha123`)"
            ),
        }
        mock_bold_none = json.dumps({"comments": [bold_none_at_head], "reviews": []})
        with patch.object(checker, "run_cmd", return_value=mock_bold_none):
            bn_ok, bn_issues = checker.check_review_comments("2298", "sha123", TEST_REPO)
            check(
                f"check_review_comments: {label} is not a finding (#2298)",
                bn_ok and bn_issues == [],
            )

    # Negative controls for the emphasis tolerance above: a bold span that
    # merely OPENS with a negator while carrying a real finding must still be
    # flagged. Only the whole-negation alternatives (none/n-slash-a) tolerate
    # emphasis; nothing/0/no-... deliberately do not (review finding on #2298).
    for label, section in (
        ("bold 'Nothing major, but...' real finding",
         "## Nits\n\n**Nothing major, but the retry loop leaks a file handle on timeout.**\n\n"),
        ("bold '0-day exploit...' real finding",
         "## Nits\n\n**0-day exploit possible in the auth handler.**\n\n"),
        ("bold 'No issues, however...' real finding",
         "## Nits\n\n**No issues, however the login flow is broken.**\n\n"),
        ("bold 'None of the tests...' real finding",
         "## Nits\n\n**None of the tests cover this path.**\n\n"),
    ):
        bold_finding_at_head = {
            "createdAt": "2026-08-26T01:00:00Z",
            "author": {"login": "github-actions"},
            "body": (
                "**Claude finished** review\n\n"
                + section
                + "### Verdict\n\n**Ready for merge**\n\n"
                "(reviewed at `sha123`)"
            ),
        }
        mock_bold_finding = json.dumps(
            {"comments": [bold_finding_at_head], "reviews": []}
        )
        with patch.object(checker, "run_cmd", return_value=mock_bold_finding):
            bf_ok, bf_issues = checker.check_review_comments(
                "2298", "sha123", TEST_REPO
            )
            check(
                f"check_review_comments: {label} IS a finding (#2298)",
                (not bf_ok) and any("Nits" in i for i in bf_issues),
            )

    nits_bold_at_head = {
        "createdAt": "2026-08-26T01:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "**Nits**\n\n1. Rename the helper.\n\n"
            "### Verdict\n\n**Ready for merge**\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_nits_bold = json.dumps({"comments": [nits_bold_at_head], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_nits_bold):
        nb_ok, nb_issues = checker.check_review_comments("2274", "sha123", TEST_REPO)
        check(
            "check_review_comments: a **Nits** heading at HEAD is a finding (#2274)",
            (not nb_ok) and any("Nits" in i for i in nb_issues),
        )

    nonblocking_at_head = {
        "createdAt": "2026-08-26T01:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "## Non-blocking\n\n1. Rename the helper.\n\n"
            "### Verdict\n\n**Ready for merge**\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_nbh = json.dumps({"comments": [nonblocking_at_head], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_nbh):
        nbl_ok, nbl_issues = checker.check_review_comments("2274", "sha123", TEST_REPO)
        check(
            "check_review_comments: a ## Non-blocking heading at HEAD is a "
            "finding (#2274)",
            (not nbl_ok) and any("Non-blocking" in i for i in nbl_issues),
        )

    nonblocking_bold_at_head = {
        "createdAt": "2026-08-26T01:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "**Non-blocking**\n\n1. Rename the helper.\n\n"
            "### Verdict\n\n**Ready for merge**\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_nbb = json.dumps({"comments": [nonblocking_bold_at_head], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_nbb):
        nbb_ok, nbb_issues = checker.check_review_comments("2274", "sha123", TEST_REPO)
        check(
            "check_review_comments: a **Non-blocking** heading at HEAD is a "
            "finding (#2274)",
            (not nbb_ok) and any("Non-blocking" in i for i in nbb_issues),
        )

    inline_nit_at_head = {
        "createdAt": "2026-08-26T01:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "The leftover item is a **nit** and does not block merge.\n\n"
            "This is **non-blocking**.\n\n"
            "### Verdict\n\n**Ready for merge**\n\n"
            "(reviewed at `sha123`)"
        ),
    }
    mock_inline = json.dumps({"comments": [inline_nit_at_head], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_inline):
        il_ok, il_issues = checker.check_review_comments("2274", "sha123", TEST_REPO)
        check(
            "check_review_comments: inline **nit** / **non-blocking** prose "
            "is not a finding heading",
            il_ok and il_issues == [],
        )

    # ai-config#2369: the non- compound must not read as the Blocking signal.
    check("classify_verdict: 'non-blocking' inside a clean verdict stays clean",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge** (one nit -- non-blocking prose polish).\n", "")
          == "clean")
    import re as _re
    check("_BARE_REJECTION no longer matches inside 'non-blocking'",
          not _re.search(checker._BARE_REJECTION,
                         "one nit -- non-blocking prose polish", _re.I))
    check("_BARE_REJECTION no longer matches inside 'non blocking'",
          not _re.search(checker._BARE_REJECTION,
                         "a non blocking suggestion", _re.I))
    # 'previously blocking' is deliberately NOT exempted: the same words
    # appear in genuinely open statements, and missing a not-clean is the
    # dangerous direction. Both directions locked:
    check("classify_verdict: 'previously-blocking finding remains open' stays not-clean",
          checker.classify_verdict(
              "### Verdict\nThe previously-blocking finding remains open; do not merge.\n", "")
          == "not-clean")
    check("classify_verdict: 'previously blocking crash NOT fixed' stays not-clean",
          checker.classify_verdict(
              "### Verdict\nNits below, plus the previously blocking crash which is NOT fixed.\n", "")
          == "not-clean")
    check("a previously blocking failure explicitly fixed is not an active finding",
          checker._unresolved_finding_pattern(
              "### Verdict\n**Ready for merge.** The previously blocking "
              "line-break failure is fixed and confirmed passing.\n")
          is None)
    check("an explicit clean verdict survives a resolved blocking mention",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The previously blocking "
              "line-break failure is fixed and confirmed passing.\n", "")
          == "clean")
    check("a resolved prior verdict blocking issue is not an active finding",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue is resolved.\n", "")
          == "clean")
    check("a curly-apostrophe prior verdict blocking issue can resolve",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict\u2019s blocking "
              "issue is resolved.\n", "")
          == "clean")
    check("a resolved prior issue with a second resolved item stays clean",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue is resolved, and the two follow-up nitpicks are also resolved.\n", "")
          == "clean")
    check("an explicit no-new-issues close preserves the resolution",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue is resolved. I found no new issues in this review.\n", "")
          == "clean")
    for resolution_suffix, label in (
        ("was resolved by the latest commit", "resolution explained by commit"),
        ("was resolved by adding tests", "resolution explained by adding tests"),
        ("was resolved in PR #123", "resolution explained by PR reference"),
        ("was resolved via commit abc1234", "resolution explained by commit sha"),
        ("was resolved with the changes in main.py", "resolution explained by filename changes"),
        ("was resolved as requested", "resolution explained by adverbial as-requested"),
        ("was resolved per review comments", "resolution explained by per-suggestion"),
        ("was resolved by removing the deprecated function", "removing non-detector object"),
        ("was resolved by disabling the deprecated feature flag", "disabling non-detector object"),
        ("was resolved by muting a noisy third-party dependency log", "muting non-detector object"),
        ("was resolved by weakening the coupling between the two modules", "weakening non-detector object"),
        ("was resolved by bypassing the cache to always fetch fresh data", "bypassing non-detector object"),
        ("was resolved", "bare resolved phrase"),
        ("has already been fixed", "adverb already before fixed"),
        ("has since been addressed", "adverb since before addressed"),
    ):
        check(
            f"classify_verdict: prior blocking finding {label} stays clean (#2774)",
            checker.classify_verdict(
                f"### Verdict\n**Ready for merge.** The prior blocking finding {resolution_suffix}.\n",
                "",
            )
            == "clean",
        )
        check(
            f"_unresolved_finding_pattern: prior blocking finding {label} has no finding (#2774)",
            checker._unresolved_finding_pattern(
                f"### Verdict\n**Ready for merge.** The prior blocking finding {resolution_suffix}.\n"
            )
            is None,
        )
    check(
        "classify_verdict: bare 'prior blocking finding was resolved' stays clean (#2774)",
        checker.classify_verdict(
            "### Verdict\n**Ready for merge.** Prior blocking finding was resolved.\n",
            "",
        )
        == "clean",
    )
    check(
        "classify_verdict: possessive finding's blocking issue is resolved stays clean (#2774)",
        checker.classify_verdict(
            "### Verdict\n**Ready for merge.** The prior finding's blocking issue is resolved.\n",
            "",
        )
        == "clean",
    )
    check(
        "classify_verdict: possessive issue's blocking problem is resolved stays clean (#2774)",
        checker.classify_verdict(
            "### Verdict\n**Ready for merge.** The prior issue's blocking problem is resolved.\n",
            "",
        )
        == "clean",
    )
    for hedged_suffix in (
        "was resolved by ignoring it entirely without actually fixing anything",
        "was resolved by a partial patch that does not cover the edge case",
        "was resolved without fixing the bug",
        "was resolved except for the edge cases",
        "was resolved by a patch that fails under load",
        "was resolved by not doing anything",
        "was resolved by skipping tests",
        "was resolved by a patch that remains open",
        "was resolved by code that is broken",
        "was resolved by removing the test that caught it",
        "was resolved by deleting the assertion",
        "was resolved by muting the linter warning",
        "was resolved by reverting the check that flagged it",
        "was resolved by suppressing the error",
        "was resolved by disabling the test",
        "was resolved by commenting out the check",
        "was resolved by weakening the assertion",
        "was resolved by bypassing the check",
        "was resolved by deleting tests",
        "was resolved by removing tests",
        "was resolved by disabling checks",
        "was resolved by commenting out tests",
        "was resolved by muting warnings",
        "was resolved by suppressing errors",
        "was resolved by disabling all checks",
        "was resolved by deleting these tests",
        "was resolved by deleting unit tests",
        "was resolved by a patch that ignores tests",
        "was resolved by code that skips the assertion",
        "was resolved by silencing the test",
    ):
        check(
            f"classify_verdict: hedged resolution '{hedged_suffix}' stays not-clean (#2774)",
            checker.classify_verdict(
                f"### Verdict\n**Ready for merge.** The prior blocking finding {hedged_suffix}.\n",
                "",
            )
            == "not-clean",
        )
        check(
            f"_unresolved_finding_pattern: hedged resolution '{hedged_suffix}' returns finding (#2774)",
            checker._unresolved_finding_pattern(
                f"### Verdict\n**Ready for merge.** The prior blocking finding {hedged_suffix}.\n"
            )
            is not None,
        )

    check(
        "classify_verdict: '### Findings (non-blocking)' heading in clean review stays clean",
        checker.classify_verdict(
            "### Findings (non-blocking)\nNo new issues.\n\n### Verdict\n**Ready for merge.**\n",
            "",
        )
        == "clean",
    )
    check(
        "_unresolved_finding_pattern: '### Findings (non-blocking)' with no new issues produces no finding",
        checker._unresolved_finding_pattern(
            "### Findings (non-blocking)\nNo new issues.\n\n### Verdict\n**Ready for merge.**\n"
        )
        is None,
    )
    check(
        "_unresolved_finding_pattern: '### Findings (non-blocking)' with real finding item blocks",
        checker._unresolved_finding_pattern(
            "### Findings (non-blocking)\n- **scripts/foo.py:42** SQL concatenation bug\n\n### Verdict\n**Ready for merge.**\n"
        )
        is not None,
    )
    check(
        "_unresolved_finding_pattern: '### Nits' with non-blocking item stays not-clean",
        checker._unresolved_finding_pattern(
            "### Nits\nnon-blocking: rename variable x for clarity.\n\n### Verdict\n**Ready for merge.**\n"
        )
        is not None,
    )
    check(
        "_unresolved_finding_pattern: '### Issues' with non-blocking item stays not-clean",
        checker._unresolved_finding_pattern(
            "### Issues\nnon-blocking: there is an off-by-one bug in the loop.\n\n### Verdict\n**Ready for merge.**\n"
        )
        is not None,
    )
    check(
        "classify_verdict: 'Needs more work' with non-blocking trailer stays not-clean",
        checker.classify_verdict(
            "### Verdict\nNeeds more work: non-blocking issue, please rename variable x.\n",
            "",
        )
        == "not-clean",
    )
    check("unrelated unresolved wording in a later paragraph does not poison resolution",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue is resolved.\n\n### Other notes\n" + "x" * 200 + "\n"
              "Unrelated: something else has not been fixed yet, but it is not blocking.\n",
              "")
          == "clean")
    check("a contrasting next sentence can reverse the resolution",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue is fixed. However, it may recur under load.\n", "")
          == "not-clean")
    check("unrecognized next-sentence commentary fails closed",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue is fixed. The full suite also passes.\n", "")
          == "not-clean")
    check("a later reversal in the same paragraph stays a finding",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue is fixed. Great news. However, testing later showed it "
              "still remains open.\n", "")
          == "not-clean")
    for reversal in (
        "Yet it remains open.",
        "Nevertheless it remains unresolved.",
        "Still, it has not been fixed.",
        "Actually it still needs to be fixed.",
        "On second thought, it has not been fixed.",
    ):
        check(f"a next-sentence reversal stays a finding: {reversal}",
              checker.classify_verdict(
                  "### Verdict\n**Ready for merge.** The prior verdict's blocking "
                  f"issue is fixed. {reversal}\n", "")
              == "not-clean")
    check("an unresolved prior verdict blocking issue stays a finding",
          checker.classify_verdict(
              "### Verdict\nThe prior verdict's blocking issue remains open.\n", "")
          == "not-clean")
    check("a prior verdict blocking issue not yet fixed stays a finding",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue has not been fixed.\n", "")
          == "not-clean")
    check("a prior verdict blocking issue requiring a fix stays a finding",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue must be fixed.\n", "")
          == "not-clean")
    check("a prior verdict blocking issue still open stays a finding",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue is still open and must be resolved.\n", "")
          == "not-clean")
    check("an incorrectly addressed prior blocker stays a finding",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The prior verdict's blocking "
              "issue was addressed incorrectly; it remains a blocker.\n", "")
          == "not-clean")
    for separator in (";", ",", ":", " and"):
        check(f"resolution after {separator!r} cannot apply to the prior blocker",
              checker.classify_verdict(
                  "### Verdict\n**Ready for merge.** The prior verdict's blocking "
                  f"issue still reproduces{separator} the unrelated typo was fixed.\n", "")
              == "not-clean")
    for unresolved in (
        "hasn\u2019t been fixed",
        "isn\u2019t fixed",
        "has not actually been fixed",
        "has yet to be fixed",
        "cannot be fixed",
    ):
        check(f"a partly resolved prior blocking issue that {unresolved} stays a finding",
              checker.classify_verdict(
                  "### Verdict\n**Ready for merge.** The prior verdict's blocking "
                  f"issue is now fixed, but {unresolved}.\n", "")
              == "not-clean")
    check("a bold resolved blocking mention is not an active finding",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The previously **blocking** "
              "line-break failure is fixed and confirmed passing.\n", "")
          == "clean")
    check("a resolved blocking mention can cross a semantic line break",
          checker.classify_verdict(
              "### Verdict\n**Ready for merge.** The previously blocking\n"
              "line-break failure is fixed and confirmed passing.\n", "")
          == "clean")
    check("a previously blocking failure that remains open stays a finding",
          checker._unresolved_finding_pattern(
              "### Verdict\nThe previously blocking line-break failure "
              "remains open and must be fixed.\n")
          is not None)
    check("a previously blocking failure that is not fixed stays a finding",
          checker._unresolved_finding_pattern(
              "### Verdict\nThe previously blocking line-break failure is not fixed.\n")
          is not None)
    check("_BARE_REJECTION still matches a bare 'merge-blocking' compound",
          bool(_re.search(checker._BARE_REJECTION, "Two merge-blocking issues remain.", _re.I)))
    check("_BARE_REJECTION still matches plain 'Blocking:'",
          bool(_re.search(checker._BARE_REJECTION, "Blocking: the API change.", _re.I)))

    # ai-config#2370: a findings section that resolves to a whole-line
    # no-findings statement is not an open finding, even when verification
    # prose precedes the closing line.
    # A resolving line reached only AFTER other content never exempts:
    # prose findings are lexically indistinguishable from verification
    # prose, so this shape is a deliberate safe-direction re-flag.
    check("verification prose before the closing line stays a (safe-direction) flag",
          checker._unresolved_finding_pattern(
              "### Findings\n\nVerification performed: traced all call sites.\n\n"
              "No actionable findings identified.\n\n### Verdict: Ready for merge\n")
          is not None)
    check("an untagged PROSE finding above a resolving line stays a finding",
          checker._unresolved_finding_pattern(
              "### Findings\n\n`foo()` returns None on empty input, crashing "
              "the caller.\n\nNo other findings.\n")
          is not None)
    check("a resolving first line with a trailing summary sentence resolves empty",
          checker._unresolved_finding_pattern(
              "### Findings\n\nNone.\n\nThe change is well-scoped and the "
              "tests pass.\n")
          is None)
    check("+ bullet and 1) numbered items veto the exemption",
          all(checker._unresolved_finding_pattern(
                  f"### Findings\n\nNo new issues.\n\n{m} `foo()` crashes.\n")
              is not None for m in ("+", "1)")))
    check("the composite: a bullet-resolving first line no longer covers a "
          "prose finding ('1. None.' does not resolve)",
          checker._unresolved_finding_pattern(
              "### Findings\n\n1. None.\n\nThe lease check is silently "
              "skipped and must be fixed before merge.\n")
          is not None)
    check("a bold-lead line after a resolving first line vetoes the exemption",
          checker._unresolved_finding_pattern(
              "### Findings\n\nNo new issues.\n\n**`_scan()` regression:** "
              "drops rows.\n")
          is not None)
    check("'* No new issues.' stays flagged (exact base vocabulary parity)",
          checker._unresolved_finding_pattern("### Findings\n\n* No new issues.\n")
          is not None)
    check("'- No new issues.' resolves (base's own class accepts the dash)",
          checker._unresolved_finding_pattern("### Findings\n\n- No new issues.\n")
          is None)
    check("a **None.** resolving first line still resolves",
          checker._unresolved_finding_pattern("### Findings\n\n**None.**\n")
          is None)
    check("a **Non-blocking:** tagged line vetoes the exemption",
          checker._unresolved_finding_pattern(
              "### Findings\n\nNo new issues.\n\n**Non-blocking:** naming "
              "could be tidier.\n")
          is not None)
    # Veto tests. The first three bodies carry NOTHING that any other
    # pattern matches, so each stays flagged only through the section logic
    # itself -- neutering _SECTION_FINDING_ITEM flips the veto-dependent
    # cases to exempt, and the resolving-first cases pin the first-line
    # resolution requirement.
    check("tagged item above a resolving last line stays a finding",
          checker._unresolved_finding_pattern(
              "### Findings\n\n1. **[Convention]** scripts/x.py:1 is oddly "
              "wrapped.\n\nNo actionable findings identified.\n")
          is not None)
    check("a resolving first line with a tagged item after it stays a finding",
          checker._unresolved_finding_pattern(
              "### Findings\n\nNone identified so far.\n\n"
              "1. **[Defect]** scripts/x.py:1 broken.\n")
          is not None)
    check("UNTAGGED numbered item above a resolving last line stays a finding",
          checker._unresolved_finding_pattern(
              "### Findings\n\n1. `foo()` returns None on empty input, "
              "crashing the caller.\n\nNo blocking issues.\n")
          is not None)
    check("resolving line FIRST with an item after it stays a finding",
          checker._unresolved_finding_pattern(
              "### Findings\n\nNo new issues.\n\n1. `foo()` returns None.\n")
          is not None)
    check("a **Location:** line above a resolving last line vetoes the exemption",
          not checker._findings_section_resolves_empty(
              "### Findings\n\n**Location:** scripts/x.py:1\n\nNone identified.\n",
              len("### Findings")))
    check("a bulleted '- None.' body still resolves empty (no self-veto)",
          checker._unresolved_finding_pattern(
              "### Findings\n\n- None.\n\n### Verdict: Ready for merge\n")
          is None)
    # ai-config#2459: trailing heading text remains part of the heading line;
    # the empty-section scan begins with the first non-empty body line.
    check("a descriptive Findings heading now re-flags (option (a))",
          checker._unresolved_finding_pattern(
              "## Findings on the diff content\n\nNone.\n")
          is not None)
    check("a plain Findings heading with an empty body still resolves empty",
          checker._unresolved_finding_pattern("## Findings\n\nNone.\n")
          is None)
    check("a plain Findings heading with a real item stays a finding",
          checker._unresolved_finding_pattern(
              "## Findings\n\n1. A real finding\n")
          is not None)
    check("a descriptive Findings heading with a real item stays a finding",
          checker._unresolved_finding_pattern(
              "## Findings on the diff content\n\n1. A real finding\n")
          is not None)
    # ai-config#1233: the exact reported false-positive shapes. Each was
    # confirmed to misfire before #2488/#2506/#2515 landed the resolving-
    # first-line logic above; these pin the fix against the precise wording
    # reported live rather than only the generic "None." cases already
    # covered, since #1233's own shape (multi-line prose trailing the
    # resolving word) had no dedicated regression test.
    check("#1233's own reprex: 'None.' plus multi-line prose resolves",
          checker._unresolved_finding_pattern(
              "### Findings\n\nNone. No CLAUDE.md/lab-manual violations, "
              "no hallucinated symbols/APIs/citations,\nno logic errors, "
              "no duplication of existing corpus content.\n\n"
              "### Verdict\n\n**Ready for merge.**\n")
          is None)
    check("#1233 comment: 'None. <same-line prose>' resolves",
          checker._unresolved_finding_pattern(
              "### Findings\n\nNone. This commit is a well-reasoned, "
              "focused fix.\n\n### Verdict\n\nReady for merge\n")
          is None)
    check("#1233 comment: bare 'None.' with an unbolded verdict resolves",
          checker._unresolved_finding_pattern(
              "### Findings\n\nNone.\n\n### Verdict\n\nReady for merge\n")
          is None)
    # #2488 review round: colon/dash-led trailing text is the section's
    # first content line (a one-line finding written on the heading must
    # not be swallowed); bare descriptive trailing stays decoration.
    check("a colon-led resolving phrase on the heading line exempts",
          checker._unresolved_finding_pattern("## Findings: none\n")
          is None)
    check("a colon-led one-line finding on the heading line is NOT "
          "swallowed by a stray resolving body",
          checker._unresolved_finding_pattern(
              "## Findings: `crash()` is missing a null check\n\nNone.\n")
          is not None)
    check("a dash-led one-line finding on the heading line stays a finding",
          checker._unresolved_finding_pattern(
              "## Findings - missing null check\n")
          is not None)
    # Second #2488-round pass: the separator may appear ANYWHERE in the
    # trailer, in Unicode dash or parenthetical form -- a position-zero
    # ASCII gate left these three swallows.
    check("an em-dash one-line finding is not swallowed",
          checker._unresolved_finding_pattern(
              "## Findings \u2014 crash() is missing a null check"
              "\n\nNone.\n")
          is not None)
    check("a parenthetical one-line finding is not swallowed",
          checker._unresolved_finding_pattern(
              "## Findings (crash() is missing a null check)\n\nNone.\n")
          is not None)
    check("a descriptive prefix before a colon-led finding is not swallowed",
          checker._unresolved_finding_pattern(
              "## Findings on the diff content: crash() missing"
              "\n\nNone.\n")
          is not None)
    check("an em-dash resolving phrase on the heading line exempts",
          checker._unresolved_finding_pattern(
              "## Findings \u2014 none\n")
          is None)
    # Fourth #2488-round pass: a bare space-separated finding on the
    # heading line has no separator at all, so the gate now enumerates
    # DECORATIONS (function-word leads) and fails unknown shapes toward
    # flagging.
    check("a bare clause-shaped heading trailer is not swallowed",
          checker._unresolved_finding_pattern(
              "## Findings the diff has a null pointer bug\n\nNone.\n")
          is not None)
    check("another bare clause-shaped trailer stays a finding",
          checker._unresolved_finding_pattern(
              "## Findings crash breaks on null input\n\nNone.\n")
          is not None)
    # Fifth #2488-round pass: a function-word LEAD alone is not
    # decoration -- the trailer must also be short and free of
    # finding-signal vocabulary.
    check("a function-word-led finding clause with signal vocab flags",
          checker._unresolved_finding_pattern(
              "## Findings regarding null pointer dereference"
              "\n\nNone.\n")
          is not None)
    check("a long function-word-led finding clause flags",
          checker._unresolved_finding_pattern(
              "## Findings on the return value ordering being swapped"
              "\n\nNone.\n")
          is not None)
    check("a signal word beyond the lead still flags",
          checker._unresolved_finding_pattern(
              "## Findings for real this time it is broken\n\nNone.\n")
          is not None)
    # #2499 option (a): ANY heading trailer is content, so decorative
    # suffixes now re-flag -- the recoverable direction, after five
    # rounds showed every decoration enumeration leaves a swallow.
    check("decorative Findings suffixes re-flag under option (a)",
          all(checker._unresolved_finding_pattern(
                  f"## Findings{suffix}\n\nNone.\n") is not None
              for suffix in (" on the diff content", " and notes")))
    # A parenthetical suffix lands on the flag side since the second
    # #2488-round pass: a paren can carry a real finding, and the gate
    # cannot tell "(blocking)" from "(crash() is missing a null check)"
    # without swallowing the latter -- over-flagging is the recoverable
    # direction.
    check("a parenthetical Findings suffix re-flags (safe direction)",
          checker._unresolved_finding_pattern(
              "## Findings (blocking)\n\nNone.\n")
          is not None)
    check("free-prose resolution stays a safe-direction flag (out of #2370 scope)",
          checker._unresolved_finding_pattern(
              "### Findings\n\nI traced everything and found no remaining bugs in the diff.\n")
          is not None)

    # --- Issue #2781: exempt non-blocking or resolved findings headings ---
    check("### Findings (non-blocking) is exempt from unresolved findings (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n- [Nit] Variable could be renamed.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings (Non-blocking) with None resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings (Non-blocking)\n\nNone.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings (non blocking) without hyphen resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings (non blocking)\n\nNone.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Non-blocking Findings resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Non-blocking Findings\n\nNone.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings: non-blocking resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings: non-blocking\n\n- Suggestion: rename foo to bar\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings --- non-blocking resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings \u2014 non-blocking\n\n- Minor formatting note.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings from prior rounds --- now resolved resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings from prior rounds \u2014 now resolved\n\n"
              "- `foo()` crash was fixed in commit abc1234.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings from prior rounds -- now resolved resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings from prior rounds -- now resolved\n\n"
              "- Fixed in abc1234\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings from prior rounds - now resolved resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings from prior rounds - now resolved\n\n"
              "- Fixed in abc1234\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings from previous rounds --- now resolved resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings from previous rounds \u2014 now resolved\n\n"
              "- Resolved.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings (resolved) resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- All items fixed.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings (addressed) resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings (addressed)\n\n"
              "- All feedback addressed.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings (now resolved) resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings (now resolved)\n\n"
              "- Item fixed.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings (all addressed) resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings (all addressed)\n\n"
              "- Items addressed.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Findings: resolved resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings: resolved\n\n"
              "- Resolved.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Resolved Findings resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Resolved Findings\n\n"
              "- Fixed.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Addressed Findings resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Addressed Findings\n\n"
              "- Fixed.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Actionable Findings (resolved) resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Actionable Findings (resolved)\n\n"
              "- Fixed in abc1234.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("### Detailed Findings (non-blocking) resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Detailed Findings (non-blocking)\n\n"
              "- Nit: style.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("full review with Findings (non-blocking) and structured CLEAN payload is clean (#2781)",
          checker.classify_verdict(
              "### Summary\nChecked all files.\n\n"
              "### Findings (non-blocking)\n- Optional nit on naming.\n\n"
              "### Verdict: Ready for merge\n\n"
              "<!-- review-data: {\"schema_version\": \"1.0\", \"verdict\": \"CLEAN\", \"findings\": []} -->\n")
          == "clean")
    check("review with Findings (non-blocking) and structured CLEAN payload has no unresolved findings (#2781)",
          checker._unresolved_finding_pattern(
              "### Summary\nChecked all files.\n\n"
              "### Findings (non-blocking)\n- Optional nit on naming.\n\n"
              "### Verdict: Ready for merge\n\n"
              "<!-- review-data: {\"schema_version\": \"1.0\", \"verdict\": \"CLEAN\", \"findings\": []} -->\n")
          is None)
    check("Findings (blocking) still flags as an unresolved finding (#2781 control)",
          checker._unresolved_finding_pattern(
              "### Findings (blocking)\n\n1. Real crash bug.\n\n"
              "### Verdict\nNeeds work\n")
          is not None)
    check("Findings (unresolved) still flags as an unresolved finding (#2781 control)",
          checker._unresolved_finding_pattern(
              "### Findings (unresolved)\n\n1. Real bug.\n\n"
              "### Verdict\nNeeds work\n")
          is not None)
    check("Findings (not addressed) still flags as an unresolved finding (#2781 control)",
          checker._unresolved_finding_pattern(
              "### Findings (not addressed)\n\n1. Real bug.\n\n"
              "### Verdict\nNeeds work\n")
          is not None)
    check("Findings (non-blocking) beside a real Actionable Findings heading still flags (#2781 control)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n- Nit: style.\n\n"
              "### Actionable Findings\n1. Critical vulnerability.\n\n"
              "### Verdict\nNeeds work\n")
          is not None)
    check("Findings (non-blocking) followed by **Critical** item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **[Critical]** scripts/auth.py:12 authentication bypass vulnerability!\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) followed by **[Defect]** item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **[Defect]** scripts/x.py:10 crashes on empty input.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) followed by **Location:** item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **Location:** scripts/foo.py:10\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) followed by unresolved defect item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- **[Defect]** scripts/x.py:10 is still failing and unresolved.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings from prior rounds --- now resolved citing resolved defect item resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings from prior rounds \u2014 now resolved\n\n"
              "- **[Defect]** `foo()` crash was fixed in commit abc1234.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("Findings from prior rounds --- now resolved with still broken defect flags (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings from prior rounds \u2014 now resolved\n\n"
              "- **[Defect]** `foo()` crash is still broken.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with 'must be fixed before merge' item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **Critical**: security flaw must be fixed before merge.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with 'needs to be addressed' item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **[Defect]**: memory leak needs to be addressed.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with 'will be fixed' item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **[Major]**: crash will be fixed in a later PR.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with 'to be resolved' item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **[Warning]**: missing validation to be resolved.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with 'should be fixed' item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **[Defect]**: race condition should be fixed.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings from prior rounds --- now resolved with 'has been fixed' resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings from prior rounds \u2014 now resolved\n\n"
              "- **[Defect]** `foo()` crash has been fixed in commit abc1234.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("Findings from prior rounds --- now resolved with 'is now resolved' resolves (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings from prior rounds \u2014 now resolved\n\n"
              "- **[Critical]** auth bypass is now resolved.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("Findings (non-blocking) with 'is being fixed in a follow-up PR' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **[Critical]** auth bypass is being fixed in a follow-up PR\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with 'fixed only in happy path; error path still leaks' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **[Defect]** the leak is fixed only in the happy path; error path still leaks\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'was fixed in abc1234 but was later reverted' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- **[Defect]** was fixed in abc1234 but the fix was later reverted\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with generic identifier 'fixed in some_function' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- **[Major]** bug fixed in some_function\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with untagged bullet describing bug is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- SQL injection in query builder\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with untagged numbered item is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "1. Crash occurs when payload is null.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with untagged unresolved bullet is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- Untagged finding still present.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (non-blocking) with explicit Nit bullet resolves cleanly (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- Nit: variable naming could be cleaner.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("Findings (non-blocking) with explicit Suggestion bullet resolves cleanly (#2781)",
          checker._unresolved_finding_pattern(
              "### Findings (non-blocking)\n\n"
              "- Suggestion: add type hints.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("Findings (resolved) with modal-perfect 'should have been fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- this should have been fixed already\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with conditional 'would have been fixed had...' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- this would have been fixed had the patch applied\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with attribution 'the author says this is fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- the author says this is fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with contrasting clause 'was fixed, though...' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- was fixed, though the underlying design flaw remains\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'vulnerable PR was closed without a fix' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- the vulnerable PR was closed without a fix; bug remains in main\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'fix was removed during a later rebase' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- the fix was removed during a later rebase, bug is back\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings -- not fully resolved yet heading is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings -- not fully resolved yet\n\n"
              "- **[Critical]** crash was fixed in commit abc1234.\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'it seems this is fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- it seems this is fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'it looks like this is fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- it looks like this is fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'this seems to have been fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- this seems to have been fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'I hope this is fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- I hope this is fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'in theory this is fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- in theory this is fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'in my opinion this is fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- in my opinion this is fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'in my view this is fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- in my view this is fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'as far as I know this is fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- as far as I know this is fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'to my knowledge this is fixed' is NOT swallowed (#2781 regression)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- to my knowledge this is fixed\n\n"
              "### Verdict\nReady for merge\n")
          is not None)
    check("Findings (resolved) with 'It is fixed in commit abc1234' resolves (#2781 positive)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- It is fixed in commit abc1234.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("Findings (resolved) with 'We fixed this in commit abc1234' resolves (#2781 positive)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- We fixed this in commit abc1234.\n\n"
              "### Verdict\nReady for merge\n")
          is None)
    check("Findings (resolved) with 'The crash they reported is fixed in commit abc1234' resolves (#2781 positive)",
          checker._unresolved_finding_pattern(
              "### Findings (resolved)\n\n"
              "- The crash they reported is fixed in commit abc1234.\n\n"
              "### Verdict\nReady for merge\n")
          is None)

    # --- ai-config#2402: a structured non-bot clean supersedes that same
    # identity's earlier not-clean, and never counts toward quorum. ---------
    human_notclean_round = {
        "createdAt": "2026-08-27T06:44:16Z",
        "author": {"login": "d-morrison"},
        "authorAssociation": "OWNER",
        "body": (
            "### Summary Verdict\nVerdict: Needs more work\n\n"
            "### Critical Findings\n1. The parser drops rows.\n\n"
            "Reviewed-Commit: sha12345678\n"
        ),
    }
    human_clean_round = {
        "createdAt": "2026-08-27T06:53:57Z",
        "author": {"login": "d-morrison"},
        "authorAssociation": "OWNER",
        "body": (
            "### Summary Verdict\nVerdict: Ready for merge\n\n"
            "### Critical Findings\nNone.\n\n"
            "### Observations\nNone.\n\n### Verification Steps\n- suite passes\n\n"
            "Reviewed-Commit: sha12345678\n"
        ),
    }
    bot_clean_round = {
        "createdAt": "2026-08-27T07:00:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished review**\n\n### Verdict\n**Ready for merge**\n\n"
            "Reviewed commit: sha123\n"
        ),
    }
    mock_seq = json.dumps({"comments": [human_notclean_round, human_clean_round,
                                        bot_clean_round], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_seq):
        sup_ok, sup_issues = checker.check_review_comments("2229", "sha123", TEST_REPO)
        check(
            "a structured non-bot clean supersedes the same identity's "
            "earlier not-clean (#2402)",
            sup_ok and sup_issues == [],
        )

    # Without the structured clean round, the human identity's not-clean
    # stands and blocks -- the supersession is what the fix adds.
    mock_stuck = json.dumps({"comments": [human_notclean_round, bot_clean_round],
                             "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_stuck):
        stuck_ok, stuck_issues = checker.check_review_comments("2229", "sha123", TEST_REPO)
        check(
            "the same sequence WITHOUT the clean round still blocks "
            "(negative control)",
            (not stuck_ok) and any("d-morrison" in i for i in stuck_issues),
        )

    # A structured non-bot clean ALONE never meets quorum: approval
    # authority comes from author identity, not body text (#2308).
    mock_solo = json.dumps({"comments": [human_clean_round], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_solo):
        solo_ok, solo_issues = checker.check_review_comments("2229", "sha123", TEST_REPO)
        check(
            "a structured non-bot clean alone does NOT meet quorum (#2308 invariant)",
            (not solo_ok) and any("No valid clean review" in i or "quorum" in i.lower()
                                  for i in solo_issues),
        )

    # SPOOF GUARD: a CONTRIBUTOR pasting an agent marker into a structured
    # clean body must not supersede the real bot's standing not-clean --
    # the identity gate refuses any body whose resolved identity differs
    # from the poster's login.
    bot_notclean_round = {
        "createdAt": "2026-08-27T07:20:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished review**\n\n### Findings\n1. Real defect.\n\n"
            "### Verdict\n**Needs more work**\n\nReviewed commit: sha123\n"
        ),
    }
    spoof_clean = {
        "createdAt": "2026-08-27T07:30:00Z",
        "author": {"login": "drive-by-account"},
        "authorAssociation": "CONTRIBUTOR",
        "body": (
            "**Claude finished review**\n\n### Summary\nAll good.\n\n"
            "### Findings\nNone.\n\n### Verdict\n**Ready for merge**\n\n"
            "Reviewed-Commit: sha12345678\n"
        ),
    }
    # A quorum-satisfying legitimate clean rides along so the assertion
    # discriminates: with the identity gate ablated, the spoof supersedes
    # Claude's not-clean and the cursor clean meets quorum, flipping
    # sp_ok to True -- so this test fails exactly when the gate is lost.
    cursor_clean_round = {
        "createdAt": "2026-08-27T07:25:00Z",
        "author": {"login": "cursor"},
        "body": (
            "### Summary\nLooks good.\n\n### Findings\nNone.\n\n"
            "### Verdict: Ready for merge\n\nReviewed-Commit: sha12345678\n"
        ),
    }
    mock_spoof = json.dumps({"comments": [bot_notclean_round,
                                          cursor_clean_round, spoof_clean],
                             "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_spoof):
        sp_ok, sp_issues = checker.check_review_comments("2229", "sha123", TEST_REPO)
        check(
            "a marker-spoofed contributor clean cannot supersede the bot's "
            "not-clean (identity gate)",
            (not sp_ok) and any("Claude" in i and "NOT clean" in i
                                for i in sp_issues),
        )

    # Structure smuggled inside a fence does not admit: quoting a prior
    # report's headings and fingerprint in a fenced block, plus a bare
    # clean phrase, is still conversational prose.
    fenced_quote = {
        "createdAt": "2026-08-27T07:40:00Z",
        "author": {"login": "d-morrison"},
        "authorAssociation": "OWNER",
        "body": (
            "Quoting the earlier report:\n\n```\n### Verdict\n"
            "Ready for merge\nReviewed-Commit: sha12345678\n```\n\n"
            "Verdict: Ready for merge\n"
        ),
    }
    mock_fenced = json.dumps({"comments": [human_notclean_round, fenced_quote],
                              "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_fenced):
        fq_ok, fq_issues = checker.check_review_comments("2229", "sha123", TEST_REPO)
        check(
            "fenced-quoted structure does not admit a casual clean "
            "(stripped-body structure test)",
            (not fq_ok) and any("NOT clean" in i for i in fq_issues),
        )

    # A casual human comment saying Ready for merge, with no report
    # structure, is still not admitted at all (#1798's guard).
    human_casual = {
        "createdAt": "2026-08-27T07:10:00Z",
        "author": {"login": "d-morrison"},
        "authorAssociation": "OWNER",
        "body": "Looks good to me -- Ready for merge whenever.",
    }
    mock_casual = json.dumps({"comments": [human_notclean_round, human_casual,
                                           bot_clean_round], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_casual):
        cas_ok, cas_issues = checker.check_review_comments("2229", "sha123", TEST_REPO)
        check(
            "a casual unstructured human clean does not supersede (#1798 guard)",
            (not cas_ok) and any("d-morrison" in i for i in cas_issues),
        )

    claude_nits_earlier = {
        "createdAt": "2026-08-07T21:56:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "## Nits\n\n1. Rename the helper.\n\n"
            "### Verdict\n\n**Ready for merge**\n\n"
            "(reviewed at `oldsha00`)"
        ),
    }
    mock_nits_cross = json.dumps({
        "comments": [claude_nits_earlier, agy_clean_at_head],
        "reviews": [],
    })
    with patch.object(checker, "run_cmd", return_value=mock_nits_cross):
        nc_ok, nc_issues = checker.check_review_comments("2274", "sha123", TEST_REPO)
        check(
            "check_review_comments: earlier Claude ## Nits is not cleared by a "
            "later Antigravity all-clear (#2274)",
            (not nc_ok) and any("Claude" in i for i in nc_issues),
        )

    claude_nits_no_verdict = {
        "createdAt": "2026-08-07T21:56:00Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** review\n\n"
            "## Nits\n\n1. Rename the helper.\n\n"
            "(reviewed at `oldsha00`)"
        ),
    }
    mock_unread_nits = json.dumps({
        "comments": [claude_nits_no_verdict, agy_clean_at_head],
        "reviews": [],
    })
    with patch.object(checker, "run_cmd", return_value=mock_unread_nits):
        un_ok, un_issues = checker.check_review_comments("2274", "sha123", TEST_REPO)
        check(
            "check_review_comments: earlier Claude ## Nits without a verdict "
            "line is not cleared by a later Antigravity all-clear (#2274)",
            (not un_ok) and any("Claude" in i for i in un_issues),
        )

    # Ordering, not payload order: the chronology must come from the timestamps,
    # so a clean verdict listed first but dated EARLIER still loses to a later
    # not-clean one.
    mock_out_of_order = json.dumps({
        "comments": [clean_verdict_at_head, {
            "createdAt": "2026-08-07T23:30:00Z",
            "author": {"login": "github-actions"},
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
        "author": {"login": "github-actions"},
        "body": (
            "**Claude finished** --- adversarial review of the whole diff.\n\n"
            "### Verdict\n\n**Needs more work** --- 8 findings below."
        ),
    }
    real_round2 = {
        "createdAt": "2026-08-07T22:49:12Z",
        "author": {"login": "github-actions"},
        "body": (
            "**Round-2 verification** --- adversarial re-check of all eight findings.\n\n"
            "### Verdict\n\n**Needs more work** --- the two items above are the only "
            "outstanding ones. I am correcting both in the next push."
        ),
    }
    real_round3_no_verdict = {
        "createdAt": "2026-08-07T23:05:32Z",
        "author": {"login": "github-actions"},
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


    # Test for #2696 (Option 2): A bot review that states a clean verdict and has NO findings heading,
    # but contains a machine-readable findings count > 0, should be classified as not-clean.
    # This prevents prose-only findings from failing open.
    bot_machine_readable_findings = {
        "createdAt": "2026-08-01T00:00:00Z",
        "author": {"login": "claude"},
        "state": "COMMENT",
        "body": "In response to a prior round, the bug is present.\n\n### Verdict\n**Ready for merge**\n\n[FINDINGS_COUNT: 1]\n\nReviewed-Commit: sha12345678"
    }
    mock_machine_readable = json.dumps({"comments": [bot_machine_readable_findings], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_machine_readable):
        mr_ok, mr_issues = checker.check_review_comments("2696", "sha12345678", TEST_REPO)
    check("a clean verdict with a machine-readable finding count > 0 is not-clean (#2696)",
          not mr_ok and mr_issues and "NOT clean" in mr_issues[0])

    # Control: same thing but count is 0
    bot_machine_readable_zero = {
        "createdAt": "2026-08-01T00:00:00Z",
        "author": {"login": "claude"},
        "state": "COMMENT",
        "body": "In response to a prior round, the bug is fixed.\n\n### Verdict\n**Ready for merge**\n\n[FINDINGS_COUNT: 0]\n\nReviewed-Commit: sha12345678"
    }
    mock_machine_readable_zero = json.dumps({"comments": [bot_machine_readable_zero], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_machine_readable_zero):
        mrz_ok, mrz_issues = checker.check_review_comments("2696", "sha12345678", TEST_REPO)
    check("a clean verdict with [FINDINGS_COUNT: 0] is clean (#2696)",
          mrz_ok and mrz_issues == [])

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

    mock_ci_cancel_superseded = json.dumps({
        "check_runs": [
            {"name": "review / claude-review", "status": "completed",
             "conclusion": "cancelled",
             "html_url": "https://github.com/o/r/actions/runs/1/job/1"},
            {"name": "review / claude-review", "status": "completed",
             "conclusion": "success",
             "html_url": "https://github.com/o/r/actions/runs/2/job/2"},
        ]
    })

    def cancel_superseded_router(cmd):
        joined = " ".join(cmd)
        if "check-runs" in joined:
            return mock_ci_cancel_superseded
        if "/actions/runs/" in joined:
            run_id = cmd[-1].rsplit("/", 1)[-1]
            return json.dumps({
                "path": ".github/workflows/claude-review.yml",
            })
        return "{}"

    with patch.object(checker, "run_cmd", side_effect=cancel_superseded_router):
        cancel_ok, cancel_issues = checker.check_ci_runs("sha123", TEST_REPO)
        check(
            "cancelled check run is ignored when same workflow later succeeded",
            cancel_ok and cancel_issues == [],
        )

    mock_ci_cancel_collision = json.dumps({
        "check_runs": [
            {"name": "ubuntu-latest (release)", "status": "completed",
             "conclusion": "cancelled",
             "html_url": "https://github.com/o/r/actions/runs/1/job/1"},
            {"name": "ubuntu-latest (release)", "status": "completed",
             "conclusion": "success",
             "html_url": "https://github.com/o/r/actions/runs/2/job/2"},
        ]
    })

    def cancel_collision_router(cmd):
        joined = " ".join(cmd)
        if "check-runs" in joined:
            return mock_ci_cancel_collision
        if "/actions/runs/" in joined:
            run_id = cmd[-1].rsplit("/", 1)[-1]
            paths = {
                "1": ".github/workflows/R-CMD-check.yaml",
                "2": ".github/workflows/check-readme.yaml",
            }
            return json.dumps({"path": paths.get(run_id, "")})
        return "{}"

    with patch.object(checker, "run_cmd", side_effect=cancel_collision_router):
        collision_ok, collision_issues = checker.check_ci_runs("sha123", TEST_REPO)
        check(
            "cancelled run is not ignored when success is from a different workflow",
            (not collision_ok)
            and any("cancelled" in i for i in collision_issues),
        )

    # A job name is not unique across workflows (#1869). The live case:
    # ucdavis/bcs has `ubuntu-latest (release)` in BOTH R-CMD-check.yaml and
    # check-readme, and a passing check-readme job was nearly read as the
    # R CMD check having passed while its matrix had not started.
    mock_ci_dupe = json.dumps({
        "check_runs": [
            {"name": "ubuntu-latest (release)", "status": "completed",
             "conclusion": "success",
             "html_url": "https://github.com/o/r/actions/runs/1/job/1"},
            {"name": "ubuntu-latest (release)", "status": "in_progress",
             "conclusion": None,
             "html_url": "https://github.com/o/r/actions/runs/2/job/2"},
            {"name": "unique-job", "status": "in_progress", "conclusion": None,
             "html_url": "https://github.com/o/r/actions/runs/3/job/3"},
        ]
    })
    with patch.object(checker, "run_cmd", return_value=mock_ci_dupe):
        dupe_ok, dupe_issues = checker.check_ci_runs("sha123", TEST_REPO)
    joined = " | ".join(dupe_issues)
    check(
        "a duplicated check-run name is disambiguated by its run URL",
        not dupe_ok
        and "runs/2/job/2" in joined
        and "ubuntu-latest (release)" in joined,
    )
    # A duplicated name with no usable URL must degrade to no annotation, not
    # crash. `check_suite` is documented as `object or null`, and an unhandled
    # AttributeError here would exit 1 -- the status reserved for "not clean" --
    # so a payload quirk would read as a PR regression (#1870 review round 1).
    mock_ci_nourl = json.dumps({
        "check_runs": [
            {"name": "dupe", "status": "in_progress", "conclusion": None,
             "html_url": None, "check_suite": None},
            {"name": "dupe", "status": "completed", "conclusion": "success",
             "html_url": None, "check_suite": None},
        ]
    })
    with patch.object(checker, "run_cmd", return_value=mock_ci_nourl):
        nourl_ok, nourl_issues = checker.check_ci_runs("sha123", TEST_REPO)
    check(
        "a duplicated name with a null html_url and null check_suite does not crash",
        not nourl_ok and nourl_issues == ["Check run 'dupe' is still in status 'in_progress'"],
    )

    check(
        "a unique check-run name is left unannotated",
        any(i.startswith("Check run 'unique-job' is still") for i in dupe_issues),
    )

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

    # --- workflow status notices are not reviews (ai-config#1719) -----------
    #
    # Measured on ai-config#1841 (2026-08-21): its review quota-skipped four
    # times, and the checker reported FULLY CLEAN because a skip notice was
    # admitted as a review, matched HEAD through its own `View run` link, and
    # carried no finding vocabulary. Five of the six distinct bot comment
    # shapes on that PR and its siblings are notices rather than reviews.
    notices = {
        "dispatch": "\U0001f440 **Claude Review Dispatched** -- [run](https://x) reviewing PR #1.",
        "quota skip": "> [!WARNING]\n> **Claude review skipped -- API credential or quota unavailable.** [View run](https://x)",
        "did not finish": "> [!CAUTION]\n> **Claude review did not finish: no verdict, and the denial count was too high to retry.**",
        "cost": "\U0001f4b0 **Cost:** $2.5898 ([review](https://x)) -- [run](https://x)",
        "pr preview": "[PR Preview Action](https://github.com/rossjrw/pr-preview-action) v1.8.1 :---: Preview removed.",
    }
    for label, body in notices.items():
        check(f"{label} notice is not admitted as a review",
              checker.is_non_review_notice(body))

    real_review = (
        "**Claude finished review** -- [View run](https://x)\n\n"
        "## Code review\n\nAll good.\n\n### Verdict\n\n**Ready for merge**"
    )
    check("negative control: a real review is NOT excluded",
          not checker.is_non_review_notice(real_review))

    # The precedence case. A review of THIS corpus routinely quotes the notices,
    # because the notices are what these checks are about -- so a prefix-window
    # match alone would turn a false clean into a false "no review at HEAD".
    review_quoting_notices = (
        "**Claude finished review** -- [View run](https://x)\n\n"
        "The run posted a \U0001f440 **Claude Review Dispatched** notice and then a "
        "**Claude review skipped** warning.\n\n### Verdict\n\n**Ready for merge**"
    )
    check("a real review that QUOTES a notice stays a review",
          not checker.is_non_review_notice(review_quoting_notices))
    check("negative control: that body really does contain a notice marker",
          "claude review dispatched" in review_quoting_notices.lower())

    # A notice marker far into a non-agent body is a mention, not a notice, so
    # the window has to bound the match rather than the whole body.
    late_mention = ("Some analysis.\n\n" + ("x" * 300)
                    + "\n\n\U0001f440 **Claude Review Dispatched**")
    check("a notice marker beyond the prefix window is a mention, not a notice",
          not checker.is_non_review_notice(late_mention))
    check("negative control: the late mention really is past the window",
          late_mention.lower().index("claude review dispatched")
          > checker.NOTICE_PREFIX_WINDOW)

    # End-to-end: the #1841 scenario driven through check_review_comments, not
    # just through the helper. This is the shape that reported FULLY CLEAN --
    # a skip notice citing the head SHA, and nothing else.
    skip_at_head = {
        "createdAt": "2026-08-21T21:13:36Z",
        "author": {"login": "github-actions"},
        "body": ("> [!WARNING]\n> **Claude review skipped -- API credential or "
                 "quota unavailable.** Re-trigger by pushing. Reviewed sha123. "
                 "[View run](https://x)"),
    }
    mock_skip_only = json.dumps({"comments": [skip_at_head], "reviews": []})
    with patch.object(checker, "run_cmd", return_value=mock_skip_only):
        skip_ok, skip_issues = checker.check_review_comments("1841", "sha123", TEST_REPO)
    check("a skip notice alone does NOT report clean",
          not skip_ok and len(skip_issues) > 0)
    check("and it is reported as no review, not as a clean one",
          any("No automated review" in i or "No review comment" in i
              for i in skip_issues))

    # Negative control, MINIMAL: the identical body with only the marker phrase
    # deleted. It will still not read clean (because it lacks an explicit
    # verdict), but it proves the marker's effect because it is now treated as
    # a review rather than being skipped, producing a different failure reason.
    #
    # The earlier version of this control substituted a whole different body (an
    # Antigravity report with an explicit `Verdict: Clean`), so it routed through
    # the precedence branch and never exercised the marker window at all. A
    # mutation check found it inert: with NON_REVIEW_NOTICE_MARKERS replaced by
    # absurd values it still passed. Caught by review on ai-config#1862, and it
    # is the reason this control now differs from the fixture by one phrase.
    control = dict(skip_at_head,
                   body=skip_at_head["body"].replace("Claude review skipped", "Status"))
    check("negative control differs from the fixture by only the marker phrase",
          "claude review skipped" not in control["body"].lower()
          and len(control["body"]) > 0.8 * len(skip_at_head["body"]))
    with patch.object(checker, "run_cmd",
                      return_value=json.dumps({"comments": [control], "reviews": []})):
        ctrl_ok, ctrl_issues = checker.check_review_comments("1841", "sha123", TEST_REPO)
    check("negative control: the same body without the marker NO LONGER reads clean (quorum requires explicit verdict)",
          not ctrl_ok)
    check("negative control: is NOT skipped as a notice (different failure reason)",
          not any("No automated review" in i or "No review comment" in i
                  for i in ctrl_issues))

    # --- review findings on #1862 ------------------------------------------
    #
    # Finding 1. self-review-fallback.md tells a session to post a fallback
    # self-review when the reviewer quota-skips, and the natural opening names
    # the notice it stands in for. The precedence guard used the 3 narrow agent
    # markers while ADMISSION used a wider body-marker set, so such a review was
    # dropped entirely -- verdict and all. A dropped `Needs more work` is worse
    # than the false clean this PR exists to fix, since it also erases the
    # verdict from check_latest_verdict's history.
    fallback_self_review = (
        "The reviewer posted `Claude review skipped -- API quota exhausted`, so "
        "I am posting a fallback self-review.\n\n### Verdict: Needs more work"
    )
    check("a self-review QUOTING the skip notice is not excluded",
          not checker.is_non_review_notice(fallback_self_review))
    check("negative control: it carries no known agent marker, so the wide "
          "body-marker predicate is what saves it",
          checker._detect_review_agent(fallback_self_review) is None
          and checker.has_review_body_marker(fallback_self_review))
    check("and it still classifies as not-clean",
          checker.classify_verdict(fallback_self_review) == "not-clean")

    # The two predicates must not drift apart again: anything wide enough to be
    # ADMITTED as a review must be wide enough to be PROTECTED from exclusion.
    for marker in checker.REVIEW_BODY_MARKERS:
        body = f"\U0001f440 **Claude Review Dispatched** and {marker} here"
        check(f"a body carrying the admission marker {marker!r} is not excluded",
              not checker.is_non_review_notice(body))

    # Finding 2. The AGENT workflow's quota notice, a distinct shape from the
    # review workflow's, documented in the same fragment.
    spend_limit = {
        "createdAt": "2026-08-21T21:00:00Z",
        "author": {"login": "github-actions"},
        "body": "You've hit your org's monthly spend limit. Reviewed sha123. [View run](https://x)",
    }
    check("the spend-limit notice is not admitted as a review",
          checker.is_non_review_notice(spend_limit["body"]))
    with patch.object(checker, "run_cmd",
                      return_value=json.dumps({"comments": [spend_limit], "reviews": []})):
        spend_ok, spend_issues = checker.check_review_comments("1841", "sha123", TEST_REPO)
    check("a spend-limit notice alone does NOT report clean",
          not spend_ok and len(spend_issues) > 0)

    # Every KNOWN REVIEW AGENT must be protected from notice exclusion too.
    # Review on #1862 observed that the `_detect_review_agent(body) or` clause is
    # redundant today, since each agent marker happens to contain a body marker.
    # That is a coincidence of the current tables rather than an invariant, so
    # this pins the property the clause exists for: it passes today through
    # either branch, and keeps passing if an agent marker is added that no body
    # marker covers.
    for agent_marker in checker.REVIEW_AGENT_MARKERS:
        body = f"\U0001f440 **Claude Review Dispatched**\n\n{agent_marker} ..."
        check(f"a body carrying the agent marker {agent_marker!r} is not excluded",
              not checker.is_non_review_notice(body))

    # `run_cmd` must decode as UTF-8 explicitly. On Windows `text=True` alone
    # decodes with cp1252, and a `gh` payload carrying any non-cp1252 byte kills
    # subprocess's reader thread -- leaving returncode 0 and stdout None, so the
    # returncode guard passes and the caller sees an AttributeError instead of a
    # decode error. Asserting on the kwarg rather than on behaviour because the
    # failure only reproduces under a cp1252 locale, which CI does not run.
    class _FakeCompleted:
        returncode = 0
        stdout = "{}"
        stderr = ""

    recorded_kwargs = {}

    def _fake_run(cmd, **kwargs):
        recorded_kwargs.update(kwargs)
        return _FakeCompleted()

    with patch.object(checker.subprocess, "run", _fake_run):
        checker.run_cmd(["gh", "api", "whatever"])
    check("run_cmd decodes subprocess output as UTF-8 explicitly",
          recorded_kwargs.get("encoding") == "utf-8")
    check("negative control: it still captures output",
          recorded_kwargs.get("capture_output") is True)
    # `text` must NOT be pinned: subprocess's docs say text mode is triggered by
    # any of text/encoding/errors/universal_newlines, so `encoding` already
    # selects it. Asserting text=True would turn a redundant kwarg into a tested
    # contract and fail whoever later simplifies the call correctly.
    check("run_cmd does not also pass a redundant text= kwarg",
          "text" not in recorded_kwargs)

    # When stdout IS None despite a zero exit, it must exit 2 rather than raise
    # RuntimeError. Two things depend on that, and a RuntimeError breaks both:
    # `_resolve_run_head_sha` catches RuntimeError and returns None, which would
    # convert this environment failure into a plausible-looking finding bullet;
    # and exit 1 is this script's "not clean" code.
    class _NoneStdout:
        returncode = 0
        stdout = None
        stderr = ""

    with patch.object(checker.subprocess, "run", lambda cmd, **kw: _NoneStdout()):
        try:
            checker.run_cmd(["gh", "api", "whatever"])
            outcome = "returned normally"
        except SystemExit as exc:
            outcome = f"SystemExit:{exc.code}"
        except RuntimeError:
            outcome = "RuntimeError"
        except AttributeError:
            outcome = "AttributeError"
    check("run_cmd exits 2 (not 1) when stdout is None, so it is not a verdict",
          outcome == f"SystemExit:{checker.USAGE_EXIT}")
    check("negative control: and it is neither RuntimeError nor AttributeError",
          outcome not in ("RuntimeError", "AttributeError", "returned normally"))

    # The regression that made `die` mandatory rather than merely tidier: a
    # RuntimeError from run_cmd is swallowed by _resolve_run_head_sha, so the
    # environment failure would surface as an ordinary "no review at this HEAD"
    # finding. Pin that it escapes instead.
    with patch.object(checker.subprocess, "run", lambda cmd, **kw: _NoneStdout()):
        try:
            checker._resolve_run_head_sha(
                "See the run: https://github.com/o/r/actions/runs/123", "o/r"
            )
            escaped = False
        except SystemExit:
            escaped = True
        except Exception:
            escaped = False
    check("a None-stdout failure escapes _resolve_run_head_sha's RuntimeError catch",
          escaped)

    # stderr is exposed to the same reader-thread decode failure as stdout, so a
    # non-zero exit whose stderr came back None must still report the real
    # failure (the command failed) rather than crashing on the diagnostic or
    # interpolating a bare "None" as the reason.
    class _NoneStderr:
        returncode = 1
        stdout = ""
        stderr = None

    with patch.object(checker.subprocess, "run", lambda cmd, **kw: _NoneStderr()):
        try:
            checker.run_cmd(["gh", "api", "whatever"])
            outcome = "returned normally"
        except SystemExit as exc:
            outcome = f"SystemExit:{exc.code}"
        except RuntimeError:
            outcome = "RuntimeError"
        except AttributeError:
            outcome = "AttributeError"
    # A non-zero exit whose stderr could not be decoded is an ENVIRONMENT
    # failure, so it must exit 2 rather than raise RuntimeError. RuntimeError
    # would be caught by `_resolve_run_head_sha`'s `except RuntimeError: return
    # None` and laundered into an ordinary "no review at this HEAD" finding --
    # exit 1 with a bullet, the shape fully-clean.md's crash test cannot see.
    check("a non-zero exit with undecodable stderr exits 2, not RuntimeError",
          outcome == f"SystemExit:{checker.USAGE_EXIT}")

    # Supporting assertion: a non-zero exit WITH readable stderr must still
    # raise RuntimeError, so the fix above did not simply convert every command
    # failure into a hard exit. Without this the assertion above passes for a
    # script that dies on all failures, which would break callers entitled to
    # degrade gracefully on a genuine 404.
    class _RealStderr:
        returncode = 1
        stdout = ""
        stderr = "gh: Not Found (HTTP 404)\n"

    with patch.object(checker.subprocess, "run", lambda cmd, **kw: _RealStderr()):
        try:
            checker.run_cmd(["gh", "api", "whatever"])
            outcome2 = "returned normally"
        except SystemExit:
            outcome2 = "SystemExit"
        except RuntimeError as exc:
            outcome2 = f"RuntimeError:{exc}"
    check("negative control: a readable-stderr failure still raises RuntimeError",
          outcome2.startswith("RuntimeError:") and "404" in outcome2)

    # Test multi-provider quorum logic.
    round_a = {
        "author": {"login": "github-actions[bot]"},
        "createdAt": "2026-08-25T11:00:00Z",
        "body": "**Claude finished** review\n\n### Verdict\n\n**Ready for merge**\n\n(reviewed at `sha123`)",
        "url": "https://github.com/Morrison-Lab/ai-config/pull/2256#issuecomment-1"
    }
    round_b = {
        "author": {"login": "github-actions[bot]"},
        "createdAt": "2026-08-25T12:00:00Z",
        "body": "Verdict: Ready for merge\n\n(reviewed at `sha123`)",
        "url": "https://github.com/Morrison-Lab/ai-config/pull/2256#issuecomment-2"
    }
    with patch.object(checker, "run_cmd", return_value=json.dumps({"comments": [round_a, round_b], "reviews": []})):
        q1_ok, q1_issues = checker.check_review_comments("2256", "sha123", TEST_REPO, quorum=2)
    check("two comments from the same shared-login provider (one marked, one unmarked) do NOT masquerade as two distinct providers",
          not q1_ok and len(q1_issues) > 0)

    round_c = {
        "author": {"login": "d-morrison"},
        "authorAssociation": "MEMBER",
        "createdAt": "2026-08-25T13:00:00Z",
        "body": "Verdict: Ready for merge\n\n(reviewed at `sha123`)\n\n_Posted by Codex (AI agent) --- not written by a human._",
        "url": "https://github.com/Morrison-Lab/ai-config/pull/2256#issuecomment-3"
    }
    with patch.object(checker, "run_cmd", return_value=json.dumps({"comments": [round_a, round_c], "reviews": []})):
        q2_ok, q2_issues = checker.check_review_comments("2256", "sha123", TEST_REPO, quorum=2)
    check("two comments from different providers DO satisfy a quorum of 2",
          q2_ok and len(q2_issues) == 0)


    round_cursor = {
        "author": {"login": "cursor"},
        "authorAssociation": "CONTRIBUTOR",
        "createdAt": "2026-08-25T14:00:00Z",
        "body": "Verdict: Ready for merge\n\n(reviewed at `sha123`)",
        "url": "https://github.com/Morrison-Lab/ai-config/pull/2256#issuecomment-4"
    }
    with patch.object(checker, "run_cmd", return_value=json.dumps({"comments": [round_a, round_cursor], "reviews": []})):
        q3_ok, q3_issues = checker.check_review_comments("2256", "sha123", TEST_REPO, quorum=2)
    check("a cursor-authored clean review counts toward quorum",
          q3_ok and len(q3_issues) == 0)

    # --- ai-config#2449: multi-backtick code spans are citation, too ---------
    # The fix does NOT change the scan text. It builds a parallel mask marking
    # which offsets came from inside a code span of 2+ backticks, and the
    # finding scans ignore a match lying WHOLLY inside it. Four earlier designs
    # blanked more text instead, and each broke a different downstream pass
    # that keys on characters or offsets (ai-config#2515, review rounds 1-4).

    # The line as it appears in the claude-review verdict on #2431.
    real_2431_citation = (
        "## Verdict: Ready for merge\n\nReviewed-Commit: abc1234\n\n"
        "- The exact quoted string @@ Addressed GitHub Claude of @9508454e@ "
        "(Needs more work) @@ matches the real comment verbatim.\n"
    ).replace("@", B)
    check(
        "the measured #2431 double-backtick citation is not read as a verdict (#2449)",
        checker.classify_verdict(real_2431_citation) == "clean",
    )

    single_span_citation = (
        "Verdict: Ready for merge\n\nCited as @Needs more work@ above.\n"
    ).replace("@", B)
    check(
        "single-backtick citation stays blanked (#1202 regression guard)",
        checker.classify_verdict(single_span_citation) == "clean",
    )

    # THE load-bearing invariant, checked against origin/main's ACTUAL
    # function rather than against this module's own. An earlier version of
    # this block compared `scan` to `strip_cited_finding_vocab(probe)`, which
    # is defined as `strip_cited_finding_vocab_with_mask(probe)[0]` -- so it
    # compared f(x)[0] with f(x)[0] and asserted nothing. Reintroducing one of
    # the four rejected designs changed the scan on hundreds of bodies and
    # still passed the whole suite.
    # Stated two ways, because each catches what the other cannot.
    #
    # (a) Directly, with no git dependency, so it also runs in a shallow CI
    #     checkout: the cited phrase must still be PRESENT in the scan and
    #     merely masked. Any design that blanks the span fails this.
    SPAN_PROBES = (
        ("Cited as @@a @x@ (Needs more work) @y@ @@ above.", "(Needs more work)"),
        ("The phrase @@Changes requested@@ is quoted.", "Changes requested"),
        ("See @@**Location:** a.py:1@@ in the template.", "**Location:** a.py:1"),
    )
    for probe, phrase in SPAN_PROBES:
        probe = probe.replace("@", B)
        scan, mask = checker.strip_cited_finding_vocab_with_mask(probe)
        start = scan.find(phrase)
        check(
            f"cited text survives in the scan and is masked, not blanked: {phrase!r}",
            start != -1
            and len(mask) == len(scan)
            and checker.match_is_cited(mask, start, start + len(phrase)),
        )

    # (b) By comparison with the function as it stood before this change, over
    #     probes chosen to hit every downstream consumer a blanking design
    #     broke. An earlier version of this block compared
    #     `strip_cited_finding_vocab(probe)` against itself -- it is defined as
    #     `strip_cited_finding_vocab_with_mask(probe)[0]` -- so it asserted
    #     nothing, and a reintroduced rejected design passed the whole suite.
    import subprocess as _sp
    import tempfile as _tf

    _repo = Path(__file__).resolve().parent.parent
    _base_src = None
    for _rev in ("origin/main", "HEAD~40", "HEAD~20", "HEAD~10"):
        _got = _sp.run(
            ["git", "show", f"{_rev}:scripts/check-pr-fully-clean.py"],
            cwd=_repo, capture_output=True, text=True,
        )
        if _got.returncode == 0:
            _base_src = _got.stdout
            break
    if _base_src is not None:
        _tmp = Path(_tf.mkdtemp()) / "base_checker.py"
        _tmp.write_text(_base_src)
        _bspec = importlib.util.spec_from_file_location("base_checker", _tmp)
        _base = importlib.util.module_from_spec(_bspec)
        _bspec.loader.exec_module(_base)
        identical = True
        for probe in (
            "Cited as @@a @x@ (Needs more work) @y@ @@ above.",
            "A stray @@@ opener in @a.md; Needs more work in @b.md@.",
            "@@-@@ Rejected",
            "The previously-blocking bug in @@a.py@@ is still there; nothing fixed.",
            "Needs @@more@@ work on the guard.",
            'Says "the @@**Location:**@@ marker" but Needs more work.',
            '"@@"@@ Needs more work "',
            "Needs more work in a.py.",
            "A stray @@ opener here.\n@@Needs more work@@ is my verdict.",
            "```\n@@Needs more work@@\n```\nAll good.",
        ):
            probe = probe.replace("@", B)
            if (checker.strip_cited_finding_vocab(probe)
                    != _base.strip_cited_finding_vocab(probe)):
                identical = False
        check(
            "scan text is byte-identical to the pre-change function (#2449)",
            identical,
        )
    # No else-branch failure: a checkout too shallow to reach any prior
    # revision cannot run (b), and (a) already asserts the invariant there.

    for label, probe in (
        ("a 2+ span", "Cited as @@a @x@ (Needs more work) @y@ @@ above."),
        ("no spans at all", "Needs more work in a.py."),
    ):
        probe = probe.replace("@", B)
        scan, mask = checker.strip_cited_finding_vocab_with_mask(probe)
        check(f"mask length tracks scan length: {label}", len(mask) == len(scan))

    # Containment is the discriminator: a phrase wholly inside a span is a
    # citation, one that straddles the boundary is the author's own words.
    straddling = (
        "## Verdict: Ready for merge\n\nNeeds @@more@@ work on the guard.\n"
    ).replace("@", B)
    check(
        "a finding phrase straddling a span boundary still counts (#2449)",
        checker.classify_verdict(straddling) == "not-clean",
    )

    contained = (
        "## Verdict: Ready for merge\n\nThe phrase @@a @x@ Needs more work@@ is quoted.\n"
    ).replace("@", B)
    check(
        "a finding phrase wholly inside a 2+ span does not count (#2449)",
        checker.classify_verdict(contained) == "clean",
    )

    posted_verdict_citation = (
        "This is in response to finding [round 3](https://x) "
        "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**).\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a posted timestamp verdict citation does not count as a finding or block clean verdict",
        checker.classify_verdict(posted_verdict_citation) == "clean"
        and checker._unresolved_finding_pattern(posted_verdict_citation) is None,
    )
    # ... and the SAME sentence without a round-naming link is kept. A
    # bare "in response to" filler was accepted as attribution, which
    # made any unrelated link or phrase into a licence to delete a live
    # verdict.
    unattributed_citation = (
        "This is in response to finding "
        "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**).\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a citation with no round-naming link is NOT stripped",
        checker.classify_verdict(unattributed_citation) == "not-clean",
    )

    # The strip requires a positive attribution signal, and a markdown
    # link naming the round is the only one accepted -- an "in response
    # to" phrase was once accepted in its place and was removed, because
    # it matched any prose containing those words. So the link-attributed
    # narration from ai-config#2662 is stripped even though no resolution
    # wording follows it.
    linked_citation = (
        "This is the author's direct response to "
        "[round 6's finding](https://github.com/x/y/pull/1#issuecomment-2) "
        "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), "
        "per the ARD protocol.\n\n### Verdict\n**Ready for merge**"
    )
    check(
        "a link-attributed posted-verdict citation is stripped",
        checker.classify_verdict(linked_citation) == "clean"
        and checker._unresolved_finding_pattern(linked_citation) is None,
    )
    # Without a round-naming link, the same parenthesized shape is
    # NOT stripped -- an unattributed cited verdict may be a live one.
    bare_paren_citation = (
        "The finding (posted 2026-08-25T10:00:00Z, verdict "
        "**Needs more work**) was noted.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "an unattributed parenthesized posted-verdict is NOT stripped",
        checker.classify_verdict(bare_paren_citation) == "not-clean",
    )
    # The veto window crosses a semantic line break: the re-raise clause on
    # the next line still refuses the strip.
    linebreak_reraise = (
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**)\n"
        "which remains unaddressed.\n\n### Verdict\n**Ready for merge**"
    )
    check(
        "a re-raise across a semantic line break refuses the strip",
        checker.classify_verdict(linebreak_reraise) == "not-clean",
    )
    # The veto window also crosses a dot glued to a following character
    # (a filename), and catches re-raise verbs the first veto list missed.
    glued_dot_reraise = (
        "This is in response to the finding "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**) "
        "which in utils.py still applies.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a re-raise past a glued filename dot refuses the strip",
        checker.classify_verdict(glued_dot_reraise) == "not-clean",
    )
    imperative_reraise = (
        "In response to [round 3](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**) "
        "must be fixed before merge.\n\n### Verdict\n**Ready for merge**"
    )
    check(
        "an imperative re-raise (must be fixed) refuses the strip",
        checker.classify_verdict(imperative_reraise) == "not-clean",
    )
    not_been_addressed = (
        "In response to [round 4](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**) "
        "has not been addressed.\n\n### Verdict\n**Ready for merge**"
    )
    check(
        "a 'not been addressed' re-raise refuses the strip",
        checker.classify_verdict(not_been_addressed) == "not-clean",
    )
    # The veto scans the containing and adjoining paragraphs around the citation:
    # a re-raise stated before the attribution (even in a preceding sentence) refuses
    # the strip, and one in a following paragraph within the section does too.
    backward_reraise = (
        "The finding remains unaddressed in [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**).\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a re-raise BEFORE the citation refuses the strip",
        checker.classify_verdict(backward_reraise) == "not-clean",
    )
    preceding_sentence_reraise = (
        "The blocking issue is still open. [round 2's finding](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**).\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a re-raise in the preceding sentence refuses the strip",
        checker.classify_verdict(preceding_sentence_reraise) == "not-clean",
    )
    following_paragraph_reraise = (
        "[round 2's finding](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**).\n\n"
        "This is still unresolved.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a re-raise in the following paragraph refuses the strip",
        checker.classify_verdict(following_paragraph_reraise) == "not-clean",
    )
    fenced_code_comment_forward_reraise = (
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**), "
        "this was noted in the thread.\n"
        "```\n### not a real heading, just quoted\n```\n"
        "and still remains open.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a forward re-raise past a fenced code block with # comments refuses the strip",
        checker.classify_verdict(fenced_code_comment_forward_reraise) == "not-clean",
    )
    fenced_code_comment_backward_reraise = (
        "This is still unresolved.\n"
        "```python\n# a plain code comment\n```\n"
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**), thanks.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a backward re-raise before a fenced code block with # comments refuses the strip",
        checker.classify_verdict(fenced_code_comment_backward_reraise) == "not-clean",
    )
    fenced_blank_line_forward_reraise = (
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**), noted.\n"
        "```\ncode line 1\n\ncode line 2\n```\n\n"
        "and still remains open.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a forward re-raise past a fenced code block with blank lines refuses the strip",
        checker.classify_verdict(fenced_blank_line_forward_reraise) == "not-clean",
    )
    fenced_blank_line_backward_reraise = (
        "This is still unresolved.\n\n"
        "```\ncode line 1\n\ncode line 2\n```\n"
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**), thanks.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a backward re-raise before a fenced code block with blank lines refuses the strip",
        checker.classify_verdict(fenced_blank_line_backward_reraise) == "not-clean",
    )
    multi_paragraph_forward_reraise = (
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**), noted.\n\n"
        "Just an intervening paragraph with nothing special in it.\n\n"
        "and still remains open.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a forward re-raise across multiple intervening paragraphs refuses the strip",
        checker.classify_verdict(multi_paragraph_forward_reraise) == "not-clean",
    )
    multi_paragraph_backward_reraise = (
        "This is still unresolved.\n\n"
        "Just an intervening paragraph with nothing special in it.\n\n"
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**), thanks.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a backward re-raise across multiple intervening paragraphs refuses the strip",
        checker.classify_verdict(multi_paragraph_backward_reraise) == "not-clean",
    )
    fenced_paragraph_forward_reraise = (
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**), noted.\n\n"
        "```\ncode\n```\n\n"
        "and still remains open.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a forward re-raise separated by a standalone fenced block paragraph refuses the strip",
        checker.classify_verdict(fenced_paragraph_forward_reraise) == "not-clean",
    )
    fenced_paragraph_backward_reraise = (
        "This is still unresolved.\n\n"
        "```\ncode\n```\n\n"
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**), thanks.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a backward re-raise separated by a standalone fenced block paragraph refuses the strip",
        checker.classify_verdict(fenced_paragraph_backward_reraise) == "not-clean",
    )
    long_sentence_reraise = (
        "In response to [round 2](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**) "
        "which, given the considerations enumerated at painful length in "
        "the paragraphs above concerning the overall shape of this change "
        "and its history, still stands as a blocker.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a re-raise far along the same sentence refuses the strip",
        checker.classify_verdict(long_sentence_reraise) == "not-clean",
    )
    for phrase in ("was ignored in this push",
                   "needs to be fixed",
                   "applies unchanged in this diff"):
        vocab_reraise = (
            "In response to [round 2](https://x) "
            "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**) "
            "which " + phrase + ".\n\n### Verdict\n**Ready for merge**"
        )
        check(
            "the re-raise vocabulary covers '" + phrase + "'",
            checker.classify_verdict(vocab_reraise) == "not-clean",
        )
    # The gate recognizes the round-naming link in its several written
    # forms, including a semantic line break after the link tail.
    for label, narration in (
        ("a possessive round reference",
         "This comment responds to [round 6's review](https://x/pull/1#c-2) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), "
         "which has since been addressed."),
        ("a hyphenated round reference",
         "I replied to [round-6 review](https://x/pull/1#c-2) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**)."),
        ("a line break after the link",
         "This is the author's direct response to\n"
         "[round 6's finding](https://x/pull/1#c-2)\n"
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**),\n"
         "per the ARD protocol."),
    ):
        body = narration + "\n\n### Verdict\n**Ready for merge**"
        check(
            "narration with " + label + " is stripped",
            checker.classify_verdict(body) == "clean",
        )
    # The strip is gated on the body stating a verdict of its own: it
    # exists to stop a CITED verdict from overriding the reviewer's own,
    # so with none to protect it must not fire. This bounds the strip
    # structurally rather than by vocabulary, which matters because the
    # veto is a closed word list and this file says elsewhere that such
    # a list cannot enumerate every re-raise phrasing. Each body below
    # is a live rejection whose re-raise is phrased outside that list,
    # or sits in the next sentence entirely.
    for label, unstated in (
        ("a re-raise in the next sentence",
         "In response to [round 2](https://x) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**). "
         "This must be fixed before merge."),
        ("'the bug is present'",
         "In response to [round 2](https://x) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), "
         "the bug is present."),
        ("\"hasn't been fixed\"",
         "In response to [round 2](https://x) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), "
         "it hasn't been fixed."),
        ("'requires a fix'",
         "In response to [round 2](https://x) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), "
         "it requires a fix."),
    ):
        check(
            "no verdict section, so " + label + " is NOT stripped",
            checker.classify_verdict(unstated) == "not-clean",
        )
    # These four reach _RERAISE_VOCAB and the ones above it do not.
    # The citation regex requires its closing paren to be followed
    # IMMEDIATELY by clause punctuation, so a body continuing ") which
    # must ..." never matches the regex at all and is refused before the
    # veto is consulted. Those tests are still correct, but they pass on
    # the lookahead rather than on the vocabulary -- verified by
    # mutation: replacing _RERAISE_VOCAB with a never-matching pattern
    # leaves them green, and flips every case below to clean.
    for label, veto_shape in (
        ("comma then 'still remains'",
         "In response to [round 2](https://x) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), "
         "it still remains a blocker."),
        ("comma then 'must be fixed'",
         "In response to [round 2](https://x) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), "
         "which must be fixed before merge."),
        ("semicolon then 'not been addressed'",
         "In response to [round 2](https://x) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**); "
         "it has not been addressed."),
        # The veto scans the paragraph, so a re-raise in the NEXT
        # sentence is seen; a sentence-bounded scan cleared this one.
        ("a period then 'remains open' in the next sentence",
         "In response to [round 2](https://x) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**). "
         "It remains open."),
    ):
        body = veto_shape + "\n\n### Verdict\n**Ready for merge**"
        check(
            "the veto refuses the strip on " + label,
            checker.classify_verdict(body) == "not-clean",
        )
    # The veto's regions are found by bisect over positions computed
    # once, not by slicing the tail per citation. Slicing re-scanned the
    # rest of the body every time: 400 citations took 1.26s and each
    # doubling quadrupled it, so a cap-sized body of them ran for
    # seconds inside a checker that runs this per review item.
    _cite_unit = (
        "In response to [round 2](https://example.com/x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**), "
        "resolved. "
    )
    _cite_body = "### Verdict\n**Ready for merge.** " + _cite_unit * 555
    _cite_secs, _cite_verdict = best_of_three(
        checker.classify_verdict, _cite_body)
    check(
        "a body packed with citations scans linearly",
        _cite_verdict == "clean" and _cite_secs < 1,
    )
    # Both citation kinds in one body. _SHA_CITATION.sub runs first and
    # replaces a variable-length match with a single space, shifting
    # every position after it -- so the veto's precomputed positions must
    # be built from the post-substitution text. Built from the raw
    # argument, they described a string that no longer existed, and the
    # veto looked for "Still"/"remains unresolved" at the wrong offsets
    # and missed them, stripping a live not-clean.
    both_citations = (
        "**Round 5 review**\n\n"
        "**[Defect] Retry loop does not release the connection-pool lock "
        "on timeout, so a stuck request starves every later request** "
        "reviewed at `a1b2c3d4e5f6789012345678901234567890abcd` is now "
        "Addressed.\n\n"
        "Still, per [round 6's finding](https://x/pull/1#c-2) "
        "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), the "
        "race condition in the retry loop remains unresolved.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a sha citation before a posted citation does not shift the veto",
        checker.classify_verdict(both_citations) == "not-clean",
    )
    # The gap width is swept rather than assumed. A paragraph-hop
    # window read a four-newline gap as two boundaries with an empty
    # phantom paragraph between them and hopped onto the phantom,
    # restoring the fail-open for one extra blank line. The section
    # scan has no paragraph arithmetic left to get this wrong, so the
    # sweep is now a guard against reintroducing any.
    _gap_failures = []
    _gap_citation = (
        "[round 2's finding](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**)."
    )
    for _n in range(2, 9):
        _gap = "\n" * _n
        for _side, _gap_body in (
            ("before", "This remains open." + _gap + _gap_citation),
            ("after", _gap_citation + _gap + "This is still unresolved."),
        ):
            if checker.classify_verdict(
                _gap_body + "\n\n### Verdict\n**Ready for merge**"
            ) != "not-clean":
                _gap_failures.append(_side + ":" + str(_n))
    check(
        "no blank-line gap width hides a re-raise (%d checked)" % (7 * 2),
        not _gap_failures,
    )
    # A "#" comment inside a fence is not a section heading, and
    # treating one as a heading clips the veto region short and strips a
    # live re-raise. The body is kept to one paragraph because that was
    # what isolated the bug from the paragraph-hop window this scan
    # replaced; under the section scan the multi-paragraph form works
    # too, and the single-paragraph shape is retained as the tighter
    # case.
    fenced_hash = (
        "This remains open.\n```\n# c\n```\n"
        "[round 2's finding](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**)."
        "\n\n### Verdict\n**Ready for merge**"
    )
    check(
        "a '#' comment inside a fence does not clip the veto window",
        checker.classify_verdict(fenced_hash) == "not-clean",
    )
    # Including an UNCLOSED fence, whose interior lines the safe default
    # leaves outside fenced_lines -- reachable by a typo, or by GitHub
    # truncating a long comment mid-block.
    # The indented case keeps its "#" at column 0: the heading regex is
    # anchored there, so an indented "#" never matches it fenced or not,
    # and a body using one would pass with fence-awareness entirely
    # broken. What it tests is that an INDENTED FENCE still counts as a
    # fence.
    for _label, _fence in (("unclosed", "```\n# c\n"),
                           ("tilde", "~~~\n# c\n~~~\n"),
                           ("indented", "  ```\n# c\n  ```\n")):
        _body = (
            "This remains open.\n" + _fence
            + "[round 2's finding](https://x) "
            "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**)."
            "\n\n### Verdict\n**Ready for merge**"
        )
        check(
            "a '#' inside a " + _label + " fence does not clip the window",
            checker.classify_verdict(_body) == "not-clean",
        )
    # A real heading DOES clip it, which is the intended boundary.
    real_heading = (
        "This remains open.\n## Section\n"
        "[round 2's finding](https://x) "
        "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**)."
        "\n\n### Verdict\n**Ready for merge**"
    )
    check(
        "a real heading still clips the veto window (control)",
        checker.classify_verdict(real_heading) == "clean",
    )
    # A verdict heading inside a FENCE does not license the strip. The
    # gate runs before fences are removed, and a review of this file
    # quotes that heading in a code block.
    fenced_heading = (
        "In response to [round 2](https://x) "
        "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), "
        "the bug is present.\n\n```\n### Verdict\n```\n"
    )
    check(
        "a verdict heading inside a fence does not license the strip",
        checker.classify_verdict(fenced_heading) == "not-clean",
    )
    # The residual this gate does NOT close, asserted so it is visible
    # rather than discovered: a body stating its own clean verdict, whose
    # only live signal is prose the checker cannot detect as a finding,
    # reads clean once the cited verdict is stripped. That is not a lost
    # detection -- with the citation removed, this same body reads clean
    # on origin/main too, because neither version detects "the bug is
    # present" as a finding. The block origin/main produces here comes
    # entirely from the citation false positive this PR removes, so the
    # two are inseparable. Tracked as ai-config#2696.
    undetectable_prose = (
        "In response to [round 2](https://x) "
        "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**), "
        "the bug is present.\n\n### Verdict\n**Ready for merge**"
    )
    check(
        "a stated clean verdict stands over prose the checker cannot read",
        checker.classify_verdict(undetectable_prose) == "clean",
    )
    control_no_citation = (
        "In response to a prior round, the bug is present."
        "\n\n### Verdict\n**Ready for merge**"
    )
    check(
        "control: the same prose without a citation is already clean",
        checker.classify_verdict(control_no_citation) == "clean",
    )
    # The adversarial direction for the same gate: a real citation with
    # a live requirement riding behind it, and an unrelated link standing
    # in for the attribution. Both classified clean while origin/main
    # classified them not-clean, which is the fail-open this mechanism
    # must never produce.
    for label, live in (
        ("a requirement clause after a real citation",
         "In response to [round 2](https://x) "
         "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**) "
         "which should be fixed before merge."),
        ("a blocker clause after a real citation",
         "In response to [round 2](https://x) "
         "(posted 2026-08-25T10:00:00Z, verdict **Needs more work**) "
         "which is a blocker."),
        ("an unrelated link as the attribution",
         "Confirmed this violates the style guide "
         "[docs](https://example.com/guide) "
         "(posted 2026-08-30T05:22:14Z, verdict **Needs more work**) "
         "so please fix it before merging."),
    ):
        body = live + "\n\n### Verdict\n**Ready for merge**"
        check(
            "a live verdict behind " + label + " is NOT stripped",
            checker.classify_verdict(body) == "not-clean",
        )

    # A LIVE verdict phrased with the same "posted <ts>, verdict **X**"
    # vocabulary, outside parens, is NOT erased -- the same adversarial
    # direction as the #1762 round-1/round-2 regression tests for
    # _SHA_CITATION above.
    live_posted_verdict = (
        "This review was posted 2026-08-30T05:22:14Z, verdict "
        "**Needs more work** because the null check is still missing."
    )
    check(
        "an unparenthesized live 'posted <ts>, verdict' statement is NOT erased",
        checker.classify_verdict(live_posted_verdict) == "not-clean",
    )
    reraised_posted_verdict = (
        "The finding from round 1 was posted 2026-08-25T10:00:00Z, verdict "
        "**Needs more work** and is still present and unaddressed in this "
        "diff.\n\n### Verdict\n**Ready for merge**"
    )
    check(
        "a finding re-raised with 'posted <ts>, verdict' wording is NOT erased",
        checker.classify_verdict(reraised_posted_verdict) == "not-clean",
    )
    # Even a parenthesized citation is kept when the rest of the sentence
    # re-raises the cited verdict as still open.
    still_standing_citation = (
        "The prior verdict (posted 2026-08-30T05:22:14Z, verdict "
        "**Needs more work**) still stands.\n\n"
        "### Verdict\n**Ready for merge**"
    )
    check(
        "a parenthesized verdict citation re-raised as still standing is NOT erased",
        checker.classify_verdict(still_standing_citation) == "not-clean",
    )

    # A negated resolution is a live not-clean statement: the negator sits
    # before the past-state marker, where the suffix scan cannot see it.
    negated_resolution = (
        "### Verdict\nNone of the earlier blocking findings were resolved."
        "\n\nDo not merge."
    )
    check(
        "a negated resolution of earlier blocking findings stays not-clean",
        checker.classify_verdict(negated_resolution) == "not-clean",
    )
    negated_prior = (
        "### Verdict\nNone of the prior blocking findings were resolved."
        "\n\nDo not merge."
    )
    check(
        "a negated resolution of prior blocking findings stays not-clean",
        checker.classify_verdict(negated_prior) == "not-clean",
    )
    for past_word in ("prior", "earlier", "previously", "round-1"):
        negated_short = (
            f"### Verdict\nNo {past_word} blocking findings were resolved.\n\nDo not merge."
        )
        check(
            f"short negated resolution 'No {past_word} blocking... resolved' stays not-clean (#2688)",
            checker.classify_verdict(negated_short) == "not-clean"
            and checker._unresolved_finding_pattern(negated_short) is not None,
        )

    # Negative controls for #2688: non-resolution "No <past-state> blocking findings"
    # must still be exempted by NOT_CLEAN_NEGATION_PREFIX.
    for no_findings_body in (
        "### Verdict\nNo prior blocking findings remain.",
        "### Verdict\nNo prior blocking findings exist.",
        "### Verdict\nNo earlier blocking findings were found.",
        "### Verdict\nNo previously blocking findings.",
    ):
        check(
            f"non-resolution negator exempts: {no_findings_body!r} (#2688 control)",
            checker.classify_verdict(no_findings_body) == ""
            and checker._unresolved_finding_pattern(no_findings_body) is None,
        )
    # A negator anywhere earlier in the sentence blocks the resolved
    # reading, including a fronted clause that negates something else.
    # This is the deliberate over-flag the blunt rule costs: judging what
    # a negator scopes over is a parsing problem, and each lexical proxy
    # tried for it admitted a fresh FALSE CLEAN. A false not-clean stalls
    # a merge until a human looks; a false clean merges over a live
    # rejection.
    fronted_negator = (
        "### Verdict\n**Ready for merge** \u2014 with no new issues, both "
        "round-2 blocking findings (demo caption overclaim, missing "
        "tactics.qmd companion video) are resolved by this round's diff."
    )
    check(
        "a fronted negated clause over-flags, the safe direction",
        checker.classify_verdict(fronted_negator) == "not-clean",
    )
    # The same sentence with the negated clause TRAILING the mention is
    # unaffected, which is the common shape and the one this PR is for.
    trailing_negator = (
        "### Verdict\n**Ready for merge** \u2014 both round-2 blocking "
        "findings (demo caption overclaim, missing tactics.qmd companion "
        "video) are resolved by this round's diff, with no new issues "
        "introduced."
    )
    check(
        "a trailing no-new-issues clause still reads as resolved",
        checker.classify_verdict(trailing_negator) == "clean",
    )
    # A negator in a PRECEDING sentence is out of scope.
    prior_sentence_negator = (
        "### Verdict\n**Ready for merge.** No new issues were found. "
        "The previously blocking findings were resolved by this "
        "round's diff."
    )
    check(
        "a negator in a preceding sentence does not block the resolution",
        checker.classify_verdict(prior_sentence_negator) == "clean",
    )
    # The guard varies what sits BETWEEN the negator and the past-state
    # marker, not just two literal phrasings: a fixed glue whitelist
    # ("of the ...") let a count or modifier through, and a bounded word
    # run then let both a longer run and punctuation inside the negated
    # noun phrase through -- each classifying a negated resolution as
    # clean, the dangerous direction.
    for negation in ("None of the two earlier",
                     "None of the identified earlier",
                     "Not one of the prior",
                     "Neither of the prior",
                     "None of these previously",
                     "None of the several very recently identified earlier",
                     "Not even a single one of the earlier",
                     "Zero of the earlier",
                     "Hardly any of the earlier",
                     "None of the many previously-identified, "
                     "still-outstanding earlier",
                     "None of the (per the last review) earlier",
                     "None of the -- as flagged before -- earlier"):
        varied = (
            "### Verdict\n**Ready for merge.** " + negation
            + " blocking findings were resolved by this round's diff."
        )
        check(
            "a negated resolution reading '" + negation + "' stays not-clean",
            checker.classify_verdict(varied) == "not-clean",
        )
    # A preceding preposition does not exempt a negator. Testing the
    # negator's apparent grammatical role let a governor word prepended
    # to the guard's target phrasing through as clean, for every governor
    # tried -- and adding a required clause boundary did not close it,
    # since the boundary can sit inside the negated noun phrase.
    for governor in ("With", "Without", "Despite", "Besides", "Barring",
                     "Assuming", "Aside from", "Apart from", "Other than"):
        for tail in ("the previously",
                     "the recently reported, previously",
                     "the recently reported; previously",
                     "the following: previously",
                     "the reviewers' concerns, previously"):
            governed = (
                "### Verdict\n**Ready for merge.** " + governor
                + " none of " + tail
                + " blocking findings were resolved by this round's diff."
            )
            check(
                "a governed negator ('" + governor + "' / '" + tail
                + "') stays not-clean",
                checker.classify_verdict(governed) == "not-clean",
            )
    # Nor does a dot that is part of an ellipsis, a URL, or a path:
    # each would otherwise restart the sentence mid-clause and hide the
    # negator before it. The mention's own sentence is what the guard
    # scans, so anything that fakes a sentence end is a fail-open.
    # The whitespace-separated forms matter separately: locating the
    # preceding token by the nearest whitespace alone yields an EMPTY
    # token there, which passes the URL check and accepts the faked
    # sentence end.
    for interrupter in ("the...",
                        "the http://x.io/a.",
                        "the src/a.py.",
                        "the www.example.com.",
                        "the http://x.io/a .",
                        "the /etc/passwd .",
                        "the www.example.com .",
                        "the http://x.io/a\r.",
                        # An exotic whitespace INSIDE the URL must not
                        # end the token early and leave a bare word whose
                        # dot then reads as a real sentence end.
                        "the http://x.io/a\rx.",
                        "the http://x.io/a\vx.",
                        "the http://x.io/a\fx.",
                        "the http://x.io/a\xa0x."):
        faked_end = (
            "### Verdict\n**Ready for merge.** None of " + interrupter
            + " previously blocking finding is resolved."
        )
        check(
            "a faked sentence end ('" + interrupter
            + "') does not hide the negator",
            checker.classify_verdict(faked_end) == "not-clean",
        )
    # The sentence scan runs once per comment body, so it has to stay
    # linear in the body. Finding each candidate's preceding token by
    # slicing and splitting the whole prefix was quadratic, and a body at
    # GitHub's 65536-character comment cap took over five seconds.
    _cap_prefix = "### Verdict\n**Ready for merge.** "
    _cap_suffix = "None of the previously blocking finding is resolved."
    _cap_unit = "x. "
    _cap_body = _cap_prefix + _cap_unit * (
        (65536 - len(_cap_prefix) - len(_cap_suffix)) // len(_cap_unit)
    ) + _cap_suffix
    _cap_secs, _cap_verdict = best_of_three(
        checker.classify_verdict, _cap_body)
    # 2s, not 5s: the quadratic this guards against measured 4.4-4.8s on
    # this exact body, so a 5s bar caught it by 5-12% and would stop
    # catching it on a faster machine. The linear implementation
    # measures under 0.1s, so 2s still leaves more than an order of
    # magnitude of headroom.
    check(
        "a max-length many-sentence body scans linearly and correctly",
        _cap_verdict == "not-clean" and _cap_secs < 2,
    )
    # A faked sentence end was reintroduced twice by fixing one
    # whitespace shape and breaking another, so the shapes are swept
    # rather than enumerated one at a time: each URL-like token, each
    # exotic whitespace character, and each way of arranging them
    # against the punctuation, on BOTH routes that share the scan.
    _faked_end_failures = []
    # Includes characters str.isspace does NOT report (zero-width space,
    # joiners, BOM), which a tool inserts into a long URL to let it
    # soft-wrap, and which were neither skipped nor a token break.
    _gaps = [chr(_x) for _x in (0x0d, 0x0b, 0x0c, 0xa0, 0x200b, 0x200c,
                                0x200d, 0xfeff, 0x180e, 0x2028, 0x2029,
                                0x3000, 0x2000, 0x2009, 0x202f, 0x205f,
                                0x2060, 0xad, 0x200e, 0x200f)]
    for _token in ("http://x.io/a", "/etc/passwd", "www.example.com"):
        for _ws in _gaps:
            for _sep in ("", " ", _ws, " " + _ws, _ws + " ", _ws + "x",
                         " " + _ws + _ws, _ws + " " + _ws):
                _guard = (
                    "### Verdict\n**Ready for merge.** None of the "
                    + _token + _sep
                    + ". previously blocking finding is resolved."
                )
                _veto = (
                    "### Verdict\nThe finding remains unresolved "
                    + _token + _sep
                    + ". in response to it (posted "
                    "2026-08-30T12:00:00Z, verdict **Needs more work**)."
                )
                for _label, _body in (("guard", _guard), ("veto", _veto)):
                    if checker.classify_verdict(_body) != "not-clean":
                        _faked_end_failures.append(
                            _label + ":" + repr(_token + _sep)
                        )
    check(
        "no whitespace arrangement fakes a sentence end (%d checked)"
        % (3 * len(_gaps) * 8 * 2),
        not _faked_end_failures,
    )
    # The marker test must not read past the token's end: startswith
    # runs against the whole text, so a token ending in "www" glued to
    # the sentence's own period otherwise matched on that period and the
    # real sentence end was discarded as a URL.
    check(
        "a token ending in 'www' does not swallow the sentence's period",
        checker._sentence_start_before("a www. b") == 6,
    )
    www_boundary = (
        "### Verdict\n**Ready for merge.** No other findings remain in "
        "www. The previously blocking finding is resolved and confirmed "
        "passing."
    )
    check(
        "a bare 'www' before a sentence end does not force a not-clean",
        checker.classify_verdict(www_boundary) == "clean",
    )
    # The scan must stay linear when NO ascii break is present, since
    # both the backward per-candidate walk and the token slice extend to
    # the start of the text and grow with each candidate. Measured at
    # 5.4s for this body before the two forward pointers replaced them.
    _nbsp = chr(0xa0)
    _dense = ("word" + _nbsp) * 40000 + "." + _nbsp
    _dense_secs, _ = best_of_three(checker._sentence_start_before, _dense)
    check(
        "the sentence scan stays linear with no ascii break present",
        _dense_secs < 1,
    )
    # The citation veto shares the same sentence scan, so a faked
    # sentence end there hides a re-raise instead of a negator, and
    # strips a live not-clean citation into a body stating no verdict
    # at all.
    veto_faked_end = (
        "### Verdict\nThe finding remains unresolved http://x.io/a\rx. "
        "in response to it (posted 2026-08-30T12:00:00Z, verdict "
        "**Needs more work**)."
    )
    check(
        "a faked sentence end does not hide a re-raise from the veto",
        checker.classify_verdict(veto_faked_end) == "not-clean",
    )
    # An abbreviation dot does not restart the sentence, so a negator
    # before it stays in scope rather than being hidden.
    abbreviation_scope = (
        "### Verdict\n**Ready for merge.** None of the round-2 issues "
        "were addressed, e.g. the previously blocking findings were "
        "resolved by this round's diff."
    )
    check(
        "an abbreviation dot does not hide an earlier negator",
        checker.classify_verdict(abbreviation_scope) == "not-clean",
    )

    # Issue #2689: negators inside code spans or quotes must not be hidden
    # from the negated-resolution check by span blanking.
    for quote_label, span_str in (
        ("inline single backtick", "`None of the`"),
        ("inline double backtick", "``None of the``"),
        ("straight double quotes", '"None of the"'),
        ("curly double quotes", "\u201cNone of the\u201d"),
    ):
        masked_negation = (
            f"### Verdict\n**Ready for merge.** {span_str} previously blocking finding is resolved."
        )
        check(
            f"negator in {quote_label} prevents resolved exemption (#2689)",
            checker.classify_verdict(masked_negation) == "not-clean"
            and checker._unresolved_finding_pattern(masked_negation) is not None,
        )

    # Negative control for #2689: affirmative resolutions with unmasked or suffix-masked elements classify clean.
    for clean_label, clean_body in (
        ("unmasked resolution", "### Verdict\n**Ready for merge.** The previously blocking finding is resolved."),
        ("quoted filename in suffix", '### Verdict\n**Ready for merge.** The previously blocking finding in "foo.py" is resolved.'),
        ("code-span filename in suffix", "### Verdict\n**Ready for merge.** The previously blocking finding in `main.py` is resolved."),
        ("parenthesized code span in suffix", "### Verdict\n**Ready for merge.** Both round-2 blocking findings (`auth.py`, `token.py`) are resolved."),
    ):
        check(
            f"{clean_label} classifies clean (#2689 control)",
            checker.classify_verdict(clean_body) == "clean"
            and checker._unresolved_finding_pattern(clean_body) is None,
        )
    # The paren-aside and character branches of the clause scan must stay
    # disjoint: an overlapping `(` was exponential backtracking (51s) on a
    # failing enumeration. Probed on _is_resolved_blocking_mention directly:
    # classify_verdict short-circuits on the leading "Needs more work"
    # before reaching this path, so a whole-body probe passes even on the
    # buggy pattern.
    enumeration_scan = (
        "### Verdict\nNeeds more work: the previously blocking items "
        + "(1) " * 24
        + "are still broken"
    )
    _blocking = re.search(r"\bblocking\b", enumeration_scan, re.IGNORECASE)
    _t0 = time.time()
    _exempted = checker._is_resolved_blocking_mention(
        enumeration_scan, _blocking
    )
    check(
        "a failing enumeration aside neither hangs nor exempts the mention",
        _exempted is False and time.time() - _t0 < 5,
    )

    # The filter guards THREE match loops, and two of them had no test at all:
    # deleting the guard in classify_verdict's clean loop, or in
    # _unresolved_finding_pattern, left the suite green. Both are reachable and
    # both change behaviour, so each gets its own body and its own control
    # (memories/mistake-patterns.md Pattern 15).
    quoted_clean_verdict = (
        "The reviewer wrote @@Verdict: Ready for merge@@ in the template.\n"
    ).replace("@", B)
    check(
        "a quoted clean verdict does not count as stating one (#2449)",
        checker.classify_verdict(quoted_clean_verdict) == "",
    )

    quoted_finding_label = (
        "## Verdict: Ready for merge\n\n"
        "The template line @@**Location:** a.py:1@@ is quoted.\n"
    ).replace("@", B)
    check(
        "a quoted finding label is not an unresolved finding (#2449)",
        checker._unresolved_finding_pattern(quoted_finding_label) is None,
    )

    # An oversized line is left unmasked, so the checker behaves exactly as
    # origin/main does on it -- over-flagging, the safe direction. Guarded
    # because the alternative (masking it) is the fail-open direction, and
    # because the bound exists for a measured quadratic cost.
    over = (
        "## Verdict: Ready for merge\n\n"
        + "x" * (checker._MAX_MASKED_LINE + 1)
        + " @@Needs more work@@\n"
    ).replace("@", B)
    under = (
        "## Verdict: Ready for merge\n\n"
        + "x" * (checker._MAX_MASKED_LINE - 40)
        + " @@Needs more work@@\n"
    ).replace("@", B)
    check(
        "a line over the mask bound is not masked, so it still counts (#2449)",
        checker.classify_verdict(over) == "not-clean",
    )
    check(
        "the same line under the bound is masked (the bound discriminates)",
        checker.classify_verdict(under) == "clean",
    )

    # Test resolved blocking mentions in verdict sections
    resolved_round2 = (
        "### Verdict\n"
        "**Ready for merge** \u2014 both round-2 blocking findings "
        "(demo caption overclaim, missing tactics.qmd companion video) "
        "are resolved by this round's diff, with no new issues introduced."
    )
    check(
        "resolved round-N blocking findings in verdict section classifies clean",
        checker.classify_verdict(resolved_round2) == "clean",
    )
    check(
        "resolved round-N blocking findings does not trigger unresolved finding pattern",
        checker._unresolved_finding_pattern(resolved_round2) is None,
    )

    # match_is_cited is the whole filter, so it is tested directly.
    check("match_is_cited: empty range is never cited",
          not checker.match_is_cited(bytearray(b"\x01\x01"), 1, 1))
    check("match_is_cited: fully covered range is cited",
          checker.match_is_cited(bytearray(b"\x01\x01\x01"), 0, 3))
    check("match_is_cited: partly covered range is NOT cited",
          not checker.match_is_cited(bytearray(b"\x01\x00\x01"), 0, 3))

    # Neutering control. The filter is the only behaviour change, so disabling
    # it must flip the fix and nothing else; a test that still passes with the
    # guarded branch gone guards nothing (memories/mistake-patterns.md #15).
    _real_filter = checker.match_is_cited
    try:
        checker.match_is_cited = lambda mask, start, end: False
        neutered_fix = checker.classify_verdict(real_2431_citation)
        neutered_straddle = checker.classify_verdict(straddling)
    finally:
        checker.match_is_cited = _real_filter
    check(
        "control: disabling the citation filter flips the fix (discriminates)",
        neutered_fix == "not-clean",
    )
    check(
        "control: disabling it does NOT change the straddling case (isolates)",
        neutered_straddle == "not-clean",
    )
    _real_filter2 = checker.match_is_cited
    try:
        checker.match_is_cited = lambda mask, start, end: False
        neutered_clean_loop = checker.classify_verdict(quoted_clean_verdict)
        neutered_finding = checker._unresolved_finding_pattern(quoted_finding_label)
    finally:
        checker.match_is_cited = _real_filter2
    check(
        "control: the clean loop's guard discriminates (#2449)",
        neutered_clean_loop == "clean",
    )
    check(
        "control: _unresolved_finding_pattern's guard discriminates (#2449)",
        neutered_finding is not None,
    )

    # Structured Review JSON parsing tests
    struct_clean = """
## Review Summary
Looks great!

Reviewed-Commit: 3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b

<!-- review-data:
{
  "schema_version": "1.0",
  "reviewer": "Claude",
  "commit_sha": "3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b",
  "verdict": "CLEAN",
  "findings": []
}
-->
"""
    data = checker.extract_structured_review(struct_clean)
    check("extract_structured_review: extracts valid comment payload", data is not None and data.get("verdict") == "CLEAN")
    check("classify_verdict: structured clean review returns clean", checker.classify_verdict(struct_clean) == "clean")
    # The payload's self-declared `reviewer` must NOT confer identity: it is
    # body text the reviewer writes about itself, and two comments from the one
    # `github-actions[bot]` login naming different reviewers otherwise satisfied
    # `--quorum 2`, which shared/workflow/fully-clean.md makes the normal
    # invocation. #2308: approval authority comes from author identity.
    check("_reviewer_identity: a payload's reviewer field does not override the login", checker._reviewer_identity(struct_clean, author="github-actions[bot]") == "github-actions[bot]")
    check("_reviewer_identity: does not escalate unauthenticated member comment to bot identity", checker._reviewer_identity(struct_clean, author="human_member") == "human_member")
    check("_reviewer_identity: agent marker takes precedence over structured reviewer field", checker._reviewer_identity("**claude finished review**\n" + struct_clean.replace('"Claude"', '"adversarial-reviewer"'), author="github-actions[bot]") == "Claude")
    check("_unresolved_finding_pattern: clean structured review has no findings", checker._unresolved_finding_pattern(struct_clean) is None)
    check("_is_structured_review_body: structured review is recognized as structured body", checker._is_structured_review_body(struct_clean))
    check("_is_structured_review_body: casual mention of JSON without heading/fingerprint is NOT structured body", not checker._is_structured_review_body("Here is the JSON format:\n<!-- review-data: {\"verdict\":\"CLEAN\"} -->"))
    check(
        "_is_structured_review_body: multi-line double-backtick span quoting report headings is NOT structured body (#2525)",
        not checker._is_structured_review_body(
            "Discussion of format:\n``\n## Verdict\nReviewed-Commit: 3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b\n``\nCasual prose."
        ),
    )
    check(
        "_is_structured_review_body: stray unclosed backtick in prose does NOT hide genuine headings (#2525)",
        checker._is_structured_review_body(
            "Here is some commentary with a stray ` backtick.\nMore prose.\n\n## Verdict\n\nReviewed-Commit: 3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b\nClean"
        ),
    )

    # Conflicting representations: prose says Needs work with findings, but JSON says CLEAN
    conflicting_body = """
### Findings
1. [Defect] SQL injection in auth handler.

### Verdict: Needs more work

<!-- review-data:
{
  "schema_version": "1.0",
  "reviewer": "Claude",
  "verdict": "CLEAN",
  "findings": []
}
-->
"""
    check("classify_verdict: prose not-clean overrides structured clean", checker.classify_verdict(conflicting_body) == "not-clean")
    check("_unresolved_finding_pattern: prose findings detected despite structured clean", checker._unresolved_finding_pattern(conflicting_body) is not None)

    struct_not_clean = """
## Review Summary
Found defects.

<!-- review-data:
{
  "schema_version": "1.0",
  "reviewer": "Codex",
  "commit_sha": "3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b",
  "verdict": "NOT_CLEAN",
  "findings": [
    {
      "file": "scripts/check-pr-fully-clean.py",
      "line": 42,
      "message": "Null pointer on empty input"
    }
  ]
}
-->
"""
    check("classify_verdict: structured not-clean review returns not-clean", checker.classify_verdict(struct_not_clean) == "not-clean")
    check("_reviewer_identity: a not-clean payload's reviewer field does not override the login", checker._reviewer_identity(struct_not_clean, author="github-actions[bot]") == "github-actions[bot]")
    check("_unresolved_finding_pattern: not-clean structured review returns finding pattern", checker._unresolved_finding_pattern(struct_not_clean) is not None)

    # Findings override clean verdict in structured JSON
    struct_clean_with_findings = """
<!-- review-data:
{
  "verdict": "CLEAN",
  "findings": [{"file": "foo.py", "message": "Bug"}]
}
-->
"""
    check("classify_verdict: structured review with findings classifies not-clean despite CLEAN verdict", checker.classify_verdict(struct_clean_with_findings) == "not-clean")

    # Details tag format
    struct_details = """
<details>
<summary>Structured Review Data</summary>

```json
{
  "schema_version": "1.0",
  "reviewer": "OpenCode",
  "commit_sha": "abc1234567890abcdef1234567890abcdef12345",
  "verdict": "Ready for merge",
  "findings": []
}
```
</details>
"""
    # The <details>-plus-JSON-fence form is deliberately NOT read. The pattern
    # that reached it spanned arbitrary distance and skipped the fence mask, so
    # a reviewer collapsing an earlier round's payload for reference minted a
    # blocking finding no ARD round could discharge (the #2482 class).
    check("extract_structured_review: ignores JSON inside a <details> block", checker.extract_structured_review(struct_details) is None)
    check("classify_verdict: <details> JSON does not supply a clean verdict", checker.classify_verdict(struct_details) != "clean")
    check("_reviewer_identity: <details> JSON does not supply reviewer identity", checker._reviewer_identity(struct_details, author="github-actions[bot]") != "OpenCode")

    struct_details_quoted_blocker = """
<details><summary>Previous round, for reference</summary>

```json
{"verdict": "NOT_CLEAN", "findings": [{"file": "a.py", "message": "example"}]}
```

</details>

### Verdict: Ready for merge
"""
    check("classify_verdict: collapsed earlier payload does not veto a clean verdict", checker.classify_verdict(struct_details_quoted_blocker) == "clean")
    check("_unresolved_finding_pattern: collapsed earlier payload mints no finding", checker._unresolved_finding_pattern(struct_details_quoted_blocker) is None)

    # --- Regression tests for the post-merge adversarial review of #2736 ---

    # F1: the mandated Claude Code disclosure footer must NOT confer reviewer
    # identity. CLAUDE.md requires it on EVERY agent-posted comment -- claims,
    # status updates, replies -- so admitting it made each of those a
    # quorum-eligible automated review, superseding a real bot verdict and
    # satisfying quorum on a PR with no automated review at all. #2308's
    # invariant: approval authority comes from author identity, never body text.
    disclosure_footer = "_Posted by Claude Code (AI agent) --- not written by a human._"
    owner_comment = "- Ready for merge.\n\n" + disclosure_footer
    check("_detect_review_agent: Claude disclosure footer is not an agent marker",
          checker._detect_review_agent(owner_comment) is None)
    check("_reviewer_identity: disclosure footer falls back to the login",
          checker._reviewer_identity(owner_comment, author="d-morrison") == "d-morrison")
    check("is_non_review_notice: a skip notice carrying the footer is still excluded",
          checker.is_non_review_notice(
              "Claude Review Dispatched: usage limit reached.\n\n" + disclosure_footer) is True)
    check("REVIEW_AGENT_MARKERS: every entry still contains a REVIEW_BODY_MARKERS entry",
          all(any(b in k for b in checker.REVIEW_BODY_MARKERS)
              for k in checker.REVIEW_AGENT_MARKERS))

    # F2: the LAST valid payload wins. The persona template a reviewer may quote
    # hardcodes "verdict": "CLEAN", and the authoritative payload comes last --
    # so first-match-wins let a NOT_CLEAN review score clean.
    struct_template_then_real = (
        '**Claude finished** review\n\n'
        'The template reads <!-- review-data: {"verdict": "CLEAN", "findings": []} --> '
        'and you append your own.\n\n'
        '### Verdict: Needs more work\n\n'
        'Reviewed-Commit: 3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b\n\n'
        '<!-- review-data: {"verdict": "NOT_CLEAN", '
        '"findings": [{"file": "a.py", "message": "real"}]} -->'
    )
    check("extract_structured_review: the last valid payload wins over a quoted template",
          (checker.extract_structured_review(struct_template_then_real) or {}).get("verdict")
          == "NOT_CLEAN")
    check("classify_verdict: a quoted CLEAN template cannot mask the real NOT_CLEAN payload",
          checker.classify_verdict(struct_template_then_real) == "not-clean")
    check("_unresolved_finding_pattern: reports the real payload's finding",
          checker._unresolved_finding_pattern(struct_template_then_real)
          == "structured finding in a.py: real")

    # F3: fences were masked, code spans and indented blocks were not -- so a
    # comment merely mentioning the format scored as a clean review at HEAD.
    span_struct = ('Re 3a7b9c1d: the schema is `<!-- review-data: '
                   '{"verdict": "CLEAN", "findings": []} -->` appended after the fingerprint.')
    check("extract_structured_review: ignores a payload inside an inline code span",
          checker.extract_structured_review(span_struct) is None)
    indented_struct = ('Example:\n\n    <!-- review-data: '
                       '{"verdict": "CLEAN", "findings": []} -->\n\ndone.')
    check("extract_structured_review: ignores a payload inside an indented code block",
          checker.extract_structured_review(indented_struct) is None)

    # The structured `commit_sha` term IS present in `is_sha_match`, and is
    # live -- see the escaped-sha case below, which is the ONLY test that
    # catches its deletion.  These three do not: each payload's sha appears
    # verbatim in the body, so `sha_short in body_lower` decides them and they
    # stay green with the structured term removed.  They pin the ordinary
    # behaviour (a prefix of HEAD matches, a different sha does not, and fewer
    # than 7 characters does not); the escaped case pins the term itself.
    prefix_sha = "3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b"

    def _prefix_payload(sha_value):
        return {
            "comments": [
                {
                    "author": {"login": "claude[bot]"},
                    "createdAt": "2026-08-30T20:00:00Z",
                    "authorAssociation": "NONE",
                    "body": ('### Verdict: Ready for merge\n\n'
                             '<!-- review-data: {"schema_version": "1.0", '
                             '"verdict": "CLEAN", "findings": [], '
                             f'"commit_sha": "{sha_value}"}} -->\n'),
                }
            ],
            "reviews": [],
        }

    with patch.object(checker, "run_cmd", return_value=json.dumps(_prefix_payload("3a7b9c1"))):
        ok, _ = wrapped_check_review_comments("123", prefix_sha, "octocat/example", quorum=1)
        check("check_review_comments: a payload naming a 7-character prefix of HEAD matches", ok)

    with patch.object(checker, "run_cmd", return_value=json.dumps(_prefix_payload("deadbeef1234"))):
        ok, _ = wrapped_check_review_comments("123", prefix_sha, "octocat/example", quorum=1)
        check("check_review_comments: a payload naming a different sha does not match", not ok)

    with patch.object(checker, "run_cmd", return_value=json.dumps(_prefix_payload("3a7b9"))):
        ok, _ = wrapped_check_review_comments("123", prefix_sha, "octocat/example", quorum=1)
        check("check_review_comments: a payload naming fewer than 7 characters does not match", not ok)

    # The structured term is NOT subsumed by the body-substring disjuncts, and
    # this is the input that proves it: `json.loads` resolves escapes, so a
    # payload whose `commit_sha` DECODES to a prefix of HEAD need not contain
    # that prefix as literal body text. An earlier cut deleted the term calling
    # it "provably" inert; this case failed closed under that deletion.
    escaped_prefix = "3a7b9c1" .replace("1", chr(92) + "u0031")
    escaped_payload = {
        "comments": [
            {
                "author": {"login": "claude[bot]"},
                "createdAt": "2026-08-30T20:00:00Z",
                "authorAssociation": "NONE",
                "body": ('### Verdict: Ready for merge\n\n'
                         '<!-- review-data: {"schema_version": "1.0", '
                         '"verdict": "CLEAN", "findings": [], '
                         f'"commit_sha": "{escaped_prefix}"}} -->\n'),
            }
        ],
        "reviews": [],
    }
    escaped_body = escaped_payload["comments"][0]["body"]
    check("test fixture: the escaped commit_sha does NOT appear verbatim in the body",
          "3a7b9c1" not in escaped_body.lower())
    check("test fixture: it decodes to a prefix of the target sha",
          (checker.extract_structured_review(escaped_body) or {}).get("commit_sha") == "3a7b9c1")
    with patch.object(checker, "run_cmd", return_value=json.dumps(escaped_payload)):
        ok, _ = wrapped_check_review_comments("123", prefix_sha, "octocat/example", quorum=1)
        check("check_review_comments: a JSON-escaped commit_sha still matches HEAD", ok)

    # A finding object using the persona's own ReportFindings key (`summary`)
    # rather than `message` must still name what it found.
    summary_key_payload = ('### Verdict: Needs more work\n\n'
                           '<!-- review-data: {"verdict": "NOT_CLEAN", "findings": '
                           '[{"file": "b.py", "summary": "off-by-one"}]} -->')
    check("_unresolved_finding_pattern: falls back to a finding's `summary` key",
          checker._unresolved_finding_pattern(summary_key_payload)
          == "structured finding in b.py: off-by-one")

    # --- Regression tests for review round 2 of #2736 ---

    payload_clean = '<!-- review-data: {"verdict": "CLEAN", "findings": []} -->'
    payload_block = ('<!-- review-data: {"verdict": "NOT_CLEAN", "findings": '
                     '[{"file": "a.py", "message": "old"}]} -->')

    # F2: find_fence_spans defaults to swallow_unclosed=False, which records
    # only an UNCLOSED fence's opener line and leaves its interior live. That
    # broke the mask in both directions.
    unclosed_clean = ("**Claude finished** review\n\nReviewers must append:\n\n```json\n"
                      + payload_clean)
    check("extract_structured_review: an unclosed fence's interior is masked too",
          checker.extract_structured_review(unclosed_clean) is None)
    check("classify_verdict: a truncated review quoting a CLEAN template is not clean",
          checker.classify_verdict(unclosed_clean) != "clean")
    unclosed_block = ("### Verdict: Ready for merge\n\n"
                      "Reviewed-Commit: 3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b\n\n"
                      "Prior round, for reference:\n\n```json\n" + payload_block)
    check("classify_verdict: a payload quoted in an unclosed fence mints no veto",
          checker.classify_verdict(unclosed_block) == "clean")
    check("_unresolved_finding_pattern: a payload quoted in an unclosed fence mints no finding",
          checker._unresolved_finding_pattern(unclosed_block) is None)

    # F6: `review-json` was a second accepted spelling with no producer.
    check("extract_structured_review: the review-json spelling is not accepted",
          checker.extract_structured_review(
              '<!-- review-json: {"verdict": "CLEAN", "findings": []} -->') is None)
    check("REVIEW_BODY_MARKERS: carries no review-json entry",
          "review-json:" not in checker.REVIEW_BODY_MARKERS)

    # A real trailing payload must still be read -- the guards above must not
    # have cost the feature they guard.
    real_block = ("### Verdict: Needs more work\n\n"
                  "Reviewed-Commit: 3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b\n\n"
                  + payload_block)
    check("classify_verdict: an unfenced trailing payload is still authoritative",
          checker.classify_verdict(real_block) == "not-clean")

    # `review-data:` as a REVIEW_BODY_MARKERS entry survived deletion with
    # every suite green. It is what stops a payload-only comment from being
    # excluded as a non-review notice.
    payload_only = ('<!-- review-data: {"verdict": "CLEAN", "findings": []} -->')
    check("REVIEW_BODY_MARKERS: carries a review-data entry",
          "review-data:" in checker.REVIEW_BODY_MARKERS)
    check("has_review_body_marker: a payload-only body is a review body",
          checker.has_review_body_marker(payload_only))
    check("is_non_review_notice: a dispatch notice carrying a payload is not excluded",
          checker.is_non_review_notice("Claude Review Dispatched\n\n" + payload_only) is False)

    # A malformed `findings` field must block AND say why. `payload_findings`
    # folds it to `[]`, so the verdict branch would otherwise print the
    # payload's own CLEAN string as the reason it blocked.
    malformed_payload = ('### Verdict: Ready for merge\n\n'
                         '<!-- review-data: {"verdict": "CLEAN", "findings": '
                         '"3 defects listed above"} -->')
    check("classify_verdict: a malformed findings field blocks",
          checker.classify_verdict(malformed_payload) == "not-clean")
    malformed_reason = checker._unresolved_finding_pattern(malformed_payload) or ""
    check("_unresolved_finding_pattern: names the malformed findings field as the cause",
          "not a list" in malformed_reason)
    check("_unresolved_finding_pattern: does not report the payload's CLEAN verdict as the cause",
          "verdict (CLEAN)" not in malformed_reason)

    # Code fence citation guard (quoted structured review in markdown fence is ignored)
    quoted_struct = """
Here is an example of structured review format:
```markdown
<!-- review-data:
{
  "verdict": "CLEAN",
  "findings": []
}
-->
```

Actual review:
### Verdict: Needs more work
"""
    check("extract_structured_review: ignores structured review inside code fence", checker.extract_structured_review(quoted_struct) is None)
    check("classify_verdict: code-fenced structured review does not override real verdict", checker.classify_verdict(quoted_struct) == "not-clean")

    # Malformed JSON safely falls back
    malformed_struct = """
### Verdict: Ready for merge

Reviewed-Commit: 3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b

<!-- review-data:
{
  "verdict": "CLEAN", invalid json here
}
-->
"""
    check("extract_structured_review: malformed JSON returns None", checker.extract_structured_review(malformed_struct) is None)
    check("classify_verdict: malformed structured JSON falls back to regex classification", checker.classify_verdict(malformed_struct) == "clean")

    # Structured NOT_CLEAN with empty findings returns unresolved finding
    struct_not_clean_empty_findings = """
<!-- review-data:
{
  "verdict": "NOT_CLEAN",
  "findings": []
}
-->
"""
    check("_unresolved_finding_pattern: NOT_CLEAN with empty findings returns blocking finding", checker._unresolved_finding_pattern(struct_not_clean_empty_findings) is not None)

    # Structured commit_sha matching in check_review_comments
    target_sha = "3a7b9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b"
    mismatched_sha = "ffffffffffffffffffffffffffffffffffffffff"
    
    clean_struct_payload = {
        "comments": [
            {
                "author": {"login": "claude[bot]"},
                "createdAt": "2026-08-30T20:00:00Z",
                "authorAssociation": "NONE",
                "body": f"""
<!-- review-data:
{{
  "schema_version": "1.0",
  "reviewer": "Claude",
  "commit_sha": "{target_sha}",
  "verdict": "CLEAN",
  "findings": []
}}
-->
""",
            }
        ],
        "reviews": [],
    }
    with patch.object(checker, "run_cmd", return_value=json.dumps(clean_struct_payload)):
        ok, issues = wrapped_check_review_comments("123", target_sha, "octocat/example", quorum=1)
        check("check_review_comments: matches structured commit_sha matching target HEAD", ok and not any(i for i in issues if not i.startswith("NOTE: ")))

    mismatched_struct_payload = {
        "comments": [
            {
                "author": {"login": "claude[bot]"},
                "createdAt": "2026-08-30T20:00:00Z",
                "authorAssociation": "NONE",
                "body": f"""
<!-- review-data:
{{
  "schema_version": "1.0",
  "reviewer": "Claude",
  "commit_sha": "{mismatched_sha}",
  "verdict": "CLEAN",
  "findings": []
}}
-->
""",
            }
        ],
        "reviews": [],
    }
    with patch.object(checker, "run_cmd", return_value=json.dumps(mismatched_struct_payload)):
        ok, issues = wrapped_check_review_comments("123", target_sha, "octocat/example", quorum=1)
        check("check_review_comments: does not match mismatched structured commit_sha", not ok)

    # Partial reviews / truncated diffs must classify as not-clean (#note_14109)
    truncated_review_sample = (
        "🔍 **Auto-review by primary (databricks-gpt-5-6-sol) of MR !50** (75 commit(s), latest: 2ce64536)\n\n"
        "**Partial review:** the supplied MR diff was truncated by 31,743 bytes. This review covers only the provided diff and post-change file contents; the omitted region was not assessed, so this is not approval of the MR as a whole.\n\n"
        "Within the available scope, I found no new actionable defects."
    )
    check("classify_verdict: partial review with truncated diff classifies as not-clean",
          checker.classify_verdict(truncated_review_sample) == "not-clean")
    check("_unresolved_finding_pattern: partial review triggers finding pattern",
          checker._unresolved_finding_pattern(truncated_review_sample) is not None)

    # Timing regression tests on many small fenced blocks (#2719).
    # Multiline \s* backtracking across thousands of stripped blank lines and
    # redundant fence parsing caused quadratic scaling (over 8s at comment cap).
    _small_fence_unit = "```\nx\n```\n"
    _fenced_no_verdict = "Some prose\n" + _small_fence_unit * 6500
    _fnv_secs, _fnv_verdict = best_of_three(
        checker.classify_verdict, _fenced_no_verdict
    )
    check(
        "classify_verdict on max-length body of small fenced blocks scales linearly (< 1s)",
        _fnv_verdict == "" and _fnv_secs < 1.0,
    )

    _fenced_clean = "### Verdict\n**Ready for merge.**\n" + _small_fence_unit * 4000
    _fc_secs, _fc_verdict = best_of_three(
        checker.classify_verdict, _fenced_clean
    )
    check(
        "classify_verdict clean on many small fenced blocks scales linearly (< 1s)",
        _fc_verdict == "clean" and _fc_secs < 1.0,
    )

    _uf_secs, _uf_res = best_of_three(
        checker._unresolved_finding_pattern, _fenced_no_verdict
    )
    check(
        "_unresolved_finding_pattern on many small fenced blocks scales linearly (< 1s)",
        _uf_res is None and _uf_secs < 1.0,
    )

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
