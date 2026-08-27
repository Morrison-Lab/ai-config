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

Retargeting is the **documented** behaviour, which is what makes this worth a
guard rather than a note. GitHub's own docs say that deleting a head branch
after its pull request is merged causes it to find open PRs using that branch
as a base and move them to the merged PR's base. So the expectation is
correct, and the observed close is a *failure of a documented feature* rather
than the rule.

Why it failed here is unknown, and this guard does not claim to know: the
timeline shows `base_ref_deleted` and `closed` at the same second, and
community reports of the same shape exist with no established cause. What is
certain is the consequence --- `gh` reported the merge as successful and said
nothing about the child, so the close is silent whatever triggered it. The
guard therefore warns that the flag **may** close a stacked child, not that
it will.

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

## The match condition

Warns when **all** of these hold for one `gh pr merge` or `gh pr close`
simple command --- both carry the same `-d, --delete-branch`, and it is the
branch deletion that is the hazard rather than the merge:

    the argv carries a delete flag  (--delete-branch, -d, a clustered -sd,
                                     or --delete-branch=<anything but false>)
    the argv names a repo           (-R / --repo, in any spelling, including
                                     -Rowner/repo with no separator)
    the argv names a PR target      (number, URL, or branch -- `gh pr view`
                                     resolves all three)
    `gh` is on PATH
    the PR's headRefName resolves
    at least one OPEN PR uses that branch as its base

Anything else is silence, including every failure mode: `gh` absent, the
network down, a non-zero exit, output that is not JSON, and output that is
valid JSON of an unexpected shape. Exit status is 0 in every one of those
cases --- the guard never blocks and never raises, because a `PreToolUse`
hook that raises is an outage on a tidy-up flag.
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

# `gh pr close` carries the SAME `-d, --delete-branch` flag as `gh pr merge`,
# and deleting the branch is the hazard -- not merging. A guard that watches
# only `merge` leaves the identical incident reachable one subcommand over.
DELETING_SUBCOMMANDS = {"merge", "close"}

# Flags whose NEXT token is a value, not the PR target. Without this,
# `gh pr merge -R o/r -t "Some title" 749 -d` reads "Some title" as the PR.
# The union across both subcommands, verified against `gh pr merge --help` and
# `gh pr close --help`. `-c/--comment` is close-only and was the gap that
# adding `close` support opened: its value was read as the PR target, so the
# guard went silent on exactly the command it was extended to cover.
VALUE_FLAGS = {
    "-R", "--repo", "-t", "--subject", "-b", "--body", "-F", "--body-file",
    "--match-head-commit", "-A", "--author-email", "-c", "--comment",
}


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


def _gh_pr_argv(argv):
    """The argv of a `gh pr merge`/`gh pr close`, or None.

    Skips env assignments and the usual leading words, so
    `ALLOW_MERGE=1 gh pr merge ...` still matches.
    """
    i = 0
    while i < len(argv) and (ASSIGNMENT.match(argv[i]) or argv[i] in LEAD_WORDS):
        i += 1
    rest = argv[i:]
    if (len(rest) >= 3 and rest[0] == "gh" and rest[1] == "pr"
            and rest[2] in DELETING_SUBCOMMANDS):
        return rest
    return None


def _parse_merge(argv):
    """(target, repo, deletes_branch) from one `gh pr merge`/`close` argv.

    `target` is whatever identifies the PR --- a number, a URL, or a branch
    name. `gh pr view` resolves all three, so the guard does not classify it.
    """
    deletes = False
    repo = None
    target = None
    i = 3
    while i < len(argv):
        tok = argv[i]
        if tok in DELETE_FLAGS:
            deletes = True
        elif tok.startswith("--delete-branch="):
            deletes = tok.split("=", 1)[1].strip().lower() not in ("false", "0", "no")
        elif tok in ("-R", "--repo"):
            i += 1
            if i < len(argv):
                repo = argv[i]
        elif tok in VALUE_FLAGS:
            i += 1  # skip the value
        elif tok.startswith("--repo="):
            repo = tok.split("=", 1)[1]
        elif tok.startswith("-R="):
            repo = tok.split("=", 1)[1]
        # `-Rowner/repo`, with neither space nor `=`. Valid pflag shorthand,
        # and it fails the clustered-flag test below because of the slash.
        elif tok.startswith("-R") and len(tok) > 2:
            repo = tok[2:]
        # Clustered boolean shorthand: `-sd` is `--squash --delete-branch`.
        # pflag accepts it, and a matcher that only knows the bare `-d` reads
        # a real delete as no delete.
        elif re.fullmatch(r"-[A-Za-z]{2,}", tok):
            if "d" in tok[1:]:
                deletes = True
        elif not tok.startswith("-") and target is None:
            target = tok
        i += 1
    return target, repo, deletes


def find_child_prs(repo, branch):
    """Numbers of open PRs whose base is `branch`. None means 'unknown'.

    The shape is validated rather than trusted: `gh` returning valid JSON that
    is not a list of objects carrying `number` is the difference between a
    silent guard and a traceback, and this hook's whole contract is that it
    never raises.
    """
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "-R", repo, "--base", branch,
             "--state", "open", "--json", "number"],
            capture_output=True, text=True, timeout=8,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    try:
        parsed = json.loads(out.stdout or "[]")
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(parsed, list):
        return None
    numbers = []
    for entry in parsed:
        if isinstance(entry, dict) and entry.get("number") is not None:
            numbers.append(entry["number"])
    return numbers


def head_branch_of(repo, target):
    try:
        out = subprocess.run(
            ["gh", "pr", "view", str(target), "-R", repo,
             "--json", "headRefName", "--jq", ".headRefName"],
            capture_output=True, text=True, timeout=8,
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
    target = repo = verb = None
    for argv in argvs:
        merge_argv = _gh_pr_argv(argv)
        if merge_argv is None:
            continue
        t, r, deletes = _parse_merge(merge_argv)
        if deletes and t and r:
            target, repo, verb = t, r, merge_argv[2]
            break
    if not target or not repo:
        return 0

    if not shutil.which("gh"):
        return 0

    branch = head_branch_of(repo, target)
    if not branch:
        return 0

    children = find_child_prs(repo, branch)
    if not children:
        # Empty list means nothing is stacked; None means the query failed or
        # came back in a shape this guard will not interpret. Both are silence,
        # so the two are deliberately not distinguished here.
        return 0

    listed = ", ".join(f"#{n}" for n in children)
    plural = len(children) > 1
    note = (
        f"`--delete-branch` here may CLOSE {listed} rather than retarget "
        f"{'them' if plural else 'it'}.\n\n"
        f"    {repo} PR {target} ({verb}) removes `{branch}`\n"
        f"    {listed} {'use' if plural else 'uses'} `{branch}` as "
        f"{'their' if plural else 'its'} base\n\n"
        "Retargeting onto the merged PR's base is GitHub's documented "
        "behaviour and usually happens. A measured case closed the child "
        "instead, for reasons nobody has established, and either way `gh` "
        "reports the merge as successful without mentioning the child.\n\n"
        "Recovering is worse than avoiding: a closed PR cannot be retargeted "
        "and cannot be reopened while its base branch is gone, so the only "
        "way out is to push the deleted branch back, reopen, retarget, and "
        "delete it again -- possible only while a copy of the branch still "
        "exists.\n\n"
        "Safer order: merge without `--delete-branch`, confirm where the "
        "child landed, then delete the branch.\n\n"
        f"    <your merge command, minus --delete-branch>\n"
        f"    gh pr edit <child> -R {repo} --base <the parent's base>\n"
        f"    gh api -X DELETE repos/{repo}/git/refs/heads/{branch}\n\n"
        "This is a warning, not a refusal: proceed if you mean to."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
        "systemMessage": (
            f"--delete-branch may close {listed}, which "
            f"{'use' if plural else 'uses'} `{branch}` as a base."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
