#!/usr/bin/env python3
"""Sweep open PRs and print one batch of merge lines for the maintainer.

    python3 scripts/mwc-batch.py OWNER/REPO [OWNER/REPO ...]

Before this script, every final head reached the maintainer by hand: an owner
thread reported it, a coordinator relayed it to the runner session, the
runner ran `check-pr-fully-clean.py`, and only then could the maintainer type
`mwc <repo> <pr> <sha>`. Whether a head is ready is decidable from the API, so
per `shared/workflow/derive-dont-enumerate.md` this derives the set instead
(ai-config#5578).

For each repository it lists the open, non-draft PRs that target the default
branch, skips any whose head still has a check run in progress or a genuine
failure (a cheap prefilter, so the checker runs only on candidates), runs
`check-pr-fully-clean.py` on the rest, and prints:

  * `mwc <repo> <pr> <sha>` for each clean content PR, for the maintainer to
    type in the runner thread;
  * `merge-infra-pr <repo> <pr>` for each clean infra PR, which the runner's
    standing infra grant covers;
  * one line per PR that is not ready, with the reason, so a sweep that found
    nothing reads differently from one that examined nothing.

It is read-only: it never merges, pushes, or comments. Content merges stay on
the maintainer's typed `mwc`; infra merges stay on `scripts/merge-infra-pr`,
which re-checks everything itself. The runner session runs this on a
schedule and posts the report.

The infra test is `scripts/merge-infra-pr`'s own: the infra repository list
is read from that script and the path list from
`hooks/no-unauthorized-merge.py`, and a renamed file's previous path counts
too. Both are read from the checkout this script runs from, while
merge-infra-pr reads a fresh clone of `main`, so run it from an up-to-date
`main` checkout or the two can classify differently.

The checker runs with only the flags given here. merge-infra-pr passes
`--reviewer-out-of-quota agy`, so pass the same `--reviewer-out-of-quota`
while agy is out of quota; without it the sweep is the stricter of the two.

Exit codes: 0 report printed; 2 called wrong or a GitHub read failed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check-pr-fully-clean.py"
MERGE_INFRA_PR = ROOT / "scripts" / "merge-infra-pr"
MERGE_HOOK = ROOT / "hooks" / "no-unauthorized-merge.py"

# Same set as pr-sweep.py: CANCELLED, SKIPPED and NEUTRAL are not failures.
FAILING_CONCLUSIONS = {"failure", "timed_out", "startup_failure", "action_required"}

# Characters of the head SHA shown in an mwc line.
SHA_CHARS = 8

# Checker blocker lines to quote per not-ready PR, and characters of each.
MAX_REASONS = 3
REASON_CHARS = 200

# The checker's line for a passed check run whose annotations are unread.
UNREAD_RE = re.compile(r"not yet read: run `gh api repos/[^/]+/[^/]+/check-runs/(\d+)/annotations`")
ANNOTATIONS_ARG_RE = re.compile(r"([\w.-]+#\d+)=(all|\d+(?:,\d+)*)")

INFRA_REPOS_RE = re.compile(r'^\s*([\w.|-]+)\)\s*scope="infra repository', re.M)
CHANGELOG_RE = re.compile(r"changelog[.]d/.+")
CANVAS_RE = re.compile(r"(^|/)canvas/")


def die(message: str) -> None:
    print(f"mwc-batch: {message}", file=sys.stderr)
    sys.exit(2)


def gh_pages(path: str) -> list:
    """Every page of a REST GET, via `gh api --paginate --slurp`; fails fast."""
    proc = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", path],
        capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        die(f"gh api {path} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def gh_list(path: str) -> list:
    """A list endpoint's items across all pages."""
    return [item for page in gh_pages(path) for item in page]


def infra_repos(script_text: str) -> set[str]:
    """The whole-repository infra set from merge-infra-pr's `case` arm."""
    match = INFRA_REPOS_RE.search(script_text)
    if not match:
        die(f"cannot find the infra repository list in {MERGE_INFRA_PR}")
    return set(match.group(1).split("|"))


def infra_patterns() -> tuple:
    spec = importlib.util.spec_from_file_location("merge_hook", MERGE_HOOK)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    return hook.INFRA_PATH_PATTERNS + (CHANGELOG_RE,)


def scope(repo_name: str, files: list[str], repos: set[str], patterns) -> str:
    """'canvas', 'infra' or 'content', by merge-infra-pr's rules."""
    if any(CANVAS_RE.search(f) for f in files):
        return "canvas"
    if repo_name in repos:
        return "infra"
    if files and all(any(p.fullmatch(f) for p in patterns) for f in files):
        return "infra"
    return "content"


def ci_state(check_runs: list[dict]) -> str:
    """'green', 'running', 'failing' or 'none' for a head's check runs."""
    if not check_runs:
        return "none"
    if any(r.get("status") != "completed" for r in check_runs):
        return "running"
    if any(r.get("conclusion") in FAILING_CONCLUSIONS for r in check_runs):
        return "failing"
    return "green"


def checker_reasons(output: str) -> tuple[list[str], list[str]]:
    """(blocker lines other than unread annotations, unread check-run ids).

    Notes are left out. Unread annotations are split off because they are the
    commonest blocker on an otherwise clean head and the runner clears them
    in one batch read, not one PR at a time.
    """
    reasons, unread = [], []
    for ln in output.splitlines():
        if not ln.startswith("  - ") or "NOTE" in ln:
            continue
        match = UNREAD_RE.search(ln)
        if match:
            unread.append(match.group(1))
        else:
            reasons.append(ln.strip()[2:][:REASON_CHARS])
    return reasons[:MAX_REASONS], unread


def run_checker(repo: str, number: int, annotations_read: str,
        extra_args: list[str]) -> tuple[bool, list[str], list[str]]:
    """(clean, reasons, unread annotation run ids) for one PR."""
    command = [sys.executable, str(CHECKER), str(number), "-R", repo, *extra_args]
    if annotations_read:
        command += ["--annotations-read", annotations_read]
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return True, [], []
    if proc.returncode != 1:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:]
        return False, [f"checker exited {proc.returncode}: {' '.join(tail)}"], []
    reasons, unread = checker_reasons(proc.stdout)
    if not reasons and not unread:
        reasons = ["checker exited 1"]
    return False, reasons, unread


def parse_annotations_read(values: list[str]) -> dict[str, str]:
    """`REPO#N=IDS` pairs, keyed `REPO#N`, as given to --annotations-read."""
    parsed = {}
    for value in values:
        match = ANNOTATIONS_ARG_RE.fullmatch(value)
        if not match:
            die(f"--annotations-read takes REPO#N=ID[,ID...] or REPO#N=all, got {value!r}")
        parsed[match.group(1)] = match.group(2)
    return parsed


def pr_paths(repo: str, number: int) -> list[str]:
    """Every path a PR changes, plus each renamed file's previous path."""
    paths = []
    for f in gh_list(f"repos/{repo}/pulls/{number}/files?per_page=100"):
        paths.append(f["filename"])
        if f.get("previous_filename"):
            paths.append(f["previous_filename"])
    return paths


def sweep_repo(repo: str, repos: set[str], patterns, annotations_read: dict[str, str],
        extra_args: list[str]) -> tuple[list[dict], int]:
    """(one result per open non-draft PR, number of drafts skipped)."""
    owner_repo = repo.split("/")
    if len(owner_repo) != 2 or not all(owner_repo):
        die(f"repository must be OWNER/REPO, got {repo!r}")
    name = owner_repo[1]
    results, drafts = [], 0
    for pr in gh_list(f"repos/{repo}/pulls?state=open&per_page=100"):
        number, sha = pr["number"], pr["head"]["sha"]
        row = {"repo": name, "number": number, "sha": sha, "title": pr["title"]}
        if pr.get("draft"):
            drafts += 1
            continue
        default = pr["base"]["repo"]["default_branch"]
        if pr["base"]["ref"] != default:
            results.append({**row, "status": "waiting",
                            "reasons": [f"base is {pr['base']['ref']}, not {default}"]})
            continue
        pages = gh_pages(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")
        state = ci_state([run for page in pages for run in page["check_runs"]])
        if state != "green":
            results.append({**row, "status": "waiting", "reasons": [f"CI {state}"]})
            continue
        clean, reasons, unread = run_checker(
            repo, number, annotations_read.get(f"{name}#{number}", ""), extra_args)
        if unread:
            reasons.append(
                f"{len(unread)} check run(s) with unread annotations: read them with "
                f"`python3 scripts/batch-read-annotations.py --repo {repo} --sha {sha}`, "
                f"then rerun with `--annotations-read {name}#{number}=<ids from its last line>`")
        if not clean:
            results.append({**row, "status": "not clean", "reasons": reasons})
            continue
        files = pr_paths(repo, number)
        results.append({**row, "status": scope(name, files, repos, patterns), "reasons": []})
    return results, drafts


def render(results: list[dict], repos_swept: list[str], drafts: int) -> str:
    out = [f"mwc-batch: {len(results)} open non-draft PRs examined in "
           f"{', '.join(repos_swept)} ({drafts} drafts skipped)"]
    groups = [
        ("content", "Ready for the maintainer's mwc:",
         lambda r: f"mwc {r['repo']} {r['number']} {r['sha'][:SHA_CHARS]}"),
        ("infra", "Ready for merge-infra-pr (infra grant):",
         lambda r: f"merge-infra-pr {r['repo']} {r['number']}"),
        ("canvas", "Clean but touches canvas/ (needs the maintainer's explicit ok):",
         lambda r: f"{r['repo']}#{r['number']} {r['sha'][:SHA_CHARS]}"),
    ]
    for status, heading, line in groups:
        rows = [r for r in results if r["status"] == status]
        out.append(f"\n{heading} {len(rows)}")
        out.extend(f"  {line(r)}   ({r['title']})" for r in rows)
    rest = [r for r in results if r["status"] in ("waiting", "not clean")]
    out.append(f"\nNot ready: {len(rest)}")
    for r in rest:
        out.append(f"  {r['repo']}#{r['number']} {r['sha'][:SHA_CHARS]} {r['status']}: "
                   + "; ".join(r["reasons"]))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repos", nargs="+", metavar="OWNER/REPO")
    parser.add_argument(
        "--annotations-read", action="append", default=[], metavar="REPO#N=IDS",
        help="Repeatable. Passed to the checker for that PR as --annotations-read "
             "IDS, only after those runs' annotations were read and fixed or "
             "explained (IDS is ID[,ID...] or all).")
    parser.add_argument(
        "--reviewer-out-of-quota", action="append", default=[], metavar="NAME",
        help="Repeatable. Passed to the checker for every PR, as merge-infra-pr "
             "passes `agy`.")
    args = parser.parse_args(argv)
    annotations_read = parse_annotations_read(args.annotations_read)
    extra_args = [arg for name in args.reviewer_out_of_quota
                  for arg in ("--reviewer-out-of-quota", name)]
    repos = infra_repos(MERGE_INFRA_PR.read_text(encoding="utf-8"))
    patterns = infra_patterns()
    results, drafts = [], 0
    for repo in args.repos:
        repo_results, repo_drafts = sweep_repo(repo, repos, patterns, annotations_read, extra_args)
        results.extend(repo_results)
        drafts += repo_drafts
    print(render(results, args.repos, drafts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
