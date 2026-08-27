#!/usr/bin/env python3
"""PreToolUse guard: `gh pr merge --delete-branch` on the base of an open PR.

## The incident

`ucdavis/bcs`#750 was stacked on #749, which is the ordinary shape for a
follow-up change: #750's `baseRefName` was #749's branch rather than `main`.
Merging the parent looked routine:

    gh pr merge 749 -R ucdavis/bcs --squash --delete-branch

The merge succeeded. The `--delete-branch` then removed
`docs/extract-shared-safety-policy-711`, which was **#750's base**, and GitHub
closes a pull request whose base branch is deleted. #750 went to `CLOSED`
rather than being retargeted to `main`.

The retarget is what everyone expects to happen, and it usually does --- GitHub
moves a stacked child onto the parent's base when the parent merges. It did not
save this one, because the deletion landed in the same operation as the merge.
So the flag turned a routine stacked merge into a closed PR, silently: `gh`
reported the merge as successful and said nothing about the child.

## Why the recovery deserves naming

The obvious recovery deadlocks, and both halves refuse for the same reason:

    retarget the closed PR  ->  Cannot change the base branch of a closed
                                pull request
    reopen it               ->  Could not open the pull request
                                (its base branch no longer exists)

Neither can go first. The way through is to push the deleted base branch back,
reopen, retarget to the real base, then delete the branch again --- which works
only while a copy of the branch still exists somewhere. Recreating it from a
local checkout is the usual route; if no copy survives, the PR cannot be
reopened at all and has to be raised again from scratch, losing its review
history.

## Why a hook rather than a rule

Nothing about the command looks wrong. `--delete-branch` is the tidy habit on
every *unstacked* merge, which is almost all of them, so it is muscle memory by
the time a stacked pair shows up. The stacking is a property of a *different*
PR, invisible at the point of typing, and `gh` gives no warning either before
or after.

The condition is decidable, which is what makes this a guard rather than a
reminder: a PR's base branch is a queryable field, so "does any open PR use
this branch as its base" has an exact answer before the merge runs.

## What it does

Warns, never blocks. Deleting a branch is recoverable while a copy survives,
and the query needs the network, so a hard block would fail closed whenever
`gh` is unavailable or slow --- turning a tidy-up flag into an outage. The
warning names the child PRs and the safe order.

Exit 0 always. Anything unexpected (no `gh`, no network, unparsable command)
stays silent rather than guessing.
"""
import json
import os
import re
import shutil
import subprocess
import sys

# `gh pr merge <n>` with --delete-branch (or -d) somewhere in the same command.
MERGE_RE = re.compile(r"\bgh\s+pr\s+merge\b")
DELETE_RE = re.compile(r"(?:^|\s)(?:--delete-branch|-d)(?:\s|$|=)")
PR_NUM_RE = re.compile(r"\bgh\s+pr\s+merge\s+(?:[^\s]+\s+)*?(\d+)\b")
REPO_RE = re.compile(r"(?:-R|--repo)[=\s]+([^\s'\"]+/[^\s'\"]+)")


def find_child_prs(repo, branch):
    """Open PRs whose base is `branch`. None means 'could not determine'."""
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "-R", repo, "--base", branch,
             "--state", "open", "--json", "number,title"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout or "[]")
    except json.JSONDecodeError:
        return None


def head_branch_of(repo, number):
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(number), "-R", repo,
             "--json", "headRefName", "--jq", ".headRefName"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    branch = out.stdout.strip()
    return branch or None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""

    if not MERGE_RE.search(command) or not DELETE_RE.search(command):
        return 0

    # A repo is required by a sibling guard, so it is normally present. Without
    # it the query target is ambiguous and the check stays silent.
    repo_match = REPO_RE.search(command)
    num_match = PR_NUM_RE.search(command)
    if not repo_match or not num_match:
        return 0

    repo = repo_match.group(1)
    number = num_match.group(1)

    if not shutil.which("gh"):
        return 0

    branch = head_branch_of(repo, number)
    if not branch:
        return 0

    children = find_child_prs(repo, branch)
    if not children:
        # Empty list: nothing is stacked, so the flag is safe. None: the query
        # failed, and guessing either way is worse than silence.
        return 0

    listed = ", ".join(f"#{c['number']}" for c in children)
    plural = len(children) > 1
    note = (
        f"`--delete-branch` here will CLOSE {listed}, not retarget "
        f"{'them' if plural else 'it'}.\n\n"
        f"    {repo}#{number} merges `{branch}`\n"
        f"    {listed} {'use' if plural else 'uses'} `{branch}` as "
        f"{'their' if plural else 'its'} base\n\n"
        "GitHub closes a pull request whose base branch is deleted. The "
        "retarget-on-merge you are expecting does not happen when the deletion "
        "lands in the same operation, and `gh` reports the merge as successful "
        "without mentioning the child.\n\n"
        "Recovering is worse than avoiding: a closed PR cannot be retargeted "
        "and cannot be reopened while its base branch is gone, so the only way "
        "out is to push the deleted branch back, reopen, retarget, and delete "
        "it again -- possible only while a copy of the branch still exists.\n\n"
        "Merge without `--delete-branch`, retarget the child, then delete:\n\n"
        f"    gh pr merge {number} -R {repo} --squash\n"
        f"    gh pr edit <child> -R {repo} --base <the parent's base>\n"
        f"    git push origin --delete {branch}\n\n"
        "This is a warning, not a refusal: proceed if you mean to."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
        "systemMessage": (
            f"--delete-branch would close {listed}, which "
            f"{'use' if plural else 'uses'} `{branch}` as a base."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
