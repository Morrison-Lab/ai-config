#!/usr/bin/env python3
"""Tests for clean-git-execute.py on a real throwaway repository and origin.
Run: python3 scripts/test_clean_git_execute.py"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.join(HERE, "clean-git-plan.py")
EXECUTE = os.path.join(HERE, "clean-git-execute.py")
OLD = "2026-01-01T00:00:00Z"
ENV = {**os.environ, "GIT_AUTHOR_DATE": OLD, "GIT_COMMITTER_DATE": OLD,
       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
FAILS = []


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, check=True,
                          capture_output=True, text=True).stdout


def commit(cwd, name):
    with open(os.path.join(cwd, name), "w", encoding="utf-8") as fh:
        fh.write(name)
    git(cwd, "add", name)
    git(cwd, "commit", "-q", "-m", name)


def pr(n, head, author="t"):
    return {"number": n, "headRefName": head, "baseRefName": "main", "state": "MERGED",
            "mergedAt": "2026-06-01T00:00:00Z", "author": {"login": author}}


def check(name, got, want):
    if got != want:
        FAILS.append(f"{name}: got {got!r}, want {want!r}")


def branches(cwd, pattern):
    return set(git(cwd, "for-each-ref", "--format=%(refname:short)", pattern).split())


with tempfile.TemporaryDirectory() as root:
    origin, repo = os.path.join(root, "origin.git"), os.path.join(root, "repo")
    git(root, "init", "-q", "--bare", "-b", "main", origin)
    git(root, "clone", "-q", "-c", "init.defaultBranch=main", origin, repo)
    commit(repo, "a")
    git(repo, "push", "-q", "origin", "main")
    for name in ("zero-ahead", "landed", "landed-other", "claimed", "unmerged"):
        git(repo, "branch", name)
    for name in ("landed", "landed-other", "claimed", "unmerged"):
        git(repo, "checkout", "-q", name)
        commit(repo, name)
    git(repo, "checkout", "-q", "main")
    git(repo, "push", "-q", "origin", "--all")
    git(repo, "fetch", "-q", "origin")
    dead = os.path.join(root, "wt-dead")
    git(repo, "worktree", "add", "-q", dead, "-b", "wt-dead")
    long_ago = time.time() - 3600
    os.utime(dead, (long_ago, long_ago))  # older than the classifier's live window

    prs = [pr(3, "landed"), pr(5, "landed-other", author="someone"), pr(6, "claimed")]
    prs_file = os.path.join(root, "prs.json")
    with open(prs_file, "w", encoding="utf-8") as fh:
        json.dump(prs, fh)
    stamp = datetime.now(timezone.utc).isoformat()
    comments_file = os.path.join(root, "comments.json")
    with open(comments_file, "w", encoding="utf-8") as fh:
        json.dump({"6": [{"body": "Please hold off, I am rebasing this.", "createdAt": stamp}],
                   "3": [{"body": "hold off -- released now", "createdAt": stamp}]}, fh)

    made = subprocess.run([sys.executable, PLAN, "--repo", repo, "--prs-json", prs_file],
                          capture_output=True, check=False, text=True)
    if made.returncode != 0:
        sys.exit(f"clean-git-plan failed: {made.stderr}")
    plan = json.loads(made.stdout)
    # A row the person confirmed that no longer matches what the repository
    # shows: the executor must re-read it and leave it alone.
    plan[0]["local"].append({"branch": "unmerged", "status": "stale", "action": "delete-d"})
    plan_file = os.path.join(root, "plan.json")
    with open(plan_file, "w", encoding="utf-8") as fh:
        json.dump(plan, fh)
    trees = {os.path.basename(r["path"]): r["action"] for r in plan[0]["worktrees"]}
    check("fixture: the dead worktree is planned for removal", trees.get("wt-dead"), "remove")

    def execute(*extra):
        r = subprocess.run([sys.executable, EXECUTE, "--plan", plan_file, "--prs-json", prs_file,
                            "--comments-json", comments_file, "--user", "t", *extra],
                           capture_output=True, check=False, text=True)
        if r.returncode != 0:
            sys.exit(f"clean-git-execute failed: {r.stdout}{r.stderr}")
        return json.loads(r.stdout)["repos"][0]

    before = branches(repo, "refs/heads") | branches(repo, "refs/remotes")
    dry = execute()
    check("a dry run changes nothing",
          branches(repo, "refs/heads") | branches(repo, "refs/remotes"), before)
    check("a dry run still lists what it would do", bool(dry["done"]), True)

    report = execute("--execute")
    kept = {(k["kind"], k["name"]): k["why"] for k in report["kept"]}
    local = branches(repo, "refs/heads")
    remote = branches(origin, "refs/heads")
    check("dead worktree removed", os.path.isdir(dead), False)
    check("its branch deleted inline", "wt-dead" in local, False)
    check("0-ahead local deleted", "zero-ahead" in local, False)
    check("0-ahead remote deleted with no PR to scope it", "zero-ahead" in remote, False)
    check("landed local deleted (a released claim is no claim)", "landed" in local, False)
    check("in-scope landed remote deleted", "landed" in remote, False)
    check("out-of-scope local still deleted locally", "landed-other" in local, False)
    check("out-of-scope remote kept", "landed-other" in remote, True)
    check("out-of-scope remote says why",
          "out of scope" in kept.get(("remote", "landed-other"), ""), True)
    check("claimed local kept", "claimed" in local, True)
    check("claimed remote kept", "claimed" in remote, True)
    check("claimed row says why", "claim comment" in kept.get(("local", "claimed"), ""), True)
    check("a row that changed since the plan is kept", "unmerged" in local, True)
    check("the changed row says what it is now", kept.get(("local", "unmerged")), "now flag")

spec = importlib.util.spec_from_file_location("clean_git_execute", EXECUTE)
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)
check("a claim with no readable timestamp keeps the branch",
      executor.claimed([{"body": "hold off please", "createdAt": ""}], time.time()), True)
check("an old claim does not", executor.claimed(
    [{"body": "hold off please", "createdAt": OLD}], time.time()), False)

if FAILS:
    print("\n".join(FAILS))
    sys.exit(1)
print("clean-git-execute: all cases pass")
