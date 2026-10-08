#!/usr/bin/env python3
"""Tests for scripts/build-pr-payload.py.

Morrison-Lab/ai-config#2441's --from-json path needs a payload gathered
somehow; this script gathers one from REST alone (see its own module
docstring for why). The mapping logic is refactored into build_payload() so
it can be exercised here on canned REST fixtures, with no network call and
no GITHUB_TOKEN required -- the same shape scripts/test_pull_request.py and
scripts/test_payload_fetcher.py already use for their own mapping/scoring
functions.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parent / "build-pr-payload.py"
spec = importlib.util.spec_from_file_location("build_pr_payload", SCRIPT)
build_pr_payload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_pr_payload)  # noqa: E402

passes = 0
failures = 0


def check(name, cond):
    global passes, failures
    if cond:
        passes += 1
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAIL: {name}")


PR_RAW = {
    "number": 173,
    "head": {"sha": "abc1234def5678901234567890abcdef1234567", "ref": "feat/example"},
    "base": {"ref": "main"},
    "state": "open",
    "merged": False,
    "draft": False,
    "mergeable": True,
    "mergeable_state": "clean",
    "labels": [{"name": "bug"}],
}

COMMITS_RAW = [
    {
        "sha": "abc1234def5678901234567890abcdef1234567",
        "commit": {
            "committer": {"date": "2026-09-01T12:00:00Z"},
            "author": {"name": "Jane Doe"},
        },
        "author": {"login": "jane"},
    }
]

CHECK_RUNS_RAW = [
    {
        "name": "R-CMD-check",
        "status": "completed",
        "conclusion": "success",
        "started_at": "2026-09-01T12:01:00Z",
        "completed_at": "2026-09-01T12:05:00Z",
        "html_url": "https://github.com/example-org/example-repo/runs/1",
    }
]


def test_maps_pr_fields():
    raw_pr = dict(
        PR_RAW,
        requested_reviewers=[{"login": "copilot-pull-request-reviewer"}],
        requested_teams=[{"slug": "review-team"}],
    )
    payload = build_pr_payload.build_payload(
        "example-org/example-repo", raw_pr, [], [], COMMITS_RAW, CHECK_RUNS_RAW
    )
    pr = payload["pr"]
    check("repo carried through", payload["repo"] == "example-org/example-repo")
    check("headRefOid mapped from head.sha", pr["headRefOid"] == PR_RAW["head"]["sha"])
    check("headRefName mapped from head.ref", pr["headRefName"] == "feat/example")
    check("baseRefName mapped from base.ref", pr["baseRefName"] == "main")
    check("state uppercased when open", pr["state"] == "OPEN")
    check("mergeStateStatus uppercased", pr["mergeStateStatus"] == "CLEAN")
    check("labels mapped to name objects", pr["labels"] == [{"name": "bug"}])
    check("check_runs length matches input", len(payload["check_runs"]) == 1)
    check(
        "commit committedDate mapped from commit.committer.date",
        pr["commits"][0]["committedDate"] == "2026-09-01T12:00:00Z",
    )
    check(
        "reviewRequests mapped from requested_reviewers and requested_teams",
        pr["reviewRequests"] == [{"login": "copilot-pull-request-reviewer"}, {"slug": "review-team"}],
    )


def test_state_merged():
    merged_pr = dict(PR_RAW, merged=True, state="closed")
    payload = build_pr_payload.build_payload(
        "example-org/example-repo", merged_pr, [], [], [], []
    )
    check("merged PR reports state MERGED regardless of raw state", payload["pr"]["state"] == "MERGED")


def test_review_decision_changes_requested_wins():
    reviews = [
        {"state": "APPROVED", "user": {"login": "alice"}},
        {"state": "CHANGES_REQUESTED", "user": {"login": "bob"}},
    ]
    payload = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, reviews, [], [], []
    )
    check(
        "CHANGES_REQUESTED wins over a different reviewer's APPROVED",
        payload["pr"]["reviewDecision"] == "CHANGES_REQUESTED",
    )


def test_review_decision_latest_supersedes():
    reviews = [
        {"state": "CHANGES_REQUESTED", "user": {"login": "alice"}},
        {"state": "APPROVED", "user": {"login": "alice"}},
    ]
    payload = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, reviews, [], [], []
    )
    check(
        "the same reviewer's later APPROVED supersedes their earlier CHANGES_REQUESTED",
        payload["pr"]["reviewDecision"] == "APPROVED",
    )


def test_review_decision_no_terminal_reviews_is_empty():
    reviews = [{"state": "COMMENTED", "user": {"login": "alice"}}]
    payload = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, reviews, [], [], []
    )
    check(
        "a COMMENTED-only review set yields an empty reviewDecision",
        payload["pr"]["reviewDecision"] == "",
    )


def test_comments_mapped():
    comments_raw = [
        {
            "body": "looks good",
            "created_at": "2026-09-01T13:00:00Z",
            "author_association": "MEMBER",
            "user": {"login": "carol"},
        }
    ]
    payload = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, [], comments_raw, [], []
    )
    comment = payload["pr"]["comments"][0]
    check("comment body mapped", comment["body"] == "looks good")
    check("comment author login mapped to nested author.login", comment["author"]["login"] == "carol")
    check("comment authorAssociation mapped", comment["authorAssociation"] == "MEMBER")


def test_check_runs_bare_list_accepted_by_payload_fetcher():
    """The output must satisfy scripts/lib/payload_fetcher.py's shape check."""
    sys.path.insert(0, str(Path(__file__).parent / "lib"))
    from payload_fetcher import PayloadFetcher  # noqa: E402

    payload = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, [], [], COMMITS_RAW, CHECK_RUNS_RAW
    )
    fetcher = PayloadFetcher(payload)
    result = json.loads(fetcher(["gh", "pr", "view"]))
    check("payload_fetcher accepts the built pr object", result["headRefOid"] == PR_RAW["head"]["sha"])


def test_main_fails_fast_with_no_token():
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "out.json")
        res = subprocess.run(
            [sys.executable, str(SCRIPT), "example-org/example-repo", "1", out],
            capture_output=True, encoding="utf-8", env=env,
        )
        check("main exits 2 with no token set", res.returncode == 2)
        check("main names the missing token in its message", "GITHUB_TOKEN" in (res.stderr or ""))
        check("no output file is written on the fail-fast path", not Path(out).exists())


def test_rest_get_paginates_enveloped_check_runs():
    """/check-runs answers with an envelope; every page must be gathered.

    ai-config#2909 review round 1 reproduced the truncation: 150 check runs
    over two pages yielded 100 with one HTTP call, silently. A dropped
    still-red run past position 100 would score a PR clean on incomplete
    evidence, the one error the fully-clean instrument exists to prevent.
    """
    import io
    import urllib.request

    calls = []
    runs = [{"name": f"job-{i}", "status": "completed", "conclusion": "success",
             "started_at": None, "completed_at": None, "html_url": ""} for i in range(150)]

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req):
        url = req.full_url
        calls.append(url)
        page = int(url.rsplit("page=", 1)[1])
        if "/check-runs" in url:
            chunk = runs[(page - 1) * 100:page * 100]
            body = {"total_count": len(runs), "check_runs": chunk}
        elif "/reviews" in url:
            body = [{"state": "APPROVED"}] * 100 if page == 1 else [{"state": "APPROVED"}] * 7
        else:
            body = {"number": 1}
        return _Resp(json.dumps(body).encode())

    real = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        got = build_pr_payload.rest_get("/repos/o/r/commits/abc/check-runs", "t", envelope="check_runs")
        check("enveloped check-runs gathers all 150 items", len(got) == 150)
        check("enveloped check-runs requests two pages", len([c for c in calls if "/check-runs" in c]) == 2)
        check("enveloped check-runs stops after the short page", not any("page=3" in c for c in calls))
        reviews = build_pr_payload.rest_get("/repos/o/r/pulls/1/reviews", "t")
        check("bare-array endpoint gathers 107 items across two pages", len(reviews) == 107)
        single = build_pr_payload.rest_get("/repos/o/r/pulls/1", "t")
        check("single-object endpoint returns its dict on the first page", single == {"number": 1})
    finally:
        urllib.request.urlopen = real


def test_run_ids_from_check_runs():
    runs = [
        {"html_url": "https://github.com/o/r/actions/runs/33570074739/job/100061971212"},
        {"html_url": "https://github.com/o/r/actions/runs/33570074739/job/100061971299"},
        {"html_url": "https://github.com/o/r/actions/runs/33572727768/job/1"},
        {"html_url": "https://github.com/o/r/runs/5"},
        {"html_url": "https://github.com/o/r/actions/runs/777"},
        {"html_url": None},
    ]
    check(
        "run ids are extracted once each, in first-seen order, skipping URLs the checker itself would not resolve",
        build_pr_payload.run_ids_from_check_runs(runs) == ["33570074739", "33572727768"],
    )


def test_build_payload_carries_actions_runs():
    runs = {"1": {"path": ".github/workflows/claude-review.yml"}}
    payload = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, [], [], COMMITS_RAW, CHECK_RUNS_RAW, runs
    )
    check("actions_runs is carried through verbatim", payload["actions_runs"] == runs)
    without = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, [], [], COMMITS_RAW, CHECK_RUNS_RAW
    )
    check("actions_runs is absent when not gathered", "actions_runs" not in without)


def test_fetch_actions_runs_maps_paths_and_skips_404():
    """A run past retention 404s; that run is skipped with a warning, not fatal."""
    import io
    import urllib.error
    import urllib.request

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    calls = []

    def fake_urlopen(req):
        url = req.full_url
        calls.append(url)
        if "/actions/runs/404404" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b"{}"))
        run_id = url.split("/actions/runs/")[1].split("?")[0]
        return _Resp(json.dumps({"id": int(run_id), "path": f".github/workflows/{run_id}.yml"}).encode())

    real = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    err = io.StringIO()
    real_err = sys.stderr
    sys.stderr = err
    try:
        got = build_pr_payload.fetch_actions_runs("o/r", ["1", "404404", "2"], "t")
    finally:
        urllib.request.urlopen = real
        sys.stderr = real_err
    check(
        "each reachable run maps to its workflow path",
        got == {"1": {"path": ".github/workflows/1.yml"}, "2": {"path": ".github/workflows/2.yml"}},
    )
    check("a 404 run is skipped and named on stderr", "404404" in err.getvalue() and "404404" not in got)
    check("each run id is fetched exactly once", len(calls) == 3)


def test_cancelled_run_superseded_end_to_end():
    """The #1697 case, scored through the real checker on a built payload.

    Fails on the pre-fix builder (no actions_runs, so the checker cannot see
    that both runs belong to one workflow) and passes with it.
    """
    lib = Path(__file__).parent / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    checker_spec = importlib.util.spec_from_file_location(
        "check_pr_fully_clean", Path(__file__).parent / "check-pr-fully-clean.py"
    )
    checker = importlib.util.module_from_spec(checker_spec)
    checker_spec.loader.exec_module(checker)
    from payload_fetcher import PayloadFetcher

    cancelled_then_green = [
        {"name": "review / claude-review", "status": "completed", "conclusion": "cancelled",
         "started_at": "2026-09-01T23:14:00Z", "completed_at": "2026-09-01T23:16:00Z",
         "html_url": "https://github.com/o/r/actions/runs/1/job/1"},
        {"name": "review / claude-review", "status": "completed", "conclusion": "success",
         "started_at": "2026-09-01T23:50:00Z", "completed_at": "2026-09-01T23:51:00Z",
         "html_url": "https://github.com/o/r/actions/runs/2/job/2"},
    ]
    same_workflow = {"1": {"path": ".github/workflows/claude-review.yml"},
                     "2": {"path": ".github/workflows/claude-review.yml"}}
    other_workflow = {"1": {"path": ".github/workflows/a.yml"},
                      "2": {"path": ".github/workflows/b.yml"}}

    def score(actions_runs):
        payload = build_pr_payload.build_payload(
            "o/r", PR_RAW, [], [], COMMITS_RAW, cancelled_then_green, actions_runs
        )
        checker._FETCHER = PayloadFetcher(payload)
        try:
            pr = checker.get_pr_info(str(PR_RAW["number"]), "o/r")
            return checker.check_ci_runs(pr)
        finally:
            checker._FETCHER = None

    ok_same, issues_same = score(same_workflow)
    check("cancelled run superseded when the payload attributes both runs to one workflow",
          ok_same and issues_same == [])
    ok_none, issues_none = score(None)
    check("without actions_runs the cancelled run still blocks (the pre-fix behaviour, safe direction)",
          not ok_none and any("cancelled" in i for i in issues_none))
    ok_other, issues_other = score(other_workflow)
    check("cancelled run is not superseded by a same-name success from another workflow",
          not ok_other and any("cancelled" in i for i in issues_other))


def test_review_threads_handling():
    # 1. review_threads is absent when review_threads_raw is None
    payload_none = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, [], [], [], []
    )
    check("review_threads is absent when not gathered", "review_threads" not in payload_none)

    # 2. review_threads carried through when provided
    sample_threads = [{"id": "t1", "isResolved": True, "isOutdated": False, "path": "x.py", "line": 1}]
    payload_threads = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, [], [], [], [], review_threads_raw=sample_threads
    )
    check("review_threads carried through when provided", payload_threads.get("review_threads") == sample_threads)

    # 3. fetch_review_threads returns nodes on successful GraphQL
    graphql_data = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": sample_threads,
                    }
                }
            }
        }
    }
    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return json.dumps(graphql_data).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        with patch("json.load", return_value=graphql_data):
            threads = build_pr_payload.fetch_review_threads("example-org/example-repo", 123, "tok")
            check("fetch_review_threads extracts nodes", threads == sample_threads)

    # 4. fetch_review_threads returns None on error
    with patch("urllib.request.urlopen", side_effect=Exception("network down")):
        threads = build_pr_payload.fetch_review_threads("example-org/example-repo", 123, "tok")
        check("fetch_review_threads returns None on error", threads is None)

    # 5-10. the CCR review_threads fallback (ai-config#4220)
    class CcrResp:
        def __init__(self, data, link=""):
            self._body = json.dumps(data).encode("utf-8")
            self.headers = {"Link": link} if link else {}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, *args):
            body, self._body = self._body, b""
            return body

    def via_ccr(resp=None, error=None):
        kwargs = {"side_effect": error} if error else {"return_value": resp}
        with patch.object(build_pr_payload, "_fetch_review_threads_graphql", return_value=None):
            with patch("urllib.request.urlopen", **kwargs) as opened:
                threads = build_pr_payload.fetch_review_threads("example-org/example-repo", 123, "tok")
        return threads, opened

    ccr_data = [
        {"resolved": False, "outdated": True, "path": "NEWS.md", "line": None, "comment_ids": [41, 42]},
        {"resolved": True, "outdated": False, "path": "R/x.R", "line": 7, "comment_ids": [43]},
    ]
    threads, opened = via_ccr(CcrResp(ccr_data))
    called = opened.call_args[0][0].full_url
    check("CCR fallback hits the ccr/review_threads route",
          "/repos/example-org/example-repo/pulls/123/ccr/review_threads?" in called)
    check("CCR fallback maps threads onto the payload fields", threads == [
        {"id": "41,42", "isResolved": False, "isOutdated": True, "path": "NEWS.md", "line": None},
        {"id": "43", "isResolved": True, "isOutdated": False, "path": "R/x.R", "line": 7},
    ])

    threads, _ = via_ccr(CcrResp([]))
    check("empty CCR answer is zero threads, not None", threads == [])

    threads, _ = via_ccr(error=Exception("proxy refused"))
    check("CCR route failure yields None", threads is None)

    threads, _ = via_ccr(CcrResp({"message": "not available"}))
    check("non-list CCR answer yields None", threads is None)

    threads, _ = via_ccr(CcrResp(["NEWS.md"]))
    check("list of non-objects from CCR yields None", threads is None)

    full = [{"resolved": True, "outdated": False, "path": "a", "line": 1, "comment_ids": [i]} for i in range(100)]
    threads, _ = via_ccr(CcrResp(full))
    check("a full page of CCR threads is refused as possibly truncated", threads is None)

    threads, _ = via_ccr(CcrResp(ccr_data, link='<https://x?page=2>; rel="next"'))
    check("a CCR answer with a next link is refused", threads is None)

    # 11. GraphQL success never consults the CCR route
    with patch.object(build_pr_payload, "_fetch_review_threads_graphql", return_value=sample_threads):
        with patch.object(build_pr_payload, "_fetch_review_threads_ccr") as ccr:
            threads = build_pr_payload.fetch_review_threads("example-org/example-repo", 123, "tok")
    check("GraphQL success skips the CCR route", threads == sample_threads and not ccr.called)



def test_review_comments_handling():
    # 1. review_comments is absent when not gathered
    payload = build_pr_payload.build_payload(
        "example-org/example-repo", PR_RAW, [], [], COMMITS_RAW, CHECK_RUNS_RAW
    )
    check("review_comments is absent when not gathered", "review_comments" not in payload)
    check("pr.reviewComments is absent when not gathered", "reviewComments" not in payload["pr"])

    # 2. review_comments mapped and carried through when provided
    sample_comments = [
        {
            "user": {"login": "Copilot"},
            "commit_id": "c1",
            "original_commit_id": "c0",
            "body": "inline feedback",
        }
    ]
    payload = build_pr_payload.build_payload(
        "example-org/example-repo",
        PR_RAW,
        [],
        [],
        COMMITS_RAW,
        CHECK_RUNS_RAW,
        review_comments_raw=sample_comments,
    )
    expected_mapped = [
        {"author": {"login": "Copilot"}, "commit_id": "c1", "original_commit_id": "c0"}
    ]
    check("review_comments carried through when provided", payload.get("review_comments") == expected_mapped)
    check("pr.reviewComments carried through when provided", payload["pr"].get("reviewComments") == expected_mapped)


def test_fetch_payload_integration():
    compare_calls = []
    compare_fail = []

    def fake_rest_get(endpoint, token, envelope=None):
        if "/compare/" in endpoint:
            compare_calls.append(endpoint)
            if compare_fail:
                raise RuntimeError("HTTP 502")
            return {"ahead_by": 2, "commits": [{"sha": "x"}],
                    "files": [{"filename": ".github/workflows/v.yml", "patch": "+x"}]}
        if "/pulls/123/comments" in endpoint:
            return [{"user": {"login": "Copilot"}, "commit_id": "c1", "original_commit_id": "c0"}]
        if "/pulls/123/reviews" in endpoint:
            return []
        if "/issues/123/comments" in endpoint:
            return []
        if "/pulls/123/commits" in endpoint:
            return COMMITS_RAW
        if "/check-runs" in endpoint:
            return CHECK_RUNS_RAW
        if "/pulls/123" in endpoint:
            return PR_RAW
        return []

    with patch.object(build_pr_payload, "rest_get", side_effect=fake_rest_get):
        with patch.object(build_pr_payload, "fetch_actions_runs", return_value={}):
            with patch.object(build_pr_payload, "fetch_review_threads", return_value=[]):
                payload = build_pr_payload.fetch_payload("example-org/example-repo", 123, "token")
                check("fetch_payload runs without UnboundLocalError/NameError", isinstance(payload, dict))
                check("fetch_payload includes review_threads", "review_threads" in payload)
                check("fetch_payload includes review_comments", "review_comments" in payload)
                check("fetch_payload carries a compact base_compare (ai-config#2982)",
                      payload.get("base_compare") == {
                          "ahead_by": 2,
                          "files": [{"filename": ".github/workflows/v.yml"}]})
                head, base = PR_RAW["head"]["sha"], PR_RAW["base"]["ref"]
                check("fetch_payload compares head...base, in that order",
                      compare_calls and compare_calls[-1].endswith(f"/compare/{head}...{base}"))
                compare_fail.append(True)
                payload = build_pr_payload.fetch_payload("example-org/example-repo", 123, "token")
                check("a failed comparison is recorded, not omitted",
                      "error" in (payload.get("base_compare") or {}))
    check("compact_compare marks a non-object comparison as an error",
          "error" in build_pr_payload.compact_compare([]))
    check("compact_compare marks a non-list files as an error",
          "error" in build_pr_payload.compact_compare({"ahead_by": 1, "files": "x"}))


def main():
    test_run_ids_from_check_runs()
    test_build_payload_carries_actions_runs()
    test_fetch_actions_runs_maps_paths_and_skips_404()
    test_cancelled_run_superseded_end_to_end()
    test_maps_pr_fields()
    test_state_merged()
    test_review_decision_changes_requested_wins()
    test_review_decision_latest_supersedes()
    test_review_decision_no_terminal_reviews_is_empty()
    test_comments_mapped()
    test_check_runs_bare_list_accepted_by_payload_fetcher()
    test_rest_get_paginates_enveloped_check_runs()
    test_main_fails_fast_with_no_token()
    test_review_threads_handling()
    test_review_comments_handling()
    test_fetch_payload_integration()
    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
