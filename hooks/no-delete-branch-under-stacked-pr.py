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

## Matching one command, not the whole string

The first draft scanned the raw `command` string, and a review found it firing
on the most routine chain in this corpus --- `post-merge`'s own cleanup:

    gh pr merge 749 -R o/r --squash && git checkout main && git branch -d b

There is no `--delete-branch` there. The `-d` belongs to `git branch -d`, and
a whole-string scan cannot tell whose flag it is, so the guard warned on the
one sequence it should never touch. Six sibling `PreToolUse` hooks already
split with `shlex` for exactly this reason; this one now does too, and reads
flags off the `gh pr merge` argv alone.

## What it does

Warns, never blocks. Deleting a branch is recoverable while a copy survives,
and the query needs the network, so a hard block would fail closed whenever
`gh` is unavailable or slow --- turning a tidy-up flag into an outage. The
warning names the child PRs and the safe order.

Exit 0 always. Anything unexpected (no `gh`, no network, unparsable command)
stays silent rather than guessing.
"""
import json
import re
import shlex
import shutil
import subprocess
import sys

# Segmentation borrowed verbatim in construction from `no-clobbering-push.py`
# and `flag-reset-hard-uncommitted-work.py`. Matching the raw command string
# is what the first draft did, and it produced a false positive on the most
# routine sequence there is -- this repo's own `post-merge` cleanup:
#
#     gh pr merge 749 -R o/r --squash && git checkout main && git branch -d b
#
# There is no `--delete-branch` there at all. The `-d` belongs to the
# unrelated `git branch -d`, and a whole-string scan cannot tell the two
# apart, so the guard fired on the one chain it should never fire on.
RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEAD_WORDS = {"then", "do", "else", "!", "time", "sudo", "command", "exec"}
_SHELL_OPS = set("();|&")

DELETE_FLAGS = {"--delete-branch", "-d"}


def _simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error."""
    cmd = re.sub(r"\\\r?\n", " ", cmd)
    cmd = RX_HEREDOC.sub("<<", cmd)
    cmd = cmd.replace("\n", ";")
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _gh_pr_merge_argv(argv):
    """The argv of a `gh pr merge`, or None. Skips env assignments and the
    usual leading words, so `ALLOW_MERGE=1 gh pr merge ...` still matches."""
    i = 0
    while i < len(argv) and (ASSIGNMENT.match(argv[i]) or argv[i] in LEAD_WORDS):
        i += 1
    rest = argv[i:]
    if len(rest) >= 3 and rest[0] == "gh" and rest[1] == "pr" and rest[2] == "merge":
        return rest
    return None


def _parse_merge(argv):
    """(pr_number, repo, deletes_branch) from one `gh pr merge` argv.

    `pr_number` is None when the target is a URL or a branch name rather than
    a number -- the guard stays silent there rather than guessing, since the
    query needs a number.
    """
    deletes = False
    repo = None
    number = None
    i = 3
    while i < len(argv):
        tok = argv[i]
        if tok in DELETE_FLAGS or tok.startswith("--delete-branch="):
            if not tok.startswith("--delete-branch=") or \
                    tok.split("=", 1)[1].strip().lower() not in ("false", "0"):
                deletes = True
        elif tok in ("-R", "--repo"):
            i += 1
            if i < len(argv):
                repo = argv[i]
        elif tok.startswith("--repo="):
            repo = tok.split("=", 1)[1]
        elif tok.startswith("-R="):
            repo = tok.split("=", 1)[1]
        elif not tok.startswith("-") and number is None and tok.isdigit():
            number = tok
        i += 1
    return number, repo, deletes


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

    argvs = _simple_commands(command)
    if not argvs:
        return 0

    # Only the `gh pr merge` segments matter. A `git branch -d` elsewhere in
    # the same chain is somebody else's `-d`.
    number = repo = None
    for argv in argvs:
        merge_argv = _gh_pr_merge_argv(argv)
        if merge_argv is None:
            continue
        n, r, deletes = _parse_merge(merge_argv)
        if deletes and n and r:
            number, repo = n, r
            break
    if not number or not repo:
        return 0

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
