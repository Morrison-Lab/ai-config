#!/usr/bin/env python3
"""Decide whether an mwc line still covers a PR whose head moved (ai-config#5967).

    python3 scripts/check-mwc-carry.py --pr N --approved-sha SHA [--base main]

Run it in a full clone of the PR's repository. The line CARRIES when the
approved head is on the head's first-parent chain and each commit added on it
is a two-parent merge whose second parent is on the base and whose tree is
`git merge-tree --write-tree` of its parents. Anything else VOIDS it (fail
closed). The new head must still be fully clean, and the merge pins the full
head SHA printed. Exit codes: 0 CARRIES, 1 VOID, 2 called wrong or git failed.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}")


class GitError(Exception):
    pass


def git(repo: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc


def rev(repo: str, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.strip()


def commit_for_sha(repo: str, sha: str) -> str:
    """The one commit object a hex SHA names, never a ref spelled like hex."""
    found = git(repo, "rev-parse", f"--disambiguate={sha.lower()}", check=False).stdout.split()
    commits = [o for o in found if git(repo, "cat-file", "-t", o).stdout.strip() == "commit"]
    if len(commits) != 1:
        raise GitError(f"SHA {sha} names {len(commits)} commits here; give the full SHA")
    return commits[0]


def is_ancestor(repo: str, older: str, newer: str) -> bool:
    proc = git(repo, "merge-base", "--is-ancestor", older, newer, check=False)
    if proc.returncode not in (0, 1):
        raise GitError(f"git merge-base --is-ancestor failed: {proc.stderr.strip()}")
    return proc.returncode == 0


def auto_merge_tree(repo: str, ours: str, theirs: str) -> str | None:
    """The tree git's automatic merge of the two commits gives, or None on a conflict."""
    proc = git(repo, "merge-tree", "--write-tree", ours, theirs, check=False)
    if proc.returncode == 1:
        return None
    if proc.returncode != 0:
        raise GitError(f"git merge-tree failed: {proc.stderr.strip()}")
    return proc.stdout.splitlines()[0].strip()


def verdict(repo: str, approved: str, head: str, base: str) -> tuple[bool, list[str]]:
    """(carries, reasons). Reasons explain a VOID, or list the merges a carry crossed."""
    approved, head, base = commit_for_sha(repo, approved), rev(repo, head), rev(repo, base)
    if head == approved:
        return True, ["the head is the approved head"]
    if not is_ancestor(repo, approved, head):
        return False, [f"approved head {approved[:8]} is not an ancestor of head {head[:8]} "
                       "(rebase or force-push)"]
    crossed = []
    commit = head
    while commit != approved:
        parents = git(repo, "rev-list", "--parents", "-n", "1", commit).stdout.split()[1:]
        if len(parents) != 2:
            return False, [f"{commit[:8]} is not a merge commit; it changes the PR's own content"]
        ours, theirs = parents
        if not is_ancestor(repo, theirs, base):
            return False, [f"merge {commit[:8]} brings in {theirs[:8]}, which is not on the base branch"]
        expected = auto_merge_tree(repo, ours, theirs)
        if expected is None:
            return False, [f"merge {commit[:8]} needed conflict resolution"]
        actual = git(repo, "rev-parse", f"{commit}^{{tree}}").stdout.strip()
        if actual != expected:
            return False, [f"merge {commit[:8]} differs from git's automatic merge of its parents "
                           "(an edit inside the merge)"]
        crossed.append(f"clean main merge {commit[:8]}")
        commit = ours
    return True, list(reversed(crossed))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--approved-sha", required=True, help="the head the mwc line approved")
    parser.add_argument("--base", default="main", help="base branch (default: main)")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--repo-dir", default=".", help="clone of the PR's repository")
    parser.add_argument("--no-fetch", action="store_true",
                        help="use local refs: --head-ref and the base as given")
    parser.add_argument("--head-ref", help="the current head (default: the PR head, fetched)")
    args = parser.parse_args(argv)
    if not SHA_RE.fullmatch(args.approved_sha):
        print(f"check-mwc-carry: --approved-sha {args.approved_sha!r} is not a commit SHA",
              file=sys.stderr)
        return 2
    try:
        if git(args.repo_dir, "rev-parse", "--is-shallow-repository").stdout.strip() == "true":
            raise GitError("the clone is shallow; run `git fetch --unshallow` first, "
                           "since merge-base and merge-tree need the history")
        base = args.base
        head = args.head_ref
        if not args.no_fetch:
            git(args.repo_dir, "fetch", "-q", args.remote,
                f"+refs/heads/{args.base}:refs/mwc-carry/base",
                f"+refs/pull/{args.pr}/head:refs/mwc-carry/head")
            git(args.repo_dir, "fetch", "-q", args.remote, args.approved_sha, check=False)
            base, head = "refs/mwc-carry/base", head or "refs/mwc-carry/head"
        if head is None:
            raise GitError("--no-fetch needs --head-ref")
        head = rev(args.repo_dir, head)
        carries, reasons = verdict(args.repo_dir, args.approved_sha, head, base)
    except GitError as exc:
        print(f"check-mwc-carry: {exc}", file=sys.stderr)
        return 2
    label = "CARRIES" if carries else "VOID"
    print(f"{label}: mwc line for PR {args.pr} (approved {args.approved_sha[:8]}) "
          f"to head {head}; pin exactly this SHA in the merge")
    for reason in reasons:
        print(f"  {reason}")
    return 0 if carries else 1


if __name__ == "__main__":
    sys.exit(main())
