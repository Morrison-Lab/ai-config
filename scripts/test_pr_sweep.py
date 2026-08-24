#!/usr/bin/env python3
"""Regression tests for pr-sweep.py.

Every fixture below encodes a real misread from 2026-07-30/31 rather than an
invented edge case, so a failure here names the mistake it prevents.

The classification functions are pure over the GraphQL payload shape, so
these run offline with no `gh` call.
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "pr_sweep", Path(__file__).parent / "pr-sweep.py"
)
pr_sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr_sweep)

passes = 0
failures = 0

NOW = datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc)


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def stamp(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_run(name, conclusion, status="COMPLETED"):
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "conclusion": conclusion,
    }


def make_pr(
    number=1,
    updated_minutes_ago=60,
    files=3,
    threads=(),
    reviews=(),
    checks=(),
    head_minutes_ago=90,
    draft=False,
):
    """Build a PR node matching the GraphQL payload shape."""
    if isinstance(files, int):
        file_nodes = [{"path": f"file{i + 1}.txt"} for i in range(files)]
        file_count = files
    else:
        file_nodes = [{"path": f} for f in files]
        file_count = len(files)

    return {
        "number": number,
        "title": f"PR {number}",
        "url": f"https://example.invalid/{number}",
        "isDraft": draft,
        "updatedAt": stamp(updated_minutes_ago),
        "author": {"login": "someone"},
        "files": {
            "totalCount": file_count,
            "nodes": file_nodes,
        },
        "reviewThreads": {
            "totalCount": len(threads),
            "nodes": [{"isResolved": r} for r in threads],
        },
        "reviews": {"nodes": list(reviews)},
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "oid": "deadbeef",
                        "committedDate": stamp(head_minutes_ago),
                        "statusCheckRollup": {"contexts": {"nodes": list(checks)}},
                    }
                }
            ]
        },
    }


def review(login, state, body="", inline=0, minutes_ago=30):
    return {
        "author": {"login": login},
        "state": state,
        "body": body,
        "submittedAt": stamp(minutes_ago),
        "comments": {"totalCount": inline},
    }


REAL_REVIEW = review("claude", "COMMENTED", body="", inline=1, minutes_ago=10)
COPILOT_REFUSAL = review(
    "copilot-pull-request-reviewer",
    "COMMENTED",
    body=(
        "Copilot was unable to review this pull request because the user who "
        "requested the review has reached their quota limit."
    ),
    inline=0,
    minutes_ago=10,
)

# --- 1. A CANCELLED check run is not a failure --------------------------
# `gh pr checks` renders a cancelled job as `fail`. On workflows with
# `concurrency: cancel-in-progress` that is routine: `Claude Code Review`
# was cancelled four times on ai-config#951 inside one hour on 2026-07-31.
# Counting those as failures would make the tool cry wolf and be ignored.
check(
    "CANCELLED check run is not reported as failing",
    pr_sweep.failing_checks(
        make_pr(checks=[check_run("review / claude-review", "CANCELLED")])
    )
    == [],
)
check(
    "SKIPPED check run is not reported as failing",
    pr_sweep.failing_checks(make_pr(checks=[check_run("claude / claude", "SKIPPED")]))
    == [],
)
check(
    "FAILURE check run IS reported as failing",
    pr_sweep.failing_checks(make_pr(checks=[check_run("validate", "FAILURE")]))
    == ["validate"],
)
check(
    "TIMED_OUT counts as failing",
    pr_sweep.failing_checks(make_pr(checks=[check_run("slow", "TIMED_OUT")]))
    == ["slow"],
)
check(
    "a cancelled run alongside a real failure does not mask or duplicate it",
    pr_sweep.failing_checks(
        make_pr(
            checks=[
                check_run("validate", "CANCELLED"),
                check_run("validate", "FAILURE"),
                check_run("lint", "SUCCESS"),
            ]
        )
    )
    == ["validate"],
)
check(
    "a legacy StatusContext failure is caught too",
    pr_sweep.failing_checks(
        make_pr(checks=[{"__typename": "StatusContext", "context": "ci/legacy",
                         "state": "FAILURE"}])
    )
    == ["ci/legacy"],
)

# --- 2. A quota refusal is not review activity ---------------------------
# Copilot refusals arrive as COMMENTED reviews with zero inline comments.
# Letting one register as review activity would mark an unreviewed head as
# reviewed -- the failure mode that hides an unowned PR.
check(
    "a Copilot quota refusal is detected as a refusal",
    pr_sweep.is_refusal(COPILOT_REFUSAL),
)
check(
    "a refusal is excluded from genuine reviews",
    pr_sweep.genuine_reviews(make_pr(reviews=[COPILOT_REFUSAL])) == [],
)
check(
    "a PR whose only review is a refusal still counts as head-unreviewed",
    pr_sweep.head_is_unreviewed(
        make_pr(reviews=[COPILOT_REFUSAL], head_minutes_ago=90)
    ),
)
# The zero-inline-comment half is load-bearing: a reviewer that genuinely
# read the diff and merely MENTIONED a rate limit still leaves inline
# comments, and must keep counting.
check(
    "a real review that merely mentions a rate limit is NOT a refusal",
    not pr_sweep.is_refusal(
        review("claude", "COMMENTED", body="Note: we hit a rate limit earlier.",
               inline=2)
    ),
)

# --- 3. An empty review body is not an empty review ----------------------
# A formal review's body is frequently empty, with the finding in a per-line
# inline comment reachable only via the pulls/<N>/comments endpoint. A
# body-only scan misses those; live ai-config PRs #951 and #953 both carry
# exactly this shape.
check(
    "an empty-bodied review carrying an inline comment counts as genuine",
    pr_sweep.genuine_reviews(make_pr(reviews=[REAL_REVIEW])) == [REAL_REVIEW],
)
check(
    "a genuine review at the head clears head-unreviewed",
    not pr_sweep.head_is_unreviewed(
        make_pr(reviews=[REAL_REVIEW], head_minutes_ago=90)
    ),
)
check(
    "a review that PREDATES the head commit leaves the head unreviewed",
    pr_sweep.head_is_unreviewed(
        make_pr(
            reviews=[review("claude", "COMMENTED", inline=1, minutes_ago=120)],
            head_minutes_ago=90,
        )
    ),
)

# --- 4. Threads, empty diffs, and blocking reviews -----------------------
check(
    "unresolved threads are counted and resolved ones are not",
    pr_sweep.unresolved_threads(make_pr(threads=(True, False, False))) == 2,
)
check(
    "an empty diff is a finding",
    "empty-diff" in pr_sweep.findings_for(make_pr(files=0, reviews=[REAL_REVIEW])),
)
check(
    "a non-empty diff is not flagged as empty",
    "empty-diff" not in pr_sweep.findings_for(make_pr(files=4, reviews=[REAL_REVIEW])),
)
check(
    "CHANGES_REQUESTED is reported",
    pr_sweep.changes_requested_by(
        make_pr(reviews=[review("human", "CHANGES_REQUESTED", inline=1)])
    )
    == ["human"],
)
check(
    "a later APPROVED from the same author clears an earlier block",
    pr_sweep.changes_requested_by(
        make_pr(
            reviews=[
                review("human", "CHANGES_REQUESTED", inline=1, minutes_ago=60),
                review("human", "APPROVED", inline=1, minutes_ago=10),
            ]
        )
    )
    == [],
)
check(
    "a later COMMENTED does NOT silently clear an earlier block",
    pr_sweep.changes_requested_by(
        make_pr(
            reviews=[
                review("human", "CHANGES_REQUESTED", inline=1, minutes_ago=60),
                review("human", "COMMENTED", inline=1, minutes_ago=10),
            ]
        )
    )
    == ["human"],
)

# --- 5. The staleness comparison -----------------------------------------
# The load-bearing threshold: a PR with findings that was touched moments
# ago is in flight, and the same PR untouched past the threshold is stalled.
CLEAN_PR = make_pr(number=10, threads=(True,), reviews=[REAL_REVIEW])
FINDINGS_PR_FRESH = make_pr(
    number=11, updated_minutes_ago=5, threads=(False,), reviews=[REAL_REVIEW]
)
FINDINGS_PR_STALE = make_pr(
    number=12, updated_minutes_ago=90, threads=(False,), reviews=[REAL_REVIEW]
)

check(
    "a PR with no findings is clean regardless of age",
    pr_sweep.classify(CLEAN_PR, NOW, 30)["bucket"] == "clean",
)
check(
    "a PR with findings touched 5m ago is in-flight, not stalled",
    pr_sweep.classify(FINDINGS_PR_FRESH, NOW, 30)["bucket"] == "in-flight",
)
check(
    "the same PR untouched for 90m is stalled",
    pr_sweep.classify(FINDINGS_PR_STALE, NOW, 30)["bucket"] == "stalled",
)
# Exactly at the boundary the PR is stalled: the comparison is `>=`.
check(
    "a PR idle exactly at the threshold is stalled",
    pr_sweep.classify(
        make_pr(number=13, updated_minutes_ago=30, threads=(False,),
                reviews=[REAL_REVIEW]),
        NOW, 30,
    )["bucket"]
    == "stalled",
)
# The threshold is a real parameter, not a decoration: the SAME PR must
# change bucket when the caller changes it.
check(
    "raising the threshold moves a stalled PR back to in-flight",
    pr_sweep.classify(FINDINGS_PR_STALE, NOW, 120)["bucket"] == "in-flight",
)
check(
    "lowering the threshold moves an in-flight PR to stalled",
    pr_sweep.classify(FINDINGS_PR_FRESH, NOW, 1)["bucket"] == "stalled",
)
check(
    "idle_minutes is computed from updatedAt",
    abs(pr_sweep.classify(FINDINGS_PR_STALE, NOW, 30)["idle_minutes"] - 90.0) < 0.5,
)

# --- 6. Report what was examined, not only what was found ----------------
# "0 stalled" is meaningless without "of N checked", and a sweep that
# examined nothing must be distinguishable from a clean one.
EMPTY_RESULT = {
    "repo": "o/r", "open_total": 0, "returned": 0,
    "drafts_skipped": 0, "examined": 0, "prs": [],
}
rendered_empty = pr_sweep.render(EMPTY_RESULT, 30, NOW)
check(
    "an empty sweep says it examined 0 PRs",
    "examined 0 of 0 open PRs" in rendered_empty,
)
check(
    "an empty sweep is visibly distinguishable from a clean one",
    "(no non-draft open PRs)" in rendered_empty,
)
CLEAN_RESULT = {
    "repo": "o/r", "open_total": 3, "returned": 3, "drafts_skipped": 1,
    "examined": 2,
    "prs": [pr_sweep.classify(CLEAN_PR, NOW, 30),
            pr_sweep.classify(make_pr(number=20, threads=(True,),
                                      reviews=[REAL_REVIEW]), NOW, 30)],
}
rendered_clean = pr_sweep.render(CLEAN_RESULT, 30, NOW)
check(
    "a clean sweep still reports the examined count and skipped drafts",
    "examined 2 of 3 open PRs (1 draft(s) skipped)" in rendered_clean,
)
check(
    "a clean sweep reports the zero-stalled tally explicitly",
    "=> 0 stalled" in rendered_clean,
)
# Truncation must be loud: a --limit smaller than the open-PR count means
# the sweep did NOT examine the whole set, which is the one thing this tool
# exists to guarantee.
TRUNCATED = dict(CLEAN_RESULT, open_total=99, returned=2)
check(
    "a truncated fetch is reported as TRUNCATED",
    "TRUNCATED" in pr_sweep.render(TRUNCATED, 30, NOW),
)

# --- 7. Drafts ------------------------------------------------------------
# A draft opened by `pr-on-claim` legitimately has an empty diff, so drafts
# are skipped by default rather than flagged.
check(
    "a draft with an empty diff would be flagged if examined",
    "empty-diff" in pr_sweep.findings_for(make_pr(files=0, draft=True,
                                                  reviews=[REAL_REVIEW])),
)

# --- 8. File set reporting ------------------------------------------------
file_pr = make_pr(
    number=30,
    files=["scripts/pr-sweep.py", "scripts/test_pr_sweep.py"],
    reviews=[REAL_REVIEW],
)
check(
    "pr_files extracts file path list from PR node",
    pr_sweep.pr_files(file_pr) == ["scripts/pr-sweep.py", "scripts/test_pr_sweep.py"],
)

classified = pr_sweep.classify(FINDINGS_PR_STALE, NOW, 30)
check(
    "classify includes file_count and files in classified dict",
    classified.get("file_count") == 3
    and classified.get("files") == ["file1.txt", "file2.txt", "file3.txt"],
)

stalled_rendered = pr_sweep.render(
    {
        "repo": "o/r",
        "open_total": 1,
        "returned": 1,
        "drafts_skipped": 0,
        "examined": 1,
        "prs": [pr_sweep.classify(make_pr(number=40, updated_minutes_ago=90, files=["a.md", "b.md"]), NOW, 30)],
    },
    30,
    NOW,
)
check(
    "render formats changed files line for stalled PRs",
    "files (2): a.md, b.md" in stalled_rendered,
)

over_cap_pr = make_pr(number=50, updated_minutes_ago=90, files=100)
over_cap_pr["files"]["totalCount"] = 150
over_cap_rendered = pr_sweep.render(
    {
        "repo": "o/r",
        "open_total": 1,
        "returned": 1,
        "drafts_skipped": 0,
        "examined": 1,
        "prs": [pr_sweep.classify(over_cap_pr, NOW, 30)],
    },
    30,
    NOW,
)
check(
    "render correctly calculates remaining files count when file_count exceeds fetched files list",
    "files (150): file1.txt, file2.txt, file3.txt, file4.txt, file5.txt, ... (+145 more)" in over_cap_rendered,
)

# A captured stream that came back None is an environment failure, not an empty
# sweep. `fetch`'s own docstring promises to fail loudly rather than return an
# empty set, and `json.loads(None)` would have raised TypeError instead. Pinned
# here rather than only in test_check_pr_fully_clean.py, because the previous
# round's finding was a fix generalized along one axis and left unguarded along
# another -- a pin in a sibling suite proves nothing about this file.
from unittest.mock import patch  # noqa: E402


class _NoneStdout:
    returncode = 0
    stdout = None
    stderr = ""


with patch.object(pr_sweep.subprocess, "run", lambda *a, **kw: _NoneStdout()):
    try:
        pr_sweep.fetch("owner/name", 10)
        outcome = "returned normally"
    except SystemExit as exc:
        outcome = f"SystemExit:{exc}"
    except TypeError:
        outcome = "TypeError"
check(
    "None stdout raises SystemExit naming an environment failure, not TypeError",
    outcome.startswith("SystemExit:") and "environment failure" in outcome,
)


class _NoneStderr:
    returncode = 1
    stdout = ""
    stderr = None


with patch.object(pr_sweep.subprocess, "run", lambda *a, **kw: _NoneStderr()):
    try:
        pr_sweep.fetch("owner/name", 10)
        outcome = "returned normally"
    except SystemExit as exc:
        outcome = f"SystemExit:{str(exc)[:60]}"
    except AttributeError:
        outcome = "AttributeError"
check(
    "undecodable stderr on a failed gh call does not raise AttributeError",
    outcome.startswith("SystemExit:"),
)

recorded = {}


class _Ok:
    returncode = 0
    stdout = '{"data": {"repository": {"pullRequests": {"nodes": []}}}}'
    stderr = ""


def _rec(cmd, **kwargs):
    recorded.update(kwargs)
    return _Ok()


with patch.object(pr_sweep.subprocess, "run", _rec):
    pr_sweep.fetch("owner/name", 10)
check("fetch decodes gh output as UTF-8 explicitly",
      recorded.get("encoding") == "utf-8")

print(f"\n{passes} passed, {failures} failed")
sys.exit(0 if failures == 0 else 1)
