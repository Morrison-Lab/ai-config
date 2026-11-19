"""`gh pr view --json`, with a REST fallback when GraphQL is refused.

`gh pr view` reads through GraphQL, and a Claude Code cloud session's proxy
answers every GraphQL call with a 403 whose message names
`GRAPHQL_BLOCKED_MARKER` (ai-config#4304). The hooks and scripts that read a
PR with `gh pr view` therefore failed on every run there (ai-config#4733).

`gh_pr_view` runs `gh pr view` first, and only when its stderr carries that
marker reads the same fields over REST (`gh api`), which the proxy allows.
Any other failure is returned as an error, never as an empty PR
(shared/principles/fail-fast.md).

REST has no equivalent of some GraphQL fields, `reviewDecision` among them.
A requested field that REST cannot supply is left out of the result and named
in its `restOmitted` list, so a caller can tell "absent" from "empty".
"""
from __future__ import annotations

import json
import re
import subprocess
from urllib.parse import quote
from typing import Callable, Iterable, Optional, Tuple

GRAPHQL_BLOCKED_MARKER = "GraphQL is not available"

PR_URL_RE = re.compile(r"^https://github\.com/([^/\s]+/[^/\s]+)/pull/(\d+)(?:[/?#].*)?$")
# `git remote get-url` answers: a github.com URL (https or ssh), or the cloud
# proxy's `http://.../git/<owner>/<repo>` form.
REMOTE_RES = (
    re.compile(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$"),
    re.compile(r"/git/([^/\s]+/[^/\s]+?)(?:\.git)?/?$"),
)

# The fields REST supplies, each from the `pulls/{n}` object unless noted.
REST_FIELDS = frozenset({
    "number", "url", "title", "body", "state", "closed", "isDraft",
    "headRefOid", "headRefName", "baseRefName", "author", "updatedAt",
    "mergeable", "mergeStateStatus",
    "reviews",            # pulls/{n}/reviews
    "statusCheckRollup",  # commits/{sha}/check-runs and commits/{sha}/status
})

MERGEABLE = {True: "MERGEABLE", False: "CONFLICTING", None: "UNKNOWN"}

Runner = Callable[..., subprocess.CompletedProcess]


def graphql_blocked(stderr: Optional[str]) -> bool:
    """True when gh's stderr says the session's proxy refuses GraphQL."""
    return GRAPHQL_BLOCKED_MARKER in (stderr or "")


def parse_pr_url(url: str) -> Optional[Tuple[str, str]]:
    """(owner/repo, number) of a github.com PR URL, or None."""
    match = PR_URL_RE.match(str(url or "").strip())
    return (match.group(1), match.group(2)) if match else None


def repo_from_remote_url(url: str) -> Optional[str]:
    """owner/repo named by a git remote URL, or None."""
    url = (url or "").strip()
    for pattern in REMOTE_RES:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _call(run: Runner, argv, cwd, timeout):
    """Run one command, decoding its output as UTF-8.

    The locale codec (cp1252 on Windows) garbles or fails on non-ASCII
    PR bodies, as `check-pr-body-figures.py`'s `run_cmd` explains.
    """
    return run(argv, capture_output=True, text=True, encoding="utf-8",
               errors="replace", timeout=timeout, cwd=cwd)


def _run(run: Runner, argv, cwd, timeout):
    """(stdout, error) for one command; error is None on exit 0."""
    try:
        result = _call(run, argv, cwd, timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{argv[0]} {argv[1]} failed to run: {exc}"
    if result.returncode != 0:
        detail = (result.stderr or "").strip() or f"exit {result.returncode}"
        return None, f"{' '.join(argv[:3])} failed: {detail}"
    return result.stdout or "", None


def _api(path, gh, cwd, timeout, run):
    """(parsed JSON, error) for one `gh api` GET."""
    out, error = _run(run, [gh, "api", path], cwd, timeout)
    if error:
        return None, error
    try:
        return json.loads(out), None
    except ValueError as exc:
        return None, f"gh api {path} answered unparseable JSON: {exc}"


def _resolve_target(target, repo, cwd, gh, timeout, run):
    """(owner/repo, number, error) for what `gh pr view [target]` would read."""
    target = "" if target is None else str(target).strip()
    parsed = parse_pr_url(target)
    if parsed:
        return parsed[0], parsed[1], None
    if not repo:
        out, error = _run(run, ["git", "remote", "get-url", "origin"], cwd, timeout)
        if error:
            return None, None, error
        repo = repo_from_remote_url(out)
        if not repo:
            return None, None, f"cannot read owner/repo from the origin remote {out.strip()!r}"
    if target.isdigit():
        return repo, target, None
    branch = target
    if not branch:
        out, error = _run(run, ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd, timeout)
        if error:
            return None, None, error
        branch = out.strip()
    if not branch or branch == "HEAD":
        return None, None, "no branch is checked out, so no PR can be found for it"
    owner = repo.split("/", 1)[0]
    pulls, error = _api(f"repos/{repo}/pulls?head={owner}:{quote(branch, safe='/')}&state=open&per_page=2",
                        gh, cwd, timeout, run)
    if error:
        return None, None, error
    if not isinstance(pulls, list) or not pulls:
        return None, None, f"no open pull request found for branch {branch!r} in {repo}"
    return repo, str(pulls[0].get("number")), None


def _check_rollup(repo, sha, gh, cwd, timeout, run):
    """GraphQL-shaped statusCheckRollup from the check-runs and status routes."""
    runs, error = _api(f"repos/{repo}/commits/{sha}/check-runs?per_page=100", gh, cwd, timeout, run)
    if error:
        return None, error
    total = runs.get("total_count") if isinstance(runs, dict) else None
    items = runs.get("check_runs") if isinstance(runs, dict) else None
    if not isinstance(items, list):
        return None, "the check-runs route answered something other than a check_runs list"
    if isinstance(total, int) and total > len(items):
        return None, f"the check-runs list is truncated ({len(items)} of {total})"
    status, error = _api(f"repos/{repo}/commits/{sha}/status", gh, cwd, timeout, run)
    if error:
        return None, error
    rollup = [
        {
            "__typename": "CheckRun",
            "name": item.get("name") or "",
            "status": str(item.get("status") or "").upper(),
            "conclusion": str(item.get("conclusion") or "").upper(),
            "detailsUrl": item.get("details_url") or item.get("html_url") or "",
        }
        for item in items
    ]
    rollup += [
        {
            "__typename": "StatusContext",
            "context": item.get("context") or "",
            "state": str(item.get("state") or "").upper(),
            "targetUrl": item.get("target_url") or "",
        }
        for item in (status.get("statuses") or [] if isinstance(status, dict) else [])
    ]
    return rollup, None


def _reviews(repo, number, gh, cwd, timeout, run):
    """GraphQL-shaped reviews from `pulls/{n}/reviews`, all pages."""
    reviews = []
    page = 1
    while True:
        batch, error = _api(f"repos/{repo}/pulls/{number}/reviews?per_page=100&page={page}",
                            gh, cwd, timeout, run)
        if error:
            return None, error
        if not isinstance(batch, list):
            return None, "the reviews route answered something other than a list"
        reviews += [
            {
                "state": r.get("state") or "",
                "body": r.get("body") or "",
                "submittedAt": r.get("submitted_at") or "",
                "authorAssociation": r.get("author_association") or "",
                "author": {"login": (r.get("user") or {}).get("login", "")},
                "commit": {"oid": r.get("commit_id") or ""},
            }
            for r in batch
        ]
        if len(batch) < 100:
            return reviews, None
        page += 1


def rest_pr_view(fields: Iterable[str], target=None, repo=None, cwd=None,
                 gh="gh", timeout=10, run: Optional[Runner] = None):
    """(data, error): the `gh pr view --json fields` payload, read over REST.

    `run` defaults to `subprocess.run` looked up at call time, so a test that
    patches `subprocess.run` reaches these calls too.
    """
    run = run or subprocess.run
    fields = list(fields)
    repo, number, error = _resolve_target(target, repo, cwd, gh, timeout, run)
    if error:
        return None, error
    pr, error = _api(f"repos/{repo}/pulls/{number}", gh, cwd, timeout, run)
    if error:
        return None, error
    state = "MERGED" if pr.get("merged_at") else str(pr.get("state") or "").upper()
    head = pr.get("head") or {}
    simple = {
        "number": pr.get("number"),
        "url": pr.get("html_url") or "",
        "title": pr.get("title") or "",
        "body": pr.get("body") or "",
        "state": state,
        "closed": state != "OPEN",
        "isDraft": bool(pr.get("draft")),
        "headRefOid": head.get("sha") or "",
        "headRefName": head.get("ref") or "",
        "baseRefName": (pr.get("base") or {}).get("ref") or "",
        "author": {"login": (pr.get("user") or {}).get("login", "")},
        "updatedAt": pr.get("updated_at") or "",
        "mergeable": MERGEABLE.get(pr.get("mergeable"), "UNKNOWN"),
        "mergeStateStatus": str(pr.get("mergeable_state") or "unknown").upper(),
    }
    data = {}
    omitted = [field for field in fields if field not in REST_FIELDS]
    for field in fields:
        if field in simple:
            data[field] = simple[field]
        elif field == "reviews":
            data[field], error = _reviews(repo, number, gh, cwd, timeout, run)
        elif field == "statusCheckRollup":
            data[field], error = _check_rollup(repo, simple["headRefOid"], gh, cwd, timeout, run)
        if error:
            return None, error
    if omitted:
        data["restOmitted"] = omitted
    return data, None


def gh_pr_view(fields: Iterable[str], target=None, repo=None, cwd=None,
               gh="gh", timeout=10, run: Optional[Runner] = None):
    """(data, error) for `gh pr view [target] [-R repo] --json fields`.

    Falls back to `rest_pr_view` only when gh reports GraphQL refused.
    """
    run = run or subprocess.run
    fields = list(fields)
    argv = [gh, "pr", "view"]
    if target not in (None, ""):
        argv.append(str(target))
    if repo:
        argv += ["-R", repo]
    argv += ["--json", ",".join(fields)]
    try:
        result = _call(run, argv, cwd, timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"gh pr view failed to run: {exc}"
    if result.returncode == 0:
        if result.stdout is None:
            return None, "gh pr view exited 0 with no output"
        try:
            return json.loads(result.stdout), None
        except ValueError as exc:
            return None, f"gh pr view answered unparseable JSON: {exc}"
    if graphql_blocked(getattr(result, "stderr", "")):
        return rest_pr_view(fields, target, repo, cwd, gh, timeout, run)
    detail = (getattr(result, "stderr", "") or "").strip() or f"exit {result.returncode}"
    return None, f"gh pr view failed: {detail}"
