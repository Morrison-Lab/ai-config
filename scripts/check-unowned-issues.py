#!/usr/bin/env python3
"""List open P1/P2 issues that nothing owns (ai-config#5056).

An issue is owned when a linked open PR references it or a comment claims it.
The check cannot see coordinator threads; the caller checks those for each
reported issue.  It is a plain report plus an exit code, not a warning: exit 1
when a P1 issue or an `owed-followup` issue has been unowned for more than
`--grace-minutes` (default 60), so it can gate a routine or CI step.

Data comes from `gh api`; tests inject it through `find_unowned(issues, ...)`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

REPOS = ["lds", "mds", "pds", "sds", "mcs", "psw", "ai-config", "gha", "macros"]
ORG = "Morrison-Lab"
CLAIM = re.compile(r"\b(claim(ed|ing)?|working on|taking this|owner:)\b", re.I)
PRIORITY = {"P1": 1, "P2": 2}


def priority(labels: list[str]) -> int | None:
    for name in labels:
        if name in PRIORITY:
            return PRIORITY[name]
    return None


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def find_unowned(issues: list[dict], now: datetime, grace_minutes: int = 60) -> list[dict]:
    """Return unowned P1/P2/owed issues, each with `overdue`, oldest-P1 first.

    Each input issue: repo, number, title, labels (names), created_at,
    open_pr_refs (count of linked open PRs), comments (list of body strings).
    """
    out = []
    for issue in issues:
        labels = issue["labels"]
        rank = priority(labels)
        owed = "owed-followup" in labels
        if rank is None and not owed:
            continue
        if issue["open_pr_refs"] > 0:
            continue
        if any(CLAIM.search(body) for body in issue["comments"]):
            continue
        age = (now - parse_time(issue["created_at"])).total_seconds() / 60
        overdue = (rank == 1 or owed) and age > grace_minutes
        out.append({**issue, "rank": rank or 3, "age_minutes": age, "overdue": overdue})
    return sorted(out, key=lambda i: (i["rank"], -i["age_minutes"]))


def gh(path: str) -> list | dict:
    done = subprocess.run(["gh", "api", "-X", "GET", path, "--paginate"],
                          capture_output=True, text=True, check=True)
    text = done.stdout.replace("][", ",")
    return json.loads(text)


def load(repos: list[str]) -> list[dict]:
    issues = []
    for repo in repos:
        rows = gh(f"repos/{ORG}/{repo}/issues?state=open&per_page=100")
        for row in rows:
            if "pull_request" in row:
                continue
            label_names = [label["name"] for label in row["labels"]]
            if priority(label_names) is None and "owed-followup" not in label_names:
                continue
            comments = gh(f"repos/{ORG}/{repo}/issues/{row['number']}/comments?per_page=100")
            events = gh(f"repos/{ORG}/{repo}/issues/{row['number']}/timeline?per_page=100")
            refs = sum(
                1 for e in events
                if e.get("event") == "cross-referenced"
                and e["source"]["issue"].get("pull_request")
                and e["source"]["issue"]["state"] == "open"
            )
            issues.append({"repo": repo, "number": row["number"], "title": row["title"],
                           "labels": label_names, "created_at": row["created_at"],
                           "open_pr_refs": refs, "comments": [c["body"] for c in comments]})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--grace-minutes", type=int, default=60)
    parser.add_argument("--repo", action="append", help="limit to these repos")
    args = parser.parse_args()
    found = find_unowned(load(args.repo or REPOS), datetime.now(timezone.utc), args.grace_minutes)
    for item in found:
        flag = "OVERDUE" if item["overdue"] else "unowned"
        print(f"{flag} P{item['rank']} {ORG}/{item['repo']}#{item['number']} "
              f"({int(item['age_minutes'])} min) {item['title']}")
    if not found:
        print("No unowned P1/P2/owed issues.")
    return 1 if any(i["overdue"] for i in found) else 0


if __name__ == "__main__":
    sys.exit(main())
