#!/usr/bin/env python3
"""Build a --from-json payload for check-pr-fully-clean.py from REST alone.

Morrison-Lab/ai-config#2908.

Morrison-Lab/ai-config#2441 already split check-pr-fully-clean.py so a
remote/web session (no `gh` CLI) can feed it a pre-gathered payload instead
of shelling out. shared/workflow/fully-clean.md's documented way to gather
that payload is the MCP tools (pull_request_read, actions_get) -- but a
remote session's GraphQL endpoint can be pinned to a fixed operation set
(measured 2026-09-01: https://api.github.com/graphql returned a 403 naming
exactly that restriction), which is the surface `gh pr view --json` itself
depends on for several fields. The plain REST API is a separate surface and,
in the same session, was reachable: `GET /repos/{owner}/{repo}/pulls/{n}`
returned 200. So this script assembles the payload from REST endpoints only,
as a script an agent can run directly instead of hand-transcribing MCP tool
output into JSON (slow, and exactly the class of by-hand work
shared/principles/deterministic-tools.md asks to replace with an instrument).

Usage:
    python3 scripts/build-pr-payload.py OWNER/REPO PR_NUMBER OUT_FILE
    python3 scripts/check-pr-fully-clean.py PR_NUMBER -R OWNER/REPO --from-json OUT_FILE

Auth: reads GITHUB_TOKEN, falling back to GH_TOKEN. Fails fast with a clear
message when neither is set -- see shared/principles/fail-fast.md.

Field mapping mirrors shared/workflow/fully-clean.md's payload table: REST's
`head.sha` becomes `headRefOid`, an author becomes
`{"author": {"login": ...}}`, and reviewDecision is derived the way GitHub
computes it -- CHANGES_REQUESTED if any reviewer's latest review requests
changes, else APPROVED if any latest review approves, else "".

The payload also carries `actions_runs`, keyed by the Actions run id of every
check run, each with the run's workflow `path`. The checker's #2277 rule --
a `cancelled` check run is superseded by a later `success` under the same job
name in the SAME workflow file -- resolves that path through
`gh api repos/{repo}/actions/runs/{id}`, which the --from-json fetcher
answers from this key and otherwise answers with `{}`. Without it every
cancel-in-progress leftover scored a head NOT clean in remote sessions
(Morrison-Lab/ai-config#1697, measured on #2926 and #2917, 2026-09-01). A run
the API no longer has (404, past retention) is skipped with a warning on
stderr rather than aborting the build, since the omission only pushes the
verdict toward not-clean, the safe direction.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

USER_AGENT = "ai-config-build-pr-payload"


class PayloadBuildError(Exception):
    """A precondition the builder needs was not met (auth, HTTP, shape)."""


def _token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise PayloadBuildError(
            "Neither GITHUB_TOKEN nor GH_TOKEN is set. This script needs one "
            "to authenticate REST reads against api.github.com."
        )
    return token


def rest_get(path: str, token: str, envelope: Optional[str] = None) -> Any:
    """GET a REST resource, paginating a list response to completion.

    A bare-array endpoint (reviews, comments, commits) paginates until a page
    comes back short. An enveloped endpoint (check-runs answers with
    ``{"total_count": N, "<envelope>": [...]}``) paginates the same way over
    the list under *envelope*, because returning the first envelope as-is
    silently drops every item past the first page -- a truncated
    ``check_runs[]`` is indistinguishable from a complete one, which is the
    one error the fully-clean instrument exists to prevent (ai-config#2909
    review round 1). A single-object endpoint (the PR itself) returns its
    dict on the first page.
    """
    items: List[Any] = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        url = f"https://api.github.com{path}{sep}per_page=100&page={page}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise PayloadBuildError(f"GET {path} failed: {exc.code} {body}") from exc
        if isinstance(data, dict):
            if envelope is None:
                return data
            chunk = data.get(envelope, [])
            items.extend(chunk)
            total = data.get("total_count")
            if len(chunk) < 100 or (isinstance(total, int) and len(items) >= total):
                return items
        else:
            items.extend(data)
            if len(data) < 100:
                return items
        page += 1


def derive_review_decision(reviews: List[Dict[str, Any]]) -> str:
    """Latest non-COMMENTED review per reviewer, then GitHub's own precedence.

    A reviewer's SUBSEQUENT review supersedes an earlier one -- only the last
    APPROVED/CHANGES_REQUESTED/DISMISSED state per login counts. Then
    CHANGES_REQUESTED wins over APPROVED if both are present across
    reviewers, matching gh pr view --json reviewDecision's own semantics.
    """
    latest: Dict[str, str] = {}
    for r in reviews:
        state = r.get("state") or ""
        if state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            login = (r.get("author") or {}).get("login", "")
            latest[login] = state
    states = set(latest.values())
    if "CHANGES_REQUESTED" in states:
        return "CHANGES_REQUESTED"
    if "APPROVED" in states:
        return "APPROVED"
    return ""


# Same shape check-pr-fully-clean.py's _workflow_path_from_check_run applies, so
# every id gathered here is one the checker's own lookup will ask for.
_RUN_ID_RE = re.compile(r"/actions/runs/(\d+)/")


def run_ids_from_check_runs(check_runs_raw: List[Dict[str, Any]]) -> List[str]:
    """Distinct Actions run ids named by the check runs' `html_url`s, in first-seen order."""
    seen: List[str] = []
    for c in check_runs_raw:
        m = _RUN_ID_RE.search(str(c.get("html_url") or ""))
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def fetch_actions_runs(owner_repo: str, run_ids: List[str], token: str) -> Dict[str, Dict[str, Any]]:
    """GET each Actions run once; map run id -> {"path": workflow file path}.

    A 404 (a run past its retention window) is reported on stderr and skipped:
    the checker treats a missing entry as "path unknown", which can only
    withhold a supersession, never grant one. Any other HTTP failure still
    raises, per fail-fast.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for run_id in run_ids:
        try:
            raw = rest_get(f"/repos/{owner_repo}/actions/runs/{run_id}", token)
        except PayloadBuildError as exc:
            if " failed: 404 " in str(exc):
                print(f"warning: actions run {run_id} not found (404); "
                      "its check runs will not be attributed to a workflow", file=sys.stderr)
                continue
            raise
        out[run_id] = {"path": raw.get("path") or ""}
    return out


def build_payload(
    owner_repo: str,
    pr_raw: Dict[str, Any],
    reviews_raw: List[Dict[str, Any]],
    comments_raw: List[Dict[str, Any]],
    commits_raw: List[Dict[str, Any]],
    check_runs_raw: List[Dict[str, Any]],
    actions_runs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Map REST JSON to the shape scripts/lib/payload_fetcher.py expects.

    Pure and network-free, so it is unit-testable on canned REST fixtures
    without a live token or an HTTP call -- see test_build_pr_payload.py.
    """
    reviews = [
        {
            "state": r.get("state") or "",
            "body": r.get("body") or "",
            "submittedAt": r.get("submitted_at") or "",
            "authorAssociation": r.get("author_association") or "",
            "author": {"login": (r.get("user") or {}).get("login", "")},
            "commit": {"oid": r.get("commit_id") or ""},
        }
        for r in reviews_raw
    ]
    comments = [
        {
            "body": c.get("body") or "",
            "createdAt": c.get("created_at") or "",
            "authorAssociation": c.get("author_association") or "",
            "author": {"login": (c.get("user") or {}).get("login", "")},
        }
        for c in comments_raw
    ]
    commits = [
        {
            "oid": c.get("sha") or "",
            "committedDate": (c.get("commit") or {}).get("committer", {}).get("date", ""),
            "authors": [
                {
                    "login": (c.get("author") or {}).get("login", ""),
                    "name": (c.get("commit") or {}).get("author", {}).get("name", ""),
                }
            ],
        }
        for c in commits_raw
    ]

    pr = {
        "number": pr_raw["number"],
        "headRefOid": pr_raw["head"]["sha"],
        "headRefName": pr_raw["head"]["ref"],
        "baseRefName": pr_raw["base"]["ref"],
        "state": "MERGED" if pr_raw.get("merged") else str(pr_raw["state"]).upper(),
        "isDraft": pr_raw.get("draft", False),
        "mergeable": pr_raw.get("mergeable"),
        "mergeStateStatus": str(pr_raw.get("mergeable_state") or "").upper(),
        "reviewDecision": derive_review_decision(reviews),
        "labels": [{"name": lbl["name"]} for lbl in pr_raw.get("labels") or []],
        "commits": commits,
        "reviews": reviews,
        "comments": comments,
    }
    check_runs = [
        {
            "name": c.get("name") or "",
            "status": c.get("status") or "",
            "conclusion": c.get("conclusion"),
            "started_at": c.get("started_at") or "",
            "completed_at": c.get("completed_at") or "",
            "html_url": c.get("html_url") or "",
        }
        for c in check_runs_raw
    ]
    payload = {"repo": owner_repo, "pr": pr, "check_runs": check_runs}
    if actions_runs is not None:
        payload["actions_runs"] = actions_runs
    return payload


def fetch_payload(owner_repo: str, pr_number: int, token: str) -> Dict[str, Any]:
    base = f"/repos/{owner_repo}"
    pr_raw = rest_get(f"{base}/pulls/{pr_number}", token)
    reviews_raw = rest_get(f"{base}/pulls/{pr_number}/reviews", token)
    comments_raw = rest_get(f"{base}/issues/{pr_number}/comments", token)
    commits_raw = rest_get(f"{base}/pulls/{pr_number}/commits", token)
    check_runs_raw = rest_get(
        f"{base}/commits/{pr_raw['head']['sha']}/check-runs", token, envelope="check_runs"
    )
    actions_runs = fetch_actions_runs(owner_repo, run_ids_from_check_runs(check_runs_raw), token)
    return build_payload(
        owner_repo, pr_raw, reviews_raw, comments_raw, commits_raw, check_runs_raw, actions_runs
    )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build-pr-payload.py",
        description=(
            "Build a check-pr-fully-clean.py --from-json payload straight from "
            "the GitHub REST API, for a remote/web session where the "
            "GraphQL surface `gh pr view --json` depends on is pinned to a "
            "fixed operation set but plain REST is reachable."
        ),
        epilog=(
            "Pairs with check-pr-fully-clean.py like this:\n"
            "  python3 scripts/build-pr-payload.py OWNER/REPO N out.json\n"
            "  python3 scripts/check-pr-fully-clean.py N -R OWNER/REPO --from-json out.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("owner_repo", metavar="OWNER/REPO", help="Repository to query")
    parser.add_argument("pr_number", type=int, metavar="PR_NUMBER", help="Pull request number")
    parser.add_argument("out_file", metavar="OUT_FILE", help="Path to write the JSON payload to")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    try:
        token = _token()
        payload = fetch_payload(args.owner_repo, args.pr_number, token)
    except PayloadBuildError as exc:
        print(f"build-pr-payload.py: {exc}", file=sys.stderr)
        return 2

    with open(args.out_file, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)

    pr = payload["pr"]
    print(
        f"{args.out_file}: head {pr['headRefOid'][:7]} {pr['state']} "
        f"{pr['mergeStateStatus']} decision={pr['reviewDecision'] or '-'} "
        f"reviews={len(pr['reviews'])} comments={len(pr['comments'])} "
        f"commits={len(pr['commits'])} checks={len(payload['check_runs'])} "
        f"actions_runs={len(payload.get('actions_runs') or {})}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
