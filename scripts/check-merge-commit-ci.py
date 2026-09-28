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
any of them is not a completed success (or a deliberate skip/neutral).
It says nothing about PR-level checks, review state, or mergeability --
`check-pr-fully-clean.py` already owns those.

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
   skipped/neutral by design).
1: at least one run on this SHA failed, or is still queued/in progress --
   NOT clean. Distinguished from 3 below: this code means runs exist and
   at least one of them is bad or unfinished.
2: called wrong, or the repository/SHA could not be resolved, or `gh` is
   not installed. Never used for a verdict about the commit.
3: no workflow runs are attached to this SHA yet. This is NOT a clean
   verdict -- a repo with push-triggered workflows takes a few seconds to
   register them, and a `main`-only workflow's absence here means it has
   not started, not that it does not apply. Retry rather than reading this
   as "nothing to check".
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any, Dict, List, Optional


USAGE_EXIT = 2
NOT_CLEAN_EXIT = 1
NO_RUNS_EXIT = 3

# Conclusions that do not block a clean verdict on their own.
OK_CONCLUSIONS = {"success", "skipped", "neutral"}


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
    if explicit:
        return explicit
    out = run_gh(["api", f"repos/{repo}/commits/HEAD", "-q", ".sha"])
    sha = out.strip()
    if not sha:
        die("Could not resolve HEAD's SHA. Pass --sha explicitly.")
    return sha


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


def evaluate(runs: List[Dict[str, Any]]) -> int:
    if not runs:
        print("No workflow runs found for this SHA yet.", file=sys.stderr)
        print(
            "This is NOT a clean verdict -- retry once the push-triggered "
            "workflows have had time to register.",
            file=sys.stderr,
        )
        return NO_RUNS_EXIT

    not_clean: List[str] = []
    for run in runs:
        name = run.get("name") or run.get("path") or "(unnamed workflow)"
        status = run.get("status")
        conclusion = run.get("conclusion")
        url = run.get("html_url", "")
        if status != "completed":
            not_clean.append(f"  - {name}: status={status} (not yet completed) {url}")
            continue
        if conclusion not in OK_CONCLUSIONS:
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
    return evaluate(runs)


if __name__ == "__main__":
    sys.exit(main())
