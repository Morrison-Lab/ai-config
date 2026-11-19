#!/usr/bin/env python3
"""Read-only dry-run classifier for `clean-git` (ai-config#4170).

Prints a JSON plan of a repository's (or each child repository's) worktrees,
local and remote branches, with a `status` and an `action` per row, by the
rules of `skills/clean-worktrees` and `skills/clean-branches`. It changes
nothing; run `git fetch --prune` first, after saving a ref snapshot.
Actions: `skip`, `flag` (a person decides), `prune` (stale worktree record),
`remove` (worktree), `delete-d`/`delete-D` (local) and `delete` (remote).
A branch an open PR comes from or targets is always `skip` (#3515).
Claim comments are not checked; `notes` says so.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

WEEK = 7 * 86400
LIVE = 600  # a worktree directory touched this recently may have a live owner
KEEP = {"main", "master", "HEAD", "develop", "gh-pages"}


def git(repo, *args):
    """stdout of `git -C repo args`, stripped, or None when git fails."""
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, check=False,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else None


def load_prs(repo, prs_json, limit):
    """Every PR of the repository, from a file or from `gh pr list`."""
    if prs_json:
        with open(prs_json, encoding="utf-8") as fh:
            return json.load(fh)
    url = git(repo, "remote", "get-url", "origin") or ""
    slug = "/".join(url.removesuffix(".git").replace(":", "/").split("/")[-2:])
    r = subprocess.run(
        ["gh", "pr", "list", "-R", slug, "--state", "all", "--limit", str(limit),
         "--json", "number,headRefName,baseRefName,state,mergedAt,author"],
        capture_output=True, check=False, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"clean-git-plan: gh pr list failed for {slug}: {r.stderr.strip()}")
    prs = json.loads(r.stdout)
    if len(prs) >= limit:  # a truncated list would mark live branches as PR-less
        sys.exit(f"clean-git-plan: {slug} returned {len(prs)} PRs, the --limit; raise it")
    return prs


class Repo:
    def __init__(self, path, prs, main, now):
        self.path, self.main, self.now = path, main, now
        self.heads, self.merged = {}, {}
        self.open = set()
        for p in prs:
            if p["state"] == "OPEN":
                self.open.update({p["headRefName"], p["baseRefName"]})
            elif p["state"] == "MERGED":
                self.merged.setdefault(p["headRefName"], []).append(p)
            self.heads.setdefault(p["headRefName"], []).append(p)

    def ahead(self, ref):
        n = git(self.path, "rev-list", "--count", f"{self.main}..{ref}")
        return None if n is None else int(n)

    def tip_time(self, ref):
        """Commit time of the ref's tip, or None when git cannot read it."""
        t = git(self.path, "log", "-1", "--format=%ct", ref)
        return int(t) if t else None

    def merged_pr(self, branch, ref):
        """(number, tip predates the merge) for the branch's last merged PR.
        An unreadable tip counts as not predating it, so the row is flagged."""
        done = sorted(self.merged.get(branch, []), key=lambda p: p["mergedAt"])
        if not done:
            return None
        at = datetime.fromisoformat(done[-1]["mergedAt"].replace("Z", "+00:00"))
        tip = self.tip_time(ref)
        return done[-1]["number"], tip is not None and tip < at.timestamp()

    def branch(self, name, ref, local):
        """(status, action) for a branch, local or remote."""
        if name in self.open:
            return "Active (an open PR comes from or targets it)", "skip"
        ahead = self.ahead(ref)
        landed = self.merged_pr(name, ref)
        if landed and landed[1]:
            return f"Dead (PR #{landed[0]} merged, tip predates it)", (
                "delete-D" if local else "delete")
        if landed:
            return f"Inspect (PR #{landed[0]} merged, tip after it)", "flag"
        if ahead == 0:
            tip = self.tip_time(ref)
            young = tip is None or self.now - tip < WEEK  # unreadable: keep it
            if local:
                return "Merged into main", "delete-d"
            return ("New (0 ahead, <7d)", "skip") if young else ("Dead (0 ahead)", "delete")
        closed = [p["number"] for p in self.heads.get(name, []) if p["state"] == "CLOSED"]
        if closed:
            return f"Closed-unmerged PR #{closed[-1]} ({ahead} ahead)", "flag"
        return f"Unmerged ({ahead} ahead, no PR)", "flag"

    def worktrees(self):
        rows, cur = [], {}
        for line in (git(self.path, "worktree", "list", "--porcelain") or "").splitlines() + [""]:
            if line:
                key, _, val = line.partition(" ")
                cur[key] = val or True
                continue
            if cur:
                rows.append(cur)
            cur = {}
        return rows[1:]  # the first is the main worktree

    def classify_worktree(self, w):
        path = w["worktree"]
        name = str(w.get("branch", "")).removeprefix("refs/heads/") or None
        row = {"path": path, "branch": name}
        if not os.path.isdir(path):
            return {**row, "status": "Missing dir", "action": "prune"}
        if w.get("locked"):
            return {**row, "status": "Locked", "action": "skip"}
        status = git(path, "status", "--porcelain")
        if status is None:  # dirtiness unknown, so never plan its removal
            return {**row, "status": "git status failed", "action": "flag"}
        if status:
            return {**row, "status": "Dirty (uncommitted)", "action": "flag"}
        if self.now - os.stat(path).st_mtime < LIVE:
            return {**row, "status": "Live? (touched <10 min ago)", "action": "skip"}
        if name is None:
            ahead = self.ahead(w["HEAD"])
            return {**row, **({"status": "Dead (detached, 0 ahead)", "action": "remove"}
                              if ahead == 0 else
                              {"status": f"Detached, {ahead} ahead", "action": "flag"})}
        if git(self.path, "rev-parse", "-q", "--verify", f"{name}@{{upstream}}") is None:
            unpushed = self.ahead(name)
        else:
            unpushed = int(git(self.path, "rev-list", "--count", f"{name}@{{upstream}}..{name}") or 0)
        status, action = self.branch(name, name, local=True)
        if action.startswith("delete") and unpushed and name not in self.merged:
            return {**row, "status": f"{unpushed} unpushed", "action": "flag"}
        return {**row, "status": status,
                "action": "remove" if action.startswith("delete") else action}

    def plan(self):
        worktrees = [self.classify_worktree(w) for w in self.worktrees()]
        held = {w["branch"] for w in worktrees if w["action"] != "remove"}
        current = git(self.path, "branch", "--show-current")
        local = []
        for name in (git(self.path, "for-each-ref", "--format=%(refname:short)",
                         "refs/heads") or "").splitlines():
            if name in KEEP or name == current or name in held:
                continue
            status, action = self.branch(name, name, local=True)
            local.append({"branch": name, "status": status, "action": action})
        remote = []
        for ref in (git(self.path, "for-each-ref", "--format=%(refname:short)",
                        "refs/remotes/origin") or "").splitlines():
            name = ref.removeprefix("origin/")
            if name in KEEP or ref == "origin":
                continue
            status, action = self.branch(name, ref, local=False)
            remote.append({"branch": name, "status": status, "action": action})
        return {"repo": self.path, "worktrees": worktrees, "local": local,
                "remote": remote, "notes": ["claim comments not checked"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--prs-json", help="PR list JSON instead of calling gh")
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--main", default="origin/main")
    args = ap.parse_args()
    root = os.path.abspath(args.repo)
    repos = [root] if git(root, "rev-parse", "--git-dir") else sorted(
        os.path.join(root, d) for d in os.listdir(root)
        if os.path.isdir(os.path.join(root, d, ".git")))  # a worktree's .git is a file
    if not repos:
        sys.exit(f"clean-git-plan: no git repository at or under {root}")
    if args.prs_json and len(repos) > 1:  # one PR list cannot describe two repositories
        sys.exit(f"clean-git-plan: --prs-json names one repository's PRs; {root} holds {len(repos)}")
    now = time.time()
    plans = [Repo(r, load_prs(r, args.prs_json, args.limit), args.main, now).plan()
             for r in repos]
    json.dump(plans, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
