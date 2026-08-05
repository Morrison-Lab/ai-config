#!/usr/bin/env python3
"""Automated verification tool for ARDI / fully-clean status.

Verifies that:
1. All GitHub Actions check runs for the PR's HEAD commit SHA are completed and passing.
2. An automated review comment evaluating the exact HEAD commit SHA has been posted.
3. All review comments evaluating the HEAD commit SHA contain zero findings, and no active CHANGES_REQUESTED or REJECTED state exists on the PR.

Exit codes:
0: Fully clean (safe to end ARDI loop)
1: Not clean (in-progress checks, failing checks, missing review, or findings present)
"""
from datetime import datetime, timedelta
import json
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


def run_cmd(cmd: List[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed ({' '.join(cmd)}): {res.stderr}")
    return res.stdout.strip()


def parse_iso_time(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_pr_info(pr_num: str) -> Tuple[str, str, str, str]:
    out = run_cmd(["gh", "pr", "view", pr_num, "--json", "headRefOid,headRefName,state,commits"])
    data = json.loads(out)
    head_sha = data["headRefOid"]
    commits = data.get("commits", [])
    commit_date = ""
    if commits:
        commit_date = commits[-1].get("committedDate", "")
    return head_sha, data["headRefName"], data["state"], commit_date


def check_ci_runs(sha: str) -> Tuple[bool, List[str]]:
    out = run_cmd(["gh", "api", f"repos/Morrison-Lab/ai-config/commits/{sha}/check-runs?per_page=100"])
    data = json.loads(out)
    check_runs = data.get("check_runs", [])

    issues = []
    if not check_runs:
        issues.append(f"No check runs found for SHA {sha[:8]}")
        return False, issues

    for cr in check_runs:
        name = cr["name"]
        status = cr["status"]
        conclusion = cr.get("conclusion")

        if status != "completed":
            issues.append(f"Check run '{name}' is still in status '{status}'")
        elif conclusion not in ("success", "neutral", "skipped"):
            issues.append(f"Check run '{name}' completed with conclusion '{conclusion}'")

    return len(issues) == 0, issues


def check_review_comments(pr_num: str, sha: str, commit_date: str) -> Tuple[bool, List[str]]:
    out = run_cmd(["gh", "pr", "view", pr_num, "--json", "comments,reviews"])
    data = json.loads(out)

    comments = data.get("comments", [])
    reviews = data.get("reviews", [])

    issues = []

    # Track the latest formal review state per author chronologically across all reviews
    author_latest_state: Dict[str, str] = {}
    for r in reviews:
        author = (r.get("author") or {}).get("login", "")
        state = r.get("state", "").upper()
        if author and state:
            author_latest_state[author] = state

    for author, state in author_latest_state.items():
        if state in ("CHANGES_REQUESTED", "REJECTED"):
            issues.append(f"PR has active formal review state '{state}' from {author}")

    # Collect automated review reports only (filtering out human/author disposition comments)
    all_items = []
    for c in comments:
        body = c.get("body", "")
        body_lower = body.lower()
        author_login = (c.get("author") or {}).get("login", "")

        if "ard review disposition summary" in body_lower:
            continue

        is_bot_author = author_login in ("github-actions", "github-actions[bot]", "claude[bot]", "claude")
        is_review_header = any(marker in body_lower for marker in ("\ud83e\udd16", "### 🤖", "code review", "claude finished review", "verdict:"))

        if is_bot_author or is_review_header:
            all_items.append(("comment", c["createdAt"], body, "", "COMMENT"))

    for r in reviews:
        body = r.get("body", "")
        commit_oid = r.get("commit", {}).get("oid", "")
        state = r.get("state", "").upper()
        submitted_at = r.get("submittedAt", "")
        if body or commit_oid or state in ("CHANGES_REQUESTED", "REJECTED"):
            all_items.append(("review", submitted_at, body, commit_oid, state))

    if not all_items:
        issues.append(f"No automated review comments or reviews found on PR #{pr_num}")
        return False, issues

    # Match items evaluating the target HEAD commit SHA
    sha_short = sha[:7]
    commit_dt = parse_iso_time(commit_date)

    matching_items = []
    for item in all_items:
        created_at_dt = parse_iso_time(item[1])
        body = item[2]
        body_lower = body.lower()
        oid = item[3]

        is_sha_match = bool((oid and oid == sha) or sha_short in body or sha in body)
        # Allow a 60-second clock skew tolerance window for commit vs server creation time
        is_timing_match = bool(
            commit_dt
            and created_at_dt
            and created_at_dt >= (commit_dt - timedelta(seconds=60))
            and (is_sha_match or not oid)
            and any(marker in body_lower for marker in ("\ud83e\udd16", "### 🤖", "code review", "claude finished review", "verdict"))
        )

        if is_sha_match or is_timing_match:
            matching_items.append(item)

    if not matching_items:
        issues.append(f"No review comment has been posted evaluating HEAD SHA {sha[:8]} yet")
        return False, issues

    # Inspect ALL matching items for HEAD SHA    # Precise finding patterns (avoiding false positives on clean review summaries)
    finding_patterns = [
        r"#+\s*(Actionable\s+|Detailed\s+)?Findings",
        r"\*\*Actionable Findings\*\*",
        r"\*\*Detailed Findings\*\*",
        r"#+\s*Issues",
        r"#+\s*Remaining",
        r"\*\*Location:\*\*",
        r"Verdict:\s*(Ready after addressing findings|Needs work|Needs more work|Changes requested|Actionable findings)",
        r"\bNeeds\s+more\s+work\b",
        r"\bNeeds\s+work\b",
        r"changes\s+requested\b",
    ]

    has_findings = False
    for item in matching_items:
        body = item[2]
        state = item[4]
        if state in ("CHANGES_REQUESTED", "REJECTED"):
            has_findings = True
            issues.append(f"Matching review for SHA {sha[:8]} has state '{state}'")

        for pat in finding_patterns:
            for match in re.finditer(pat, body, re.IGNORECASE | re.MULTILINE):
                if pat == r"changes\s+requested\b":
                    start = match.start()
                    prefix = body[max(0, start - 25):start].lower()
                    if re.search(r"\bno\s+(\w+\s+)?$", prefix):
                        continue
                has_findings = True
                issues.append(f"Review comment for SHA {sha[:8]} contains findings (matched pattern '{pat}')")

    if not has_findings and not issues:
        print(f"\u2713 Found clean review comment evaluating HEAD SHA {sha[:8]}")

    return len(issues) == 0, issues


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/check-pr-fully-clean.py <pr-number>")
        sys.exit(1)

    pr_num = sys.argv[1]
    print(f"Checking ARDI / fully-clean status for PR #{pr_num}...")

    sha, branch, state, commit_date = get_pr_info(pr_num)
    print(f"PR #{pr_num} ({branch}): state={state}, HEAD={sha[:8]} (committed {commit_date})")

    ci_ok, ci_issues = check_ci_runs(sha)
    review_ok, review_issues = check_review_comments(pr_num, sha, commit_date)

    all_issues = ci_issues + review_issues

    if all_issues:
        print("\n\u274c PR is NOT fully clean:")
        for issue in all_issues:
            print(f"  - {issue}")
        sys.exit(1)

    print(f"\n\u2705 PR #{pr_num} is FULLY CLEAN on HEAD {sha[:8]}!")
    sys.exit(0)


if __name__ == "__main__":
    main()
