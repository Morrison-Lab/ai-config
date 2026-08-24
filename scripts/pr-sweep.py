#!/usr/bin/env python3
"""Derive the live set of open PRs and report which ones are stalled.

An agent brief that enumerates work items by number ("drive #937, #939,
#943, #946") is a snapshot, stale the moment it is written. Agents then do
their jobs correctly on the lists they were given, and the PRs that appear
*between* the lists -- opened by another session, or newly broken -- are
covered by nobody. No artifact can show that gap, because coverage is a
property of the set rather than of any member, so the only way to see it is
to re-derive the set.

Per `shared/workflow/algorithmatize-checks.md`, "which open PRs are stalled"
has a numeric definition over data the API already returns, so it belongs in
an instrument rather than in anyone's periodic judgment. The prose
counterpart to this script is `shared/workflow/derive-dont-enumerate.md`;
`skills/pr-status-all/SKILL.md` remains the richer per-PR dashboard, and
this script is the cheap standing sweep that says which PRs that dashboard
should be pointed at.

Four correctness details, each from a real misread on 2026-07-30/31:

  1. `gh pr checks` renders a CANCELLED job as `fail`. A very short
     "failing" job is usually a concurrency cancellation, not a defect. This
     reads each check run's own `conclusion` and counts only genuine
     failures, so the tool does not cry wolf and get ignored.
  2. A formal review's body is frequently EMPTY, with the finding in a
     per-line inline comment. A body-only scan misses those entirely, so
     review activity is measured by inline-comment count as well as body.
  3. Copilot quota refusals arrive as `COMMENTED` reviews with zero inline
     comments and a body saying it could not review. Those inflate the
     reviewer count without anyone having read the diff, so they are
     excluded from "has been reviewed".
  4. A PR can look clean with an EMPTY DIFF, if its implementation was
     never pushed. `files.totalCount` catches that.

Always reports what it examined, not only what it found: "0 stalled" is
meaningless without "of N open PRs checked", and a sweep that examined
nothing must be distinguishable from a clean one.

Read-only. It reports; it never pushes, comments, or merges. Reporting a PR
as stalled is not authorization to drive it -- `shared/workflow/ardi.md`
limits that to PRs a session owns or has explicitly claimed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone

# Minutes of inactivity after which a PR carrying an unaddressed finding is
# treated as stalled rather than in flight. Thirty minutes is well past a
# normal review round trip (a push, its checks, and a verdict) but short
# enough to catch the 73-minute and 26-minute gaps that motivated this
# script. A parameter rather than a literal, per
# `shared/coding/configurable-parameters.md`.
DEFAULT_STALE_MINUTES = 30

# Maximum number of changed file paths to show individually in text output.
MAX_FILES_SHOWN = 5

# Check-run conclusions that mean the job genuinely failed. CANCELLED is
# deliberately absent: on workflows with `concurrency: cancel-in-progress`,
# a superseded run is cancelled as designed. SKIPPED and NEUTRAL are not
# failures either, and a draft PR's review job reports SKIPPED routinely.
FAILING_CONCLUSIONS = {
    "FAILURE",
    "TIMED_OUT",
    "STARTUP_FAILURE",
    "ACTION_REQUIRED",
}

# Legacy commit-status states that mean failure.
FAILING_STATUS_STATES = {"FAILURE", "ERROR"}

# Substrings marking a review that declined to review, rather than one that
# read the diff. Matched case-insensitively against the review body.
REFUSAL_MARKERS = (
    "unable to review",
    "quota limit",
    "reached their quota",
    "rate limit",
    "spend limit",
)

QUERY = """
query($owner:String!, $name:String!, $first:Int!) {
  repository(owner:$owner, name:$name) {
    pullRequests(states:OPEN, first:$first, orderBy:{field:UPDATED_AT, direction:DESC}) {
      totalCount
      nodes {
        number title url isDraft updatedAt
        author { login }
        files(first:100) { totalCount nodes { path } }
        reviewThreads(first:100) { totalCount nodes { isResolved } }
        reviews(last:40) {
          nodes { author { login } state body submittedAt comments(first:1) { totalCount } }
        }
        commits(last:1) {
          nodes { commit { oid committedDate
            statusCheckRollup { contexts(first:100) { nodes {
              __typename
              ... on CheckRun { name status conclusion }
              ... on StatusContext { context state }
            } } } } }
        }
      }
    }
  }
}
"""


def parse_time(value):
    """Parse a GitHub ISO-8601 timestamp into an aware datetime."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def pr_files(pr):
    """List of file paths changed in this PR (up to 100)."""
    nodes = (pr.get("files") or {}).get("nodes") or []
    return [n.get("path") for n in nodes if isinstance(n, dict) and n.get("path")]


def head_commit(pr):
    """Return the PR's head commit node, or None when the PR has no commits."""
    nodes = (pr.get("commits") or {}).get("nodes") or []
    return nodes[0]["commit"] if nodes else None


def failing_checks(pr):
    """Names of check runs that genuinely failed on the head commit.

    Reads each run's own `conclusion` rather than a rendered pass/fail
    column, so a CANCELLED run -- normal under
    `concurrency: cancel-in-progress` -- is not reported as a failure.
    """
    commit = head_commit(pr)
    if not commit:
        return []
    rollup = commit.get("statusCheckRollup") or {}
    contexts = (rollup.get("contexts") or {}).get("nodes") or []
    failed = []
    for ctx in contexts:
        if ctx.get("__typename") == "CheckRun":
            if ctx.get("conclusion") in FAILING_CONCLUSIONS:
                failed.append(ctx.get("name") or "?")
        elif ctx.get("state") in FAILING_STATUS_STATES:
            failed.append(ctx.get("context") or "?")
    # A check-run name is not unique on a head commit -- two workflow runs
    # can each define a job by the same name -- so de-duplicate for display
    # while keeping the order stable.
    return sorted(set(failed))


def pending_checks(pr):
    """Names of check runs still queued or running on the head commit."""
    commit = head_commit(pr)
    if not commit:
        return []
    rollup = commit.get("statusCheckRollup") or {}
    contexts = (rollup.get("contexts") or {}).get("nodes") or []
    pending = [
        ctx.get("name") or "?"
        for ctx in contexts
        if ctx.get("__typename") == "CheckRun"
        and ctx.get("status") in {"QUEUED", "IN_PROGRESS", "WAITING", "PENDING"}
    ]
    return sorted(set(pending))


def is_refusal(review):
    """True when a review declined to review rather than reading the diff.

    A quota refusal arrives as a `COMMENTED` review with zero inline
    comments and a body saying so. Requiring the zero-comment half matters:
    a reviewer that genuinely read the diff and happened to mention a rate
    limit in passing still leaves inline comments, and must keep counting as
    review activity.
    """
    if (review.get("comments") or {}).get("totalCount", 0) > 0:
        return False
    body = (review.get("body") or "").lower()
    return any(marker in body for marker in REFUSAL_MARKERS)


def genuine_reviews(pr):
    """Reviews that actually read the diff, newest last."""
    nodes = (pr.get("reviews") or {}).get("nodes") or []
    return [r for r in nodes if not is_refusal(r)]


def unresolved_threads(pr):
    """Count of review threads still open.

    An outdated thread still counts: addressing a finding and resolving its
    thread are separate actions, and only the second clears it.
    """
    nodes = (pr.get("reviewThreads") or {}).get("nodes") or []
    return sum(1 for t in nodes if not t.get("isResolved"))


def changes_requested_by(pr):
    """Logins whose latest review state is CHANGES_REQUESTED.

    Reduces per author over states that express a verdict, so a later
    `COMMENTED` review does not silently clear an earlier block.
    """
    latest = {}
    for review in genuine_reviews(pr):
        state = review.get("state")
        if state in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            login = (review.get("author") or {}).get("login") or "?"
            latest[login] = state
    return sorted(l for l, s in latest.items() if s == "CHANGES_REQUESTED")


def head_is_unreviewed(pr):
    """True when no genuine review has landed at or after the head commit."""
    commit = head_commit(pr)
    if not commit:
        return False
    pushed = parse_time(commit.get("committedDate"))
    reviewed = [
        parse_time(r.get("submittedAt"))
        for r in genuine_reviews(pr)
        if r.get("submittedAt")
    ]
    if not reviewed:
        return True
    return max(reviewed) < pushed


def idle_minutes(pr, now):
    """Minutes since the PR was last touched by anything."""
    updated = parse_time(pr.get("updatedAt"))
    if updated is None:
        return 0.0
    return (now - updated).total_seconds() / 60.0


def findings_for(pr):
    """Actionable problems on a PR, independent of how long it has sat.

    Ordered most to least blocking, so the first entry is the headline.
    """
    reasons = []
    if (pr.get("files") or {}).get("totalCount", 0) == 0:
        reasons.append("empty-diff")
    failed = failing_checks(pr)
    if failed:
        reasons.append("failing-checks(" + ", ".join(failed) + ")")
    blocked = changes_requested_by(pr)
    if blocked:
        reasons.append("changes-requested(" + ", ".join(blocked) + ")")
    open_threads = unresolved_threads(pr)
    if open_threads:
        reasons.append(f"unresolved-threads({open_threads})")
    if head_is_unreviewed(pr):
        pending = pending_checks(pr)
        if pending:
            reasons.append(f"head-unreviewed, {len(pending)} check(s) still running")
        else:
            reasons.append("head-unreviewed")
    return reasons


def classify(pr, now, stale_minutes):
    """Bucket one PR as stalled, in-flight, or clean.

    `stalled` means it carries an unaddressed finding AND nothing has
    touched it for longer than the threshold. A PR with findings that was
    touched moments ago is `in-flight` -- someone is plausibly on it, and
    flagging it would be the crying-wolf failure this tool exists to avoid.
    """
    reasons = findings_for(pr)
    idle = idle_minutes(pr, now)
    if not reasons:
        bucket = "clean"
    elif idle >= stale_minutes:
        bucket = "stalled"
    else:
        bucket = "in-flight"
    file_paths = pr_files(pr)
    file_count = (pr.get("files") or {}).get("totalCount", len(file_paths))
    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "author": (pr.get("author") or {}).get("login"),
        "isDraft": pr.get("isDraft", False),
        "idle_minutes": round(idle, 1),
        "file_count": file_count,
        "files": file_paths,
        "reasons": reasons,
        "bucket": bucket,
    }


def format_files_line(pr):
    """Format file count and paths for display in text output."""
    files = pr.get("files") or []
    count = pr.get("file_count", len(files))
    if not files and count == 0:
        return None
    file_list = ", ".join(files[:MAX_FILES_SHOWN])
    if count > MAX_FILES_SHOWN:
        file_list += f", ... (+{count - MAX_FILES_SHOWN} more)"
    return f"            files ({count}): {file_list}"


def fetch(repo, limit):
    """Fetch open PRs for `owner/name` via one GraphQL call.

    Fails loudly rather than returning an empty set: a sweep that silently
    examined nothing is indistinguishable from a clean one, which is the
    exact failure `shared/principles/fail-fast.md` warns about.
    """
    if "/" not in repo:
        raise SystemExit(f"pr-sweep: --repo needs owner/name, got {repo!r}")
    owner, name = repo.split("/", 1)
    proc = subprocess.run(
        [
            "gh", "api", "graphql",
            "-F", f"owner={owner}",
            "-F", f"name={name}",
            "-F", f"first={limit}",
            "-f", f"query={QUERY}",
        ],
        capture_output=True,
        # `encoding` is load-bearing on Windows; see the long note in
        # `check-pr-fully-clean.py`'s `run_cmd`. Without it the locale codec
        # (cp1252) silently mojibakes most non-ASCII and hard-fails on five
        # bytes, the latter leaving `stdout` as None with `returncode` 0 -- so
        # the guard below passes and `json.loads(None)` raises TypeError, in a
        # function whose docstring promises to fail loudly rather than return
        # an empty set.
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"pr-sweep: gh failed for {repo} (exit {proc.returncode}): "
            f"{proc.stderr.strip()}"
        )
    if proc.stdout is None:
        raise SystemExit(
            f"pr-sweep: gh produced no capturable stdout for {repo}; its output "
            "could not be read or decoded. This is an environment failure, not "
            "an empty sweep."
        )
    payload = json.loads(proc.stdout)
    if payload.get("errors"):
        raise SystemExit(f"pr-sweep: GraphQL errors for {repo}: {payload['errors']}")
    repository = (payload.get("data") or {}).get("repository")
    if repository is None:
        raise SystemExit(f"pr-sweep: no such repository: {repo}")
    return repository["pullRequests"]


def sweep(repo, stale_minutes, limit, include_drafts, now):
    """Classify every open PR in one repo."""
    prs = fetch(repo, limit)
    nodes = prs.get("nodes") or []
    total = prs.get("totalCount", len(nodes))
    examined, skipped = [], 0
    for pr in nodes:
        if pr.get("isDraft") and not include_drafts:
            skipped += 1
            continue
        examined.append(classify(pr, now, stale_minutes))
    return {
        "repo": repo,
        "open_total": total,
        "returned": len(nodes),
        "drafts_skipped": skipped,
        "examined": len(examined),
        "prs": examined,
    }


def render(result, stale_minutes, now):
    """Print one repo's result, leading with what was examined."""
    lines = []
    truncated = ""
    if result["returned"] < result["open_total"]:
        truncated = (
            f" [TRUNCATED: {result['returned']} of {result['open_total']} fetched;"
            " raise --limit]"
        )
    lines.append(
        f"{result['repo']}: examined {result['examined']} of {result['open_total']} "
        f"open PRs ({result['drafts_skipped']} draft(s) skipped), "
        f"threshold {stale_minutes}m, at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"{truncated}"
    )
    buckets = {"stalled": [], "in-flight": [], "clean": []}
    for pr in result["prs"]:
        buckets[pr["bucket"]].append(pr)
    for pr in buckets["stalled"]:
        lines.append(
            f"  STALLED   #{pr['number']}  idle {pr['idle_minutes']:>6.1f}m  "
            f"{'; '.join(pr['reasons'])}"
        )
        lines.append(f"            {pr['title'][:88]}")
        fl = format_files_line(pr)
        if fl:
            lines.append(fl)
    for pr in buckets["in-flight"]:
        lines.append(
            f"  in-flight #{pr['number']}  idle {pr['idle_minutes']:>6.1f}m  "
            f"{'; '.join(pr['reasons'])}"
        )
        fl = format_files_line(pr)
        if fl:
            lines.append(fl)
    if buckets["clean"]:
        nums = ", ".join(f"#{p['number']}" for p in buckets["clean"])
        lines.append(f"  clean     {nums}")
    if not result["prs"]:
        lines.append("  (no non-draft open PRs)")
    lines.append(
        f"  => {len(buckets['stalled'])} stalled, "
        f"{len(buckets['in-flight'])} in-flight, "
        f"{len(buckets['clean'])} clean"
    )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Report which open PRs are stalled, deriving the set live."
    )
    parser.add_argument(
        "--repo", "-R", action="append", required=True, metavar="OWNER/NAME",
        help="Repository to sweep; repeat for several.",
    )
    parser.add_argument(
        "--stale-minutes", type=float, default=DEFAULT_STALE_MINUTES,
        help=f"Idle threshold in minutes (default {DEFAULT_STALE_MINUTES}).",
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Maximum open PRs to fetch per repo (default 100).",
    )
    parser.add_argument(
        "--include-drafts", action="store_true",
        help="Also examine draft PRs (skipped by default).",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit 1 when any PR is stalled (default: advisory, always 0).",
    )
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    results = [
        sweep(repo, args.stale_minutes, args.limit, args.include_drafts, now)
        for repo in args.repo
    ]

    if args.json:
        print(json.dumps(
            {"generated_at": now.isoformat(),
             "stale_minutes": args.stale_minutes,
             "repos": results},
            indent=2,
        ))
    else:
        print("\n\n".join(render(r, args.stale_minutes, now) for r in results))

    stalled = sum(
        1 for r in results for p in r["prs"] if p["bucket"] == "stalled"
    )
    return 1 if (args.strict and stalled) else 0


if __name__ == "__main__":
    sys.exit(main())
