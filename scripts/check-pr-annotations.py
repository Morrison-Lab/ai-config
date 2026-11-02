#!/usr/bin/env python3
"""List every CI annotation on a PR's head, and fail on unacknowledged ones.

Agents must read warnings and notices that do not fail CI (Ezra, 2026-11-02).
A green check run can still carry annotations, so `check-pr-fully-clean.py`
cannot see them.  This script reads them over REST and exits 1 when the head
has any annotation at level warning or failure that no PR comment
acknowledges.

Acknowledge a head by posting a comment that contains the line
`Annotations reviewed: <first 8 characters of the head SHA>`,
after fixing each annotation or saying why it is a false positive.
A push changes the head, so the acknowledgement lapses with it.

Usage: check-pr-annotations.py OWNER/REPO PR_NUMBER
"""

from __future__ import annotations

import json
import subprocess
import sys


def gh_api(path: str) -> object:
    out = subprocess.run(
        ["gh", "api", path], check=True, capture_output=True, text=True
    ).stdout
    return json.loads(out)


def head_sha(repo: str, pr: str) -> str:
    return gh_api(f"repos/{repo}/pulls/{pr}")["head"]["sha"]


def annotations(repo: str, sha: str) -> list[dict]:
    runs = gh_api(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")
    found = []
    for run in runs["check_runs"]:
        if run["output"]["annotations_count"] == 0:
            continue
        for ann in gh_api(f"repos/{repo}/check-runs/{run['id']}/annotations?per_page=100"):
            found.append({**ann, "run": run["name"]})
    return found


def acknowledged(repo: str, pr: str, sha: str) -> bool:
    comments = gh_api(f"repos/{repo}/issues/{pr}/comments?per_page=100")
    marker = f"Annotations reviewed: {sha[:8]}"
    return any(marker in c["body"] for c in comments)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    repo, pr = sys.argv[1], sys.argv[2]
    sha = head_sha(repo, pr)
    found = annotations(repo, sha)
    print(f"{repo}#{pr} head {sha[:8]}: {len(found)} annotation(s)")
    for ann in found:
        print(
            f"  [{ann['annotation_level']}] {ann['run']}: {ann['path']}:"
            f"{ann['start_line']} {ann['message']}"
        )
    blocking = [a for a in found if a["annotation_level"] != "notice"]
    if blocking and not acknowledged(repo, pr, sha):
        print(
            f"\nNOT CLEAN: {len(blocking)} warning/failure annotation(s) are "
            f"unacknowledged. Fix each or say why it is a false positive, then "
            f"comment 'Annotations reviewed: {sha[:8]}'."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
