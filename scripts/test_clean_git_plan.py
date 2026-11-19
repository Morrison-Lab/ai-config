#!/usr/bin/env python3
"""Tests for clean-git-plan.py on a real throwaway repository and origin.
Run: python3 scripts/test_clean_git_plan.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clean-git-plan.py")
OLD = "2026-01-01T00:00:00Z"
ENV = {**os.environ, "GIT_AUTHOR_DATE": OLD, "GIT_COMMITTER_DATE": OLD,
       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
FAILS = []


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=ENV, check=True, capture_output=True)


def commit(cwd, name):
    with open(os.path.join(cwd, name), "w", encoding="utf-8") as fh:
        fh.write(name)
    git(cwd, "add", name)
    git(cwd, "commit", "-q", "-m", name)


def pr(n, head, state, base="main", merged=None):
    return {"number": n, "headRefName": head, "baseRefName": base, "state": state,
            "mergedAt": merged, "author": {"login": "t"}}


def check(name, got, want):
    if got != want:
        FAILS.append(f"{name}: got {got!r}, want {want!r}")


with tempfile.TemporaryDirectory() as root:
    origin, repo = os.path.join(root, "origin.git"), os.path.join(root, "repo")
    git(root, "init", "-q", "--bare", "-b", "main", origin)
    git(root, "clone", "-q", origin, repo)
    commit(repo, "a")
    git(repo, "push", "-q", "origin", "main")
    for name in ("open-head", "stack-base", "zero-ahead", "landed", "unmerged", "closed"):
        git(repo, "branch", name)
    for name in ("open-head", "landed", "unmerged", "closed"):
        git(repo, "checkout", "-q", name)
        commit(repo, name)
    git(repo, "checkout", "-q", "main")
    git(repo, "push", "-q", "origin", "--all")
    git(repo, "fetch", "-q", "origin")
    git(repo, "worktree", "add", "-q", os.path.join(root, "wt-dirty"), "unmerged")
    with open(os.path.join(root, "wt-dirty", "x"), "w", encoding="utf-8") as fh:
        fh.write("x")
    git(repo, "worktree", "add", "-q", os.path.join(root, "wt-gone"), "-b", "gone")
    shutil.rmtree(os.path.join(root, "wt-gone"))
    git(repo, "worktree", "add", "-q", os.path.join(root, "wt-broken"), "-b", "broken")
    with open(os.path.join(root, "wt-broken", ".git"), "w", encoding="utf-8") as fh:
        fh.write("gitdir: /nonexistent\n")  # git status now fails there
    prs = [pr(1, "open-head", "OPEN"), pr(2, "child", "OPEN", base="stack-base"),
           pr(3, "landed", "MERGED", merged="2026-06-01T00:00:00Z"),
           pr(4, "closed", "CLOSED")]
    prs_file = os.path.join(root, "prs.json")
    with open(prs_file, "w", encoding="utf-8") as fh:
        json.dump(prs, fh)
    run = subprocess.run([sys.executable, SCRIPT, "--repo", repo, "--prs-json", prs_file],
                         capture_output=True, check=False, text=True)
    if run.returncode != 0:
        sys.exit(f"clean-git-plan failed: {run.stderr}")
    plan = json.loads(run.stdout)[0]
    remote = {r["branch"]: r["action"] for r in plan["remote"]}
    local = {r["branch"]: r["action"] for r in plan["local"]}
    trees = {os.path.basename(r["path"]): r["action"] for r in plan["worktrees"]}
    for name, want in [("open-head", "skip"), ("stack-base", "skip"),
                       ("zero-ahead", "delete"), ("landed", "delete"),
                       ("unmerged", "flag"), ("closed", "flag")]:
        check(f"remote {name}", remote.get(name), want)
    for name, want in [("open-head", "skip"), ("stack-base", "skip"),
                       ("zero-ahead", "delete-d"), ("landed", "delete-D"),
                       ("closed", "flag")]:
        check(f"local {name}", local.get(name), want)
    check("local branch held by a live worktree is not listed", "unmerged" in local, False)
    check("dirty worktree", trees.get("wt-dirty"), "flag")
    check("worktree whose directory is gone", trees.get("wt-gone"), "prune")
    check("worktree where git status fails", trees.get("wt-broken"), "flag")
    many = subprocess.run([sys.executable, SCRIPT, "--repo", root, "--prs-json", prs_file],
                          capture_output=True, check=False, text=True)
    check("non-repo parent classifies its child repositories, not their worktrees",
          [os.path.basename(p["repo"]) for p in json.loads(many.stdout or "[]")], ["repo"])
    git(root, "init", "-q", os.path.join(root, "repo2"))
    check("one --prs-json file refused for two repositories",
          subprocess.run([sys.executable, SCRIPT, "--repo", root, "--prs-json", prs_file],
                         capture_output=True, check=False, text=True).returncode != 0, True)

if FAILS:
    print("\n".join(FAILS))
    sys.exit(1)
print("clean-git-plan: all cases pass")
