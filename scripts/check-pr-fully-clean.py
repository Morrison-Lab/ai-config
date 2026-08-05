#!/usr/bin/env python3
"""Automated verification tool for ARDI / fully-clean status.

Verifies that:
1. All GitHub Actions check runs for the PR's HEAD commit SHA are completed and passing.
2. A review comment evaluating the exact HEAD commit SHA has been posted.
3. The latest review comment for the HEAD commit SHA contains zero actionable findings.

Exit codes:
0: Fully clean (safe to end ARDI loop)
1: Not clean (in-progress checks, failing checks, missing review, or findings present)
"""
import json
import re
import subprocess
import sys
from typing import Dict, List, Tuple


def run_cmd(cmd: List[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed ({' '.join(cmd)}): {res.stderr}")
    return res.stdout.strip()


def get_pr_info(pr_num: str) -> Tuple[str, str, str]:
    out = run_cmd(["gh", "pr", "view", pr_num, "--json", "headRefOid,headRefName,state"])
    data = json.loads(out)
    return data["headRefOid"], data["headRefName"], data["state"]


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


def check_review_comments(pr_num: str, sha: str) -> Tuple[bool, List[str]]:
    out = run_cmd(["gh", "pr", "view", pr_num, "--json", "comments,reviews"])
    data = json.loads(out)

    comments = data.get("comments", [])
    reviews = data.get("reviews", [])

    issues = []
    # Collect all bot review comments/reviews
    all_items = []
    for c in comments:
        if c.get("author", {}).get("login") in ("github-actions", "github-actions[bot]", "claude[bot]"):
            all_items.append(("comment", c["createdAt"], c["body"]))
    for r in reviews:
        if r.get("author", {}).get("login") in ("github-actions", "github-actions[bot]", "claude[bot]"):
            commit_oid = r.get("commit", {}).get("oid", "")
            all_items.append(("review", r.get("submittedAt", ""), r.get("body", ""), commit_oid))

    if not all_items:
        issues.append(f"No automated review comments or reviews found on PR #{pr_num}")
        return False, issues

    # Find items mentioning the current commit SHA or posted for the commit
    sha_short = sha[:7]
    matching_items = []
    for item in all_items:
        body = item[2]
        oid = item[3] if len(item) > 3 else ""
        if oid == sha or sha_short in body or sha in body:
            matching_items.append(item)

    if not matching_items:
        issues.append(f"No review comment has been posted evaluating HEAD SHA {sha[:8]} yet")
        return False, issues

    # Inspect the latest matching review comment
    latest_body = matching_items[-1][2]

    # Check for finding indicators
    finding_patterns = [
        r"### Actionable Findings",
        r"### Detailed Findings",
        r"Verdict:\s*Ready after addressing findings",
        r"Verdict:\s*Needs work",
        r"Verdict:\s*Changes requested",
        r"#### \d+\.",
    ]

    has_findings = False
    for pat in finding_patterns:
        if re.search(pat, latest_body, re.IGNORECASE):
            has_findings = True
            issues.append(f"Latest review comment for SHA {sha[:8]} contains findings (matched pattern '{pat}')")

    if not has_findings:
        print(f"✓ Found clean review comment evaluating HEAD SHA {sha[:8]}")

    return len(issues) == 0, issues


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/check-pr-fully-clean.py <pr-number>")
        sys.exit(1)

    pr_num = sys.argv[1]
    print(f"Checking ARDI / fully-clean status for PR #{pr_num}...")

    sha, branch, state = get_pr_info(pr_num)
    print(f"PR #{pr_num} ({branch}): state={state}, HEAD={sha[:8]}")

    ci_ok, ci_issues = check_ci_runs(sha)
    review_ok, review_issues = check_review_comments(pr_num, sha)

    all_issues = ci_issues + review_issues

    if all_issues:
        print("\n❌ PR is NOT fully clean:")
        for issue in all_issues:
            print(f"  - {issue}")
        sys.exit(1)

    print(f"\n✅ PR #{pr_num} is FULLY CLEAN on HEAD {sha[:8]}!")
    sys.exit(0)


if __name__ == "__main__":
    main()
