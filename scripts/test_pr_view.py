#!/usr/bin/env python3
"""Tests for scripts/lib/pr_view.py (ai-config#4733).

A fake runner stands in for `gh` and `git`: each case pins one branch of the
GraphQL-then-REST read, including the failures that must not read as an
empty PR.

Run:  python3 scripts/test_pr_view.py
"""
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))

import pr_view  # noqa: E402

BLOCKED = ('gh: 403 {"message":"GitHub GraphQL is not available from Claude Code '
           'sessions; use the REST API"}')
PR = {
    "number": 7, "html_url": "https://github.com/o/r/pull/7", "title": "t",
    "body": "b", "state": "closed", "merged_at": "2026-11-19T00:00:00Z",
    "draft": False, "head": {"sha": "abc123", "ref": "feat/x"},
    "base": {"ref": "main"}, "user": {"login": "me"},
    "updated_at": "2026-11-19T01:00:00Z", "mergeable": None,
    "mergeable_state": "unknown",
}
REVIEW = {"state": "APPROVED", "body": "ok", "submitted_at": "s",
          "author_association": "MEMBER", "user": {"login": "rev"},
          "commit_id": "abc123"}

failures = []


def check(label, got, want):
    if got == want:
        print(f"PASS: {label}")
    else:
        failures.append(label)
        print(f"FAIL: {label}\n  got:  {got!r}\n  want: {want!r}")


def fake(routes, view_rc=1, view_stderr=BLOCKED, view_out=""):
    """A runner: `gh pr view` answers per the view_* args, `gh api` by route."""
    calls = []

    def run(argv, **_kwargs):
        calls.append(list(argv))
        if argv[1:3] == ["pr", "view"]:
            return subprocess.CompletedProcess(argv, view_rc, view_out, view_stderr)
        key = " ".join(argv[1:])
        if key in routes:
            answer = routes[key]
            if isinstance(answer, tuple):
                return subprocess.CompletedProcess(argv, answer[0], "", answer[1])
            text = answer if isinstance(answer, str) else json.dumps(answer)
            return subprocess.CompletedProcess(argv, 0, text, "")
        return subprocess.CompletedProcess(argv, 1, "", f"unrouted: {key}")
    return run, calls


# 1. A working `gh pr view` is returned as is, with no REST call.
run, calls = fake({}, view_rc=0, view_stderr="", view_out='{"state": "OPEN"}')
check("graphql answer passes through", pr_view.gh_pr_view(["state"], target=7, run=run),
      ({"state": "OPEN"}, None))
check("no REST call when graphql works", len(calls), 1)

# 2. Any other gh failure is an error, never a REST read or an empty PR.
run, calls = fake({}, view_stderr="no pull requests found")
data, error = pr_view.gh_pr_view(["state"], target=7, repo="o/r", run=run)
check("non-graphql failure returns no data", data, None)
check("non-graphql failure names gh's reason", "no pull requests found" in (error or ""), True)
check("non-graphql failure makes no REST call", len(calls), 1)

# 3. GraphQL refused: the PR is read over REST, in gh's field shapes.
routes = {
    "api repos/o/r/pulls/7": PR,
    "api repos/o/r/pulls/7/reviews?per_page=100&page=1": [REVIEW],
}
run, _ = fake(routes)
data, error = pr_view.gh_pr_view(
    ["number", "state", "closed", "headRefOid", "headRefName", "baseRefName",
     "mergeable", "mergeStateStatus", "reviews", "reviewDecision"],
    target=7, repo="o/r", run=run)
check("REST fallback reports no error", error, None)
check("merged PR reads MERGED", data and data["state"], "MERGED")
check("merged PR reads closed", data and data["closed"], True)
check("head sha", data and data["headRefOid"], "abc123")
check("head branch", data and data["headRefName"], "feat/x")
check("base branch", data and data["baseRefName"], "main")
check("null mergeable reads UNKNOWN", data and data["mergeable"], "UNKNOWN")
check("mergeable_state upper-cased", data and data["mergeStateStatus"], "UNKNOWN")
check("review mapped to gh shape", data and data["reviews"],
      [{"state": "APPROVED", "body": "ok", "submittedAt": "s",
        "authorAssociation": "MEMBER", "author": {"login": "rev"},
        "commit": {"oid": "abc123"}}])
check("field REST lacks is named, not faked", data and data.get("restOmitted"),
      ["reviewDecision"])
check("field REST lacks is absent", data and "reviewDecision" in data, False)

# 4. A URL target reads its own repo and number.
run, calls = fake({"api repos/x/y/pulls/9": dict(PR, number=9)})
data, error = pr_view.gh_pr_view(["number"], target="https://github.com/x/y/pull/9", run=run)
check("URL target", (data, error), ({"number": 9}, None))

# 5. No target: the current branch's open PR, found from the origin remote.
routes = {
    "api repos/o/r/pulls?head=o:feat/x&state=open&per_page=2": [{"number": 7}],
    "api repos/o/r/pulls/7": PR,
}


def branch_run(argv, **kwargs):
    if argv[:3] == ["git", "remote", "get-url"]:
        return subprocess.CompletedProcess(argv, 0, "http://proxy@127.0.0.1:1/git/o/r\n", "")
    if argv[:2] == ["git", "rev-parse"]:
        return subprocess.CompletedProcess(argv, 0, "feat/x\n", "")
    return base_run(argv, **kwargs)


base_run, _ = fake(routes)
check("current branch via the proxy remote",
      pr_view.gh_pr_view(["number"], run=branch_run), ({"number": 7}, None))

# 6. A failed REST read is an error, not an empty PR.
run, _ = fake({"api repos/o/r/pulls/7": (1, "HTTP 404")})
data, error = pr_view.gh_pr_view(["state"], target=7, repo="o/r", run=run)
check("REST failure returns no data", data, None)
check("REST failure names the cause", "HTTP 404" in (error or ""), True)

# 7. A truncated check-run list is refused.
routes = {
    "api repos/o/r/pulls/7": PR,
    "api repos/o/r/commits/abc123/check-runs?per_page=100":
        {"total_count": 101, "check_runs": [{"name": "a"}]},
}
run, _ = fake(routes)
data, error = pr_view.gh_pr_view(["statusCheckRollup"], target=7, repo="o/r", run=run)
check("truncated check runs refused", (data, "truncated" in (error or "")), (None, True))

# 8. Check runs and commit statuses map onto the GraphQL rollup.
routes["api repos/o/r/commits/abc123/check-runs?per_page=100"] = {
    "total_count": 1,
    "check_runs": [{"name": "build", "status": "completed", "conclusion": "success",
                    "details_url": "u"}]}
routes["api repos/o/r/commits/abc123/status"] = {
    "statuses": [{"context": "ci/x", "state": "pending", "target_url": "t"}]}
run, _ = fake(routes)
data, error = pr_view.gh_pr_view(["statusCheckRollup"], target=7, repo="o/r", run=run)
check("rollup mapped", (data, error), ({"statusCheckRollup": [
    {"__typename": "CheckRun", "name": "build", "status": "COMPLETED",
     "conclusion": "SUCCESS", "detailsUrl": "u"},
    {"__typename": "StatusContext", "context": "ci/x", "state": "PENDING",
     "targetUrl": "t"}]}, None))

# 9. Remote and URL parsing.
check("https remote", pr_view.repo_from_remote_url("https://github.com/o/r.git"), "o/r")
check("ssh remote", pr_view.repo_from_remote_url("git@github.com:o/r.git"), "o/r")
check("proxy remote", pr_view.repo_from_remote_url("http://p@127.0.0.1:9/git/o/r"), "o/r")
check("non-github remote", pr_view.repo_from_remote_url("https://gitlab.com/o/r"), None)
check("PR URL", pr_view.parse_pr_url("https://github.com/o/r/pull/12#x"), ("o/r", "12"))
check("issue URL is not a PR", pr_view.parse_pr_url("https://github.com/o/r/issues/12"), None)
check("graphql marker matches the measured message", pr_view.graphql_blocked(BLOCKED), True)

if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
print("\nAll pr_view tests passed.")
