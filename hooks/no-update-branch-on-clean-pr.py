#!/usr/bin/env python3
"""PreToolUse deny: do not merge the base into a PR that is already fully clean.

ai-config#5093. On 2026-11-07 ids#47 lost its Clean verdict at head 98ed862a
when main was merged into it. Merging main into a PR branch is always allowed
(shared/workflow/sync-with-main.md), but on a PR that already passed
`check-pr-fully-clean.py` the merge moves the head, so the Clean review and the
checker pass stop applying and the PR needs a new review round.

Denies `mcp__github__update_pull_request_branch`, and a Bash command running
`gh pr update-branch <N>` or naming `repos/<o>/<r>/pulls/<N>/update-branch`
(the `gh api` form), when the transcript holds the checker's line
`<owner>/<repo>#<N> is FULLY CLEAN on HEAD <sha8>! [stale-base rule]` for that
PR and no later checker report that the branch needs the base. Those reports
are the cases where updating is required: base drift that added a CI gate the
head never ran ("<base> gained N commit(s) since this head's merge base",
ai-config#2982), a conflict (`mergeable_state 'dirty'`), or a base that requires
an up-to-date branch (`mergeable_state 'behind'`). Drift that is only other
PRs' content is not one of them: Ezra decided on 2026-11-14 that such a PR
merges on its current head (ai-config#5675). A PR with no clean line in the
transcript is untouched, so syncing a not-yet-clean PR stays free.

Not covered: `git merge origin/main` followed by `git push`, since the push
names no PR number to match against a clean line; the prose rule in
shared/workflow/fully-clean.md carries that path.

The clean line is searched in the whole transcript text, not only in trusted
tool results (block-merge-without-clean-checker.py does that stricter parse for
merges): a deny here costs one message, so the broader match errs the safe way.
Fails open on any parse trouble, including an unreadable transcript.
"""
import json
import re
import subprocess
import sys

TOOL = "mcp__github__update_pull_request_branch"
# Only a line carrying the "[stale-base rule]" marker counts: a checker older
# than ai-config#5144 prints the same line without it and also lacks the
# stale-base rule, so trusting it refused a main merge on a stale head (lds#2208).
CLEAN = re.compile(
    r"([\w.-]+/[\w.-]+)#(\d+) is FULLY CLEAN on HEAD ([0-9a-f]{7,40})!? \[stale-base rule\]")
# A checker report that the branch needs the base: base drift that added a
# CI gate (or hit the compare cap), a conflict, or a base that requires an
# up-to-date branch (ai-config#5675).
DRIFT = re.compile(
    r"gained \d+ commit\(s\) since this head's merge base"
    r"|mergeable_state '(?:behind|dirty)'"
    r"|holds this PR as 'behind'")
HEADER = re.compile(r"fully-clean status for ([\w.-]+/[\w.-]+)#(\d+)")
API_PATH = re.compile(r"repos/([\w.-]+)/([\w.-]+)/pulls/(\d+)/update-branch\b")
GH_PR = re.compile(r"\bgh\s+pr\s+update-branch\b([^;&|\n]*)")
NUMBER = re.compile(r"(?:^|\s)#?(\d+)(?=\s|$)")
REPO_FLAG = re.compile(r"(?:-R|--repo)[\s=]+([\w.-]+/[\w.-]+)")
REMOTE = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$")

REASON = """\
[hook: no-update-branch-on-clean-pr] {repo}#{num} is already fully clean on \
HEAD {sha} in this session, and merging the base into it moves the head, so \
the Clean review and the checker pass stop applying (ai-config#5093; ids#47 \
lost its Clean verdict this way on 2026-11-07).
A base that moved only by other PRs' content is not a reason to update: \
merge from the clean head (ai-config#5675). If the base gained a CI gate this \
head never ran, the PR now conflicts, or the base requires an up-to-date \
branch, rerun check-pr-fully-clean.py: its report of that lifts this denial."""


def last_clean(text, repo, num):
    """(position, sha) of the last FULLY CLEAN line for the PR, or None."""
    found = None
    for m in CLEAN.finditer(text):
        if m.group(1).lower() == repo and m.group(2) == num:
            found = (m.start(), m.group(3))
    return found


def drift_after(text, repo, num, after):
    """True when a needs-the-base report for THIS PR follows position *after*.

    The report names no PR, so it is attributed to the checker run whose
    header ("Checking ARDI / fully-clean status for <repo>#<N>...") most
    recently precedes it, and that header must itself come after position
    *after* (the clean line): a report under another PR's header, under none, or
    under this PR's earlier clean-run header does not count (review of
    ai-config#5094, #5095).
    """
    headers = [(m.start(), m.group(1).lower(), m.group(2))
               for m in HEADER.finditer(text) if m.start() > after]
    for d in DRIFT.finditer(text):
        if d.start() <= after:
            continue
        owner = [h for h in headers if h[0] < d.start()]
        if owner and owner[-1][1:] == (repo, num):
            return True
    return False


def origin_repo(cwd):
    """owner/name of the origin remote in *cwd*, or None."""
    if not isinstance(cwd, str):
        return None
    try:
        url = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    m = REMOTE.search(url)
    return m.group(1) if m else None


def target_of(tool, tool_input, cwd):
    """(owner, name, number) the update call names, or None when it names none.

    The MCP tool names all three. A Bash command counts when it runs
    `gh pr update-branch <N>` (repo from `-R`/`--repo`, else the origin remote
    of the working directory) or any command naming
    `repos/<owner>/<name>/pulls/<N>/update-branch` (the `gh api` form).
    A `gh pr update-branch` with no number acts on the current branch's PR,
    which the command does not name, so it is left alone (fails open).
    """
    if tool == TOOL:
        owner, name = tool_input.get("owner"), tool_input.get("repo")
        num = tool_input.get("pullNumber")
        if isinstance(owner, str) and isinstance(name, str) and num is not None:
            return owner, name, str(num)
        return None
    if tool != "Bash" or not isinstance(tool_input.get("command"), str):
        return None
    cmd = tool_input["command"]
    m = API_PATH.search(cmd)
    if m:
        return m.group(1), m.group(2), m.group(3)
    m = GH_PR.search(cmd)
    if not m:
        return None
    rest = m.group(1)
    num = NUMBER.search(rest)
    if not num:
        return None
    flag = REPO_FLAG.search(rest)
    full = flag.group(1) if flag else origin_repo(cwd)
    if not full or "/" not in full:
        return None
    owner, name = full.split("/", 1)
    return owner, name, num.group(1)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    target = target_of(payload.get("tool_name"), tool_input, payload.get("cwd"))
    if target is None:
        return 0
    owner, name, num = target
    repo = f"{owner}/{name}".lower()
    try:
        with open(payload.get("transcript_path"), encoding="utf-8", errors="replace") as f:
            text = f.read()
    except (OSError, TypeError, ValueError):
        return 0
    clean = last_clean(text, repo, num)
    if clean is None:
        return 0
    if drift_after(text, repo, num, clean[0]):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(repo=f"{owner}/{name}", num=num, sha=clean[1]),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
