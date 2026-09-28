#!/usr/bin/env python3
"""Verify that every workflow run triggered on a given commit succeeded.

`fully-clean.md` and `check-pr-fully-clean.py` both answer "is this PR's
HEAD clean" -- a question scoped to the PR's own checks. Neither answers
"is the commit that landed on `main` clean", and that is a different
question whenever a repo runs checks on `push` that it does not run on
`pull_request` -- a full render, a PDF build, a deploy. A PR whose own CI
was green can still turn `main` red the moment it merges, and nothing in
the PR's own check list would have shown it.

This script is the deterministic instrument for that second question: list
every workflow run GitHub attaches to one commit SHA, and exit non-zero if
any of them is not a completed success (or a deliberate skip).
It says nothing about PR-level checks, review state, or mergeability --
`check-pr-fully-clean.py` already owns those.

NOT COVERED. A workflow triggered by `workflow_run` (a deploy that waits on
a build, a post-publish check) is attached to the SHA of the run that
triggered it, and does not start until that upstream run finishes -- so a
check made immediately after the push-triggered runs complete can miss a
`workflow_run` job that has not started registering yet. This script has no
way to know such a workflow exists on the SHA it has not yet seen; re-run
the check once, after the push-triggered runs are confirmed complete, to
catch a late-starting one. See `verify-merge-commit-ci.md` for the
scheduling guidance this implies.

Incident this exists for: Morrison-Lab/mds's `publish.yml` renders every
format, PDF included, on push to `main`; its `preview.yml` renders HTML
only. Several PRs merged green on their own (HTML-only) preview checks,
and the push-triggered publish run then failed on the merge commit with a
lualatex error -- a `####` theorem-div title containing `$[0, 1]$`, which
Quarto emits as `\begin{example}[...]`, so the `]` closed the LaTeX
optional argument early
(https://github.com/Morrison-Lab/mds/actions/runs/36405007145/job/108871519751,
fixed in Morrison-Lab/mds#19). The merges were reported done without
anyone looking at that job.

Exit codes:
0: every workflow run on this SHA completed successfully (or was
   deliberately skipped by design).
1: at least one run on this SHA failed, or is still queued/in progress --
   NOT clean. Distinguished from 3 below: this code means runs exist and
   at least one of them is bad or unfinished.
2: called wrong, the repository could not be resolved, `--sha` is not a
   full 40-character hex SHA, `--sha` does not resolve to a real commit on
   the repository, or `gh` is not installed. Never used for a verdict about
   the commit -- a typo'd, truncated, or wrong-repo SHA must not produce the
   same exit as "no runs registered yet" (3), which is why `--sha` is
   validated against the commit itself before the runs are ever queried.
3: `--sha` resolved to a real commit, but no workflow runs are attached to
   it yet. This is NOT a clean verdict -- a repo with push-triggered
   workflows takes a few seconds to register them, and a `main`-only
   workflow's absence here means it has not started, not that it does not
   apply. Retry, but bound the retry: if this SHA still reads exit 3 after
   about 15 minutes, check whether the repository has any workflow
   triggered by `push` to the default branch at all. If it has none, say so
   explicitly -- that is the permanent, expected case, not a stuck check.
   If it has one, escalate that the run never registered, since a push
   trigger normally queues within seconds.

CANCELLED-BUT-SUPERSEDED RUNS. A `concurrency: cancel-in-progress` group
cancels an in-flight run when a newer commit is pushed to the same branch
before it finishes, which leaves a `cancelled` run sitting on an otherwise
clean SHA. Two shapes, decided differently, both measured on this repo's
own `main` (merge commit `25bd0c6`'s `Quarto Publish` was cancelled by the
concurrency group when `1d5b337` was pushed a minute later, and
`1d5b337`'s own `Quarto Publish` succeeded):

(a) A same-named run of the same workflow, on the SAME sha, that
    succeeded -- ordinarily a manual or automatic re-run. Treated as
    clean, silently, mirroring `check-pr-fully-clean.py`'s identical
    handling (ai-config#2277) rather than reimplementing a second
    incompatible rule for the same shape.
(b) The NEXT completed run of the same workflow on the same branch after
    this cancelled one -- not the next SUCCESS. Given cancelled X, failed
    Z, then successful Y in that order, X is reported NOT clean, naming Z,
    because Z is the run that actually answers "did the change X carried
    pass" -- a success-only query would silently skip Z and report X
    "superseded by Y (success)" instead. A chain of cancellations (X, then
    W, also cancelled by a still-newer push) is walked past rather than
    treated as an answer, so the same rule reaches through as many
    cancellations as it takes to find a real completed run. When that run
    succeeded, X is treated as clean, with an explicit "superseded by
    <sha> (success)" note in the output -- never silently, since the SHA
    actually being reported on did not itself produce a passing run. This
    is a judgment call, made here because the next run's own result
    (success or failure) is a more direct answer about the branch state X
    merged into than X's own cancellation was; note that the check against
    a branch's CURRENT head (no next run possible, since nothing is later)
    is still the one that matters for the "is `main` OK right now"
    question this script exists to answer.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional


USAGE_EXIT = 2
NOT_CLEAN_EXIT = 1
NO_RUNS_EXIT = 3

# Conclusions that do not block a clean verdict on their own. `neutral` is
# deliberately excluded: GitHub's own docs describe it as a step that
# "completed and returned neither a passing nor a failing result", so
# treating it as clean would be the more permissive reading with no stated
# reason to prefer it. Callers who want a `neutral` run to count as clean
# report so explicitly rather than getting it for free.
OK_CONCLUSIONS = {"success", "skipped"}

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(USAGE_EXIT)


def run_gh(args: List[str]) -> str:
    try:
        res = subprocess.run(
            ["gh", *args], capture_output=True, encoding="utf-8", check=False
        )
    except FileNotFoundError:
        die("`gh` is not installed or not on PATH.")
    if res.returncode != 0:
        die(f"gh {' '.join(args)} failed:\n{res.stderr}")
    return res.stdout


def resolve_repo(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    out = run_gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    repo = out.strip()
    if not repo:
        die(
            "Could not resolve the current repository. "
            "Pass -R/--repo OWNER/REPO explicitly."
        )
    return repo


def resolve_sha(repo: str, explicit: Optional[str]) -> str:
    """Resolve the SHA to check, and prove it names a real commit.

    A typo'd, truncated, or wrong-repo SHA and a genuinely un-registered
    push produce the SAME symptom against `actions/runs?head_sha=` --- an
    empty list --- so nothing downstream of that query can tell them apart.
    Settling it here, against the commit itself, is what lets exit 3 mean
    only "this real commit has no runs yet" rather than "this string did
    not match anything".
    """
    if explicit is None:
        out = run_gh(["api", f"repos/{repo}/commits/HEAD", "-q", ".sha"])
        sha = out.strip()
        if not sha:
            die("Could not resolve HEAD's SHA. Pass --sha explicitly.")
        return sha

    if not FULL_SHA_RE.match(explicit):
        die(
            f"--sha must be a full 40-character hex commit SHA, got: {explicit!r}\n"
            "A short/abbreviated SHA is not accepted: it can under-match "
            "another commit, and the runs query below needs the exact "
            "value, not a prefix."
        )

    # `run_gh` already exits 2 with the API's own error text on a 404, which
    # is exactly the "does not resolve" case -- so the die() below only
    # fires on the pathological case where the API returns 200 with an
    # empty/mismatched sha field.
    out = run_gh(["api", f"repos/{repo}/commits/{explicit}", "-q", ".sha"])
    resolved = out.strip()
    if resolved.lower() != explicit.lower():
        die(
            f"--sha {explicit!r} did not resolve to itself on {repo} "
            f"(API returned {resolved!r}); refusing to guess which commit "
            "was meant."
        )
    return explicit


def _run_key(run: Dict[str, Any]) -> tuple:
    """Identify "the same workflow's same job" across runs.

    Scoped by `workflow_id` rather than `name` alone, since a job name is
    not unique across workflows (two workflows can each define a job
    called the same thing) -- the same ambiguity `check-pr-fully-clean.py`
    disambiguates for the same reason.
    """
    return (run.get("workflow_id"), run.get("name"))


def find_same_sha_success(cancelled: Dict[str, Any], runs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Case (a): a same-workflow run on the SAME sha that succeeded."""
    key = _run_key(cancelled)
    for other in runs:
        if other is cancelled:
            continue
        if _run_key(other) != key:
            continue
        if other.get("status") == "completed" and other.get("conclusion") == "success":
            return other
    return None


def find_next_completed_branch_run(
    repo: str, cancelled: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Case (b): the NEXT completed run of the same workflow on the same
    branch, after this cancelled one.

    Deliberately not "the next SUCCESS" -- querying for `status=success`
    alone would silently skip an intervening failure. Given cancelled X,
    failed Z, successful Y in that order, a success-only query returns Y
    and reports X "superseded by Y (success)" with Z's failure invisible.
    Fetching every conclusion and walking chronologically is what lets the
    caller see Z and report X not-clean because of it, rather than because
    of anything about X's own (cancelled) run.

    Other CANCELLED runs are skipped when walking forward, not treated as
    the answer: a chain of cancellations (X cancelled, then W also
    cancelled by a still-newer push) supersedes across the whole chain,
    and W is exactly as uninformative about "is main OK" as X's own
    cancellation was.
    """
    workflow_id = cancelled.get("workflow_id")
    branch = cancelled.get("head_branch")
    created_at = cancelled.get("created_at")
    cancelled_sha = cancelled.get("head_sha")
    if not (workflow_id and branch and created_at):
        return None
    out = run_gh(
        [
            "api",
            f"repos/{repo}/actions/workflows/{workflow_id}/runs",
            "-X",
            "GET",
            "-f",
            f"branch={branch}",
            "--paginate",
            "--slurp",
        ]
    )
    pages = json.loads(out)
    candidates: List[Dict[str, Any]] = []
    for page in pages:
        candidates.extend(page.get("workflow_runs", []))
    later = [
        r
        for r in candidates
        if r.get("created_at", "") > created_at and r.get("head_sha") != cancelled_sha
    ]
    later.sort(key=lambda r: r.get("created_at", ""))
    for r in later:
        if r.get("status") != "completed":
            continue
        if r.get("conclusion") == "cancelled":
            continue
        return r
    return None


def fetch_runs(repo: str, sha: str) -> List[Dict[str, Any]]:
    """All workflow runs GitHub attaches to this commit, paginated."""
    out = run_gh(
        [
            "api",
            f"repos/{repo}/actions/runs",
            "-X",
            "GET",
            "-f",
            f"head_sha={sha}",
            "--paginate",
            "--slurp",
        ]
    )
    pages = json.loads(out)
    runs: List[Dict[str, Any]] = []
    for page in pages:
        runs.extend(page.get("workflow_runs", []))
    return runs


def evaluate(runs: List[Dict[str, Any]], repo: Optional[str] = None) -> int:
    """`repo` enables the cross-commit supersede lookup (case (b) above);
    without it, only the same-SHA supersede case (a) is checked, and a
    cancelled run with no same-SHA success is reported not-clean. Tests
    that want case (b) pass `repo` and monkeypatch `run_gh`.
    """
    if not runs:
        print("No workflow runs found for this SHA yet.", file=sys.stderr)
        print(
            "This is NOT a clean verdict -- retry once the push-triggered "
            "workflows have had time to register.",
            file=sys.stderr,
        )
        return NO_RUNS_EXIT

    not_clean: List[str] = []
    notes: List[str] = []
    for run in runs:
        name = run.get("name") or run.get("path") or "(unnamed workflow)"
        status = run.get("status")
        conclusion = run.get("conclusion")
        url = run.get("html_url", "")
        if status != "completed":
            not_clean.append(f"  - {name}: status={status} (not yet completed) {url}")
            continue
        if conclusion in OK_CONCLUSIONS:
            continue
        if conclusion == "cancelled":
            # Case (a): a same-SHA re-run succeeded. Silent, mirroring
            # check-pr-fully-clean.py's identical handling (ai-config#2277).
            if find_same_sha_success(run, runs) is not None:
                continue
            # Case (b): a later commit on the same branch superseded this
            # one via a concurrency group. Read the NEXT completed run on
            # that branch, not the next SUCCESS -- an intervening failure
            # between this cancellation and a later success must not be
            # skipped over. Reported explicitly either way, never
            # silently, since this exact SHA did not itself produce a
            # passing run.
            if repo is not None:
                next_run = find_next_completed_branch_run(repo, run)
                if next_run is not None:
                    next_sha = (next_run.get("head_sha") or "")[:8]
                    if next_run.get("conclusion") == "success":
                        notes.append(
                            f"  - {name}: cancelled on this SHA, but "
                            f"superseded by {next_sha} (success) -- "
                            "treated as clean"
                        )
                        continue
                    not_clean.append(
                        f"  - {name}: cancelled on this SHA; the next run "
                        f"on this branch ({next_sha}) concluded "
                        f"'{next_run.get('conclusion')}', not success -- "
                        f"NOT superseded-clean {next_run.get('html_url', '')}"
                    )
                    continue
        not_clean.append(f"  - {name}: conclusion={conclusion} {url}")

    total = len(runs)
    if not_clean:
        print(f"NOT CLEAN: {len(not_clean)} of {total} workflow run(s) on this SHA:")
        for line in not_clean:
            print(line)
        return NOT_CLEAN_EXIT

    print(f"CLEAN: all {total} workflow run(s) on this SHA completed successfully.")
    for run in runs:
        name = run.get("name") or run.get("path") or "(unnamed workflow)"
        print(f"  - {name}: {run.get('conclusion')}")
    for line in notes:
        print(line)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-R",
        "--repo",
        help="OWNER/REPO to check (default: resolve from the current checkout)",
    )
    parser.add_argument(
        "--sha",
        help="commit SHA to check (default: the repo's current HEAD on GitHub)",
    )
    args = parser.parse_args(argv)

    repo = resolve_repo(args.repo)
    sha = resolve_sha(repo, args.sha)
    print(f"Checking workflow runs for {repo}@{sha}...")
    runs = fetch_runs(repo, sha)
    return evaluate(runs, repo=repo)


if __name__ == "__main__":
    sys.exit(main())
