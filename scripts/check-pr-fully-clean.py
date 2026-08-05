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
from datetime import datetime
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


def parse_iso_time(ts: str) -> datetime | None:
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
    # Collect all automated review reports (case-insensitive marker filtering)
    all_items = []
    for c in comments:
        body = c.get("body", "")
        body_lower = body.lower()
        if "### 🤖" in body or "code review" in body_lower or "claude finished review" in body_lower or "verdict" in body_lower:
            all_items.append(("comment", c["createdAt"], body))

    for r in reviews:
        body = r.get("body", "")
        commit_oid = r.get("commit", {}).get("oid", "")
        if body or commit_oid:
            all_items.append(("review", r.get("submittedAt", ""), body, commit_oid))

    if not all_items:
        issues.append(f"No automated review comments or reviews found on PR #{pr_num}")
        return False, issues

    # Match items for HEAD commit SHA:
    # 1. Matching commit OID (from reviews API)
    # 2. SHA or short SHA in comment body
    # 3. Created on or after the HEAD commit's timestamp AND contains review report header
    sha_short = sha[:7]
    commit_dt = parse_iso_time(commit_date)

    matching_items = []
    for item in all_items:
        created_at_dt = parse_iso_time(item[1])
        body = item[2]
        body_lower = body.lower()
        oid = item[3] if len(item) > 3 else ""

        is_sha_match = (oid == sha or sha_short in body or sha in body)
        is_timing_match = bool(
            commit_dt
            and created_at_dt
            and created_at_dt >= commit_dt
            and ("### 🤖" in body or "code review" in body_lower or "claude finished review" in body_lower or "verdict" in body_lower)
        )

        if is_sha_match or is_timing_match:
            matching_items.append(item)

    if not matching_items:
        issues.append(f"No review comment has been posted evaluating HEAD SHA {sha[:8]} yet")
        return False, issues

    # Sort matching items chronologically by timestamp
    matching_items.sort(key=lambda x: x[1])

    # Inspect the latest matching review comment
    latest_item = matching_items[-1]
    latest_body = latest_item[2]

    # Check for finding indicators
    finding_patterns = [
        r"###\s*(Actionable\s+|Detailed\s+)?Findings",
        r"\*\*Findings\b",
        r"Findings\s*\(posted\s+inline",
        r"###\s*Issues",
        r"###\s*Remaining",
        r"\*\*Location:\*\*",
        r"Verdict:\s*(Ready after addressing findings|Needs work|Needs more work|Changes requested|Actionable findings)",
        r"\bNeeds\s+more\s+work\b",
        r"\bNeeds\s+work\b",
        r"\bChanges\s+requested\b",
        r"#### \d+\.",
        r"^\s*\d+\.\s+\*\*",
    ]

    has_findings = False
    for pat in finding_patterns:
        if re.search(pat, latest_body, re.IGNORECASE | re.MULTILINE):
            has_findings = True
            issues.append(f"Latest review comment for SHA {sha[:8]} contains findings (matched pattern '{pat}')")

    if not has_findings:
        print(f"✓ Found clean review comment evaluating HEAD SHA {sha[:8]} (created {latest_item[1]})")

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
        print("\n❌ PR is NOT fully clean:")
        for issue in all_issues:
            print(f"  - {issue}")
        sys.exit(1)

    print(f"\n✅ PR #{pr_num} is FULLY CLEAN on HEAD {sha[:8]}!")
    sys.exit(0)


if __name__ == "__main__":
    main()
