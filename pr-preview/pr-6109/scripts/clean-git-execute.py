#!/usr/bin/env python3
"""Carry out a confirmed `clean-git` plan (ai-config#4170).

Reads the JSON that `scripts/clean-git-plan.py` printed and the person
confirmed, and runs it: worktrees first, then local and remote branches, as
`skills/clean-git/SKILL.md` step 3 orders them. Without `--execute` it only
prints what it would do.

A confirmed plan is a prediction, so nothing in it is acted on unread. Before
each pass the repository is classified again, with the same code that made
the plan, and a row is acted on only when its fresh action is the one that
was confirmed. Anything that changed is reported and left alone.

Two checks the classifier does not make run here, on every branch about to
be deleted:

- A claim comment ("hold off", "paws off", "back off") from the last 24 hours
  on a PR from that branch keeps it (`skills/clean-branches/SKILL.md` step e).
- A remote branch is deleted only when it is 0 commits ahead of main, so
  deleting it loses nothing, or when every PR from it is in scope by
  `scripts/pr-scope.py`: opened by or assigned to the invoking user, or
  opened by the Actions app (AGENTS.md, "Only work PRs scoped to the user or
  Actions app"). An unresolved identity fails closed.

A failed worktree removal stops that repository's branch pass, since the
branch plan assumed the worktree pass succeeded. No worktree removal uses
`--force`. A local branch is force-deleted (`git branch -D`) only when its
fresh row is `delete-D`: a PR from it merged and its tip predates the merge,
so a squash or rebase merge left its commits unreachable from main.

Usage:
    python3 scripts/clean-git-plan.py --repo . > plan.json   # then confirm it
    python3 scripts/clean-git-execute.py --plan plan.json --user LOGIN [--execute]
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CLAIM = re.compile(r"hold off|paws off|back off", re.I)
RELEASE = re.compile(r"unclaim|released|PR is free|now mergeable", re.I)
CLAIM_WINDOW = 24 * 3600


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"),
                                                  os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plan_mod = load("clean-git-plan")
scope_mod = load("pr-scope")


def run(repo, args, execute):
    """Run `git -C repo args` when executing. (ok, message)."""
    if not execute:
        return True, "dry run"
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, check=False,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def gh_comments(slug, number):
    r = subprocess.run(["gh", "pr", "view", str(number), "-R", slug, "--json", "comments"],
                       capture_output=True, check=False, text=True, encoding="utf-8")
    if r.returncode != 0:
        return None
    return json.loads(r.stdout).get("comments", [])


def claimed(comments, now):
    """True when a comment within CLAIM_WINDOW claims the branch, or when the
    comments could not be read (None): an unknown claim keeps the branch."""
    if comments is None:
        return True
    for c in comments:
        body = c.get("body") or ""
        if not CLAIM.search(body) or RELEASE.search(body):
            continue
        try:
            at = datetime.fromisoformat(str(c.get("createdAt", "")).replace("Z", "+00:00"))
        except ValueError:
            return True  # a claim of unknown age keeps the branch
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if now - at.timestamp() < CLAIM_WINDOW:
            return True
    return False


class Executor:
    def __init__(self, path, prs, args, comments_for, now):
        self.path, self.prs, self.args, self.now = path, prs, args, now
        self.comments_for = comments_for
        self.ids = {scope_mod.normalize_login(i) for i in [args.user, *args.alias] if i}
        self.report = {"repo": path, "done": [], "kept": [], "failed": []}

    def fresh(self):
        return plan_mod.Repo(self.path, self.prs, self.args.main, self.now).plan()

    def keep(self, kind, name, why):
        self.report["kept"].append({"kind": kind, "name": name, "why": why})

    def act(self, kind, name, git_args):
        ok, msg = run(self.path, git_args, self.args.execute)
        entry = {"kind": kind, "name": name, "command": "git " + " ".join(git_args)}
        if ok:
            self.report["done"].append(entry)
        else:
            self.report["failed"].append({**entry, "error": msg})
        return ok

    def prs_from(self, branch):
        return [p for p in self.prs if p.get("headRefName") == branch]

    def blocked(self, branch, remote):
        """Why a branch must not be deleted, or None."""
        prs = self.prs_from(branch)
        for p in prs:
            if claimed(self.comments_for(p["number"]), self.now):
                return f"claim comment on PR #{p['number']} in the last 24 hours"
        if remote and not prs:
            # The plan deletes an ahead remote branch only when a PR from it
            # merged, so this does not happen; if it does, nothing scopes it.
            return "ahead of main, or ahead unknown, with no PR to scope it"
        if remote:
            for p in prs:
                pr = scope_mod.normalize_pr(p)
                ok, reason = scope_mod.classify(pr, self.ids, set(), set(), bool(self.ids))
                if not ok:
                    return f"PR #{p['number']} is out of scope ({reason})"
        return None

    def worktree_pass(self, confirmed):
        fresh = {w["path"]: w for w in self.fresh()["worktrees"]}
        wanted = [w for w in confirmed["worktrees"] if w["action"] in ("prune", "remove")]
        removed = []
        if any(w["action"] == "prune" for w in wanted):
            if all(fresh.get(w["path"], {}).get("action") == "prune"
                   for w in wanted if w["action"] == "prune"):
                self.act("worktree", "stale records", ["worktree", "prune"])
            else:
                self.keep("worktree", "stale records", "a record changed since the plan")
        for w in wanted:
            if w["action"] != "remove":
                continue
            now = fresh.get(w["path"], {}).get("action")
            if now != "remove":
                self.keep("worktree", w["path"], f"now {now or 'gone'}, was remove")
                continue
            if not self.act("worktree", w["path"], ["worktree", "remove", w["path"]]):
                return None  # the branch plan assumed this succeeded
            removed.append(w["branch"])
        return [b for b in removed if b]

    def branch_pass(self, confirmed, inline):
        fresh = self.fresh()
        local = {r["branch"]: r["action"] for r in fresh["local"]}
        remote = {r["branch"]: r["action"] for r in fresh["remote"]}
        targets = {r["branch"]: r["action"] for r in confirmed["local"]
                   if r["action"] in ("delete-d", "delete-D")}
        for branch in inline:  # the confirmed worktree row covered its branch
            targets.setdefault(branch, local.get(branch))
        for branch, action in targets.items():
            now = local.get(branch)
            if now not in ("delete-d", "delete-D") or (branch not in inline and now != action):
                self.keep("local", branch, f"now {now or 'gone'}"
                          + ("; survived both passes, needs a person" if branch in inline else ""))
                continue
            why = self.blocked(branch, remote=False)
            if why:
                self.keep("local", branch, why)
                continue
            self.act("local", branch, ["branch", "-d" if now == "delete-d" else "-D", branch])
        for row in confirmed["remote"]:
            branch = row["branch"]
            if row["action"] != "delete":
                continue
            if remote.get(branch) != "delete":
                self.keep("remote", branch, f"now {remote.get(branch) or 'gone'}, was delete")
                continue
            ahead = plan_mod.Repo(self.path, self.prs, self.args.main, self.now).ahead(
                "origin/" + branch)
            why = self.blocked(branch, remote=ahead != 0)
            if why:
                self.keep("remote", branch, why)
                continue
            self.act("remote", branch, ["push", "origin", "--delete", branch])

    def execute(self, confirmed):
        inline = self.worktree_pass(confirmed)
        if inline is None:
            self.keep("branches", "all", "a worktree removal failed, so the branch pass stopped")
        else:
            self.branch_pass(confirmed, inline)
        return self.report


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", required=True, help="the confirmed clean-git-plan.py JSON")
    ap.add_argument("--execute", action="store_true", help="act; without it, a dry run")
    ap.add_argument("--user", default="", help="the invoking user's login")
    ap.add_argument("--alias", action="append", default=[], help="another login of the user")
    ap.add_argument("--prs-json", help="PR list JSON instead of calling gh (one repository)")
    ap.add_argument("--comments-json", help="{PR number: comments} instead of calling gh")
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--main", default="origin/main")
    args = ap.parse_args()
    with open(args.plan, encoding="utf-8") as fh:
        plans = json.load(fh)
    if args.prs_json and len(plans) > 1:
        sys.exit("clean-git-execute: --prs-json names one repository's PRs")
    canned = None
    if args.comments_json:
        with open(args.comments_json, encoding="utf-8") as fh:
            canned = {int(k): v for k, v in json.load(fh).items()}
    now = time.time()
    reports = []
    for confirmed in plans:
        path = confirmed["repo"]
        prs = plan_mod.load_prs(path, args.prs_json, args.limit)
        url = plan_mod.git(path, "remote", "get-url", "origin") or ""
        slug = "/".join(url.removesuffix(".git").replace(":", "/").split("/")[-2:])

        def comments_for(number, slug=slug):
            return canned.get(number, []) if canned is not None else gh_comments(slug, number)

        reports.append(Executor(path, prs, args, comments_for, now).execute(confirmed))
    json.dump({"executed": args.execute, "repos": reports}, sys.stdout, indent=1)
    print()
    sys.exit(1 if any(r["failed"] for r in reports) else 0)


if __name__ == "__main__":
    main()
