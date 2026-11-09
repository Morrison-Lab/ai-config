#!/usr/bin/env python3
"""PreToolUse deny: do not merge the base into a PR that is already fully clean.

ai-config#5093. On 2026-11-07 ids#47 lost its Clean verdict at head 98ed862a
when main was merged into it. Merging main into a PR branch is always allowed
(shared/workflow/sync-with-main.md), but on a PR that already passed
`check-pr-fully-clean.py` the merge moves the head, so the Clean review and the
checker pass stop applying and the PR needs a new review round.

Denies `mcp__github__update_pull_request_branch` when the transcript holds the
checker's line `<owner>/<repo>#<N> is FULLY CLEAN on HEAD <sha8>! [stale-base rule]` for that PR
and no later base-drift report from the checker. The checker prints the drift
report ("<base> gained N commit(s) since this head's merge base") when the base
gained a CI gate the head never ran, which is the case where merging the base
is required (ai-config#2982). A PR with no clean line in the transcript is
untouched, so syncing a not-yet-clean PR stays free.

The clean line is searched in the whole transcript text, not only in trusted
tool results (block-merge-without-clean-checker.py does that stricter parse for
merges): a deny here costs one message, so the broader match errs the safe way.
Fails open on any parse trouble, including an unreadable transcript.
"""
import json
import re
import sys

TOOL = "mcp__github__update_pull_request_branch"
# Only a line carrying the "[stale-base rule]" marker counts: a checker older
# than ai-config#5144 prints the same line without it and also lacks the
# stale-base rule, so trusting it refused a main merge on a stale head (lds#2208).
CLEAN = re.compile(
    r"([\w.-]+/[\w.-]+)#(\d+) is FULLY CLEAN on HEAD ([0-9a-f]{7,40})!? \[stale-base rule\]")
DRIFT = re.compile(r"gained \d+ commit\(s\) since this head's merge base")
HEADER = re.compile(r"fully-clean status for ([\w.-]+/[\w.-]+)#(\d+)")

REASON = """\
[hook: no-update-branch-on-clean-pr] {repo}#{num} is already fully clean on \
HEAD {sha} in this session, and merging the base into it moves the head, so \
the Clean review and the checker pass stop applying (ai-config#5093; ids#47 \
lost its Clean verdict this way on 2026-11-07).
Leave the branch as it is and let the merge happen from the clean head. If the \
base gained a CI gate this head never ran, run check-pr-fully-clean.py: its \
base-drift report ("gained N commit(s) since this head's merge base") lifts \
this denial."""


def last_clean(text, repo, num):
    """(position, sha) of the last FULLY CLEAN line for the PR, or None."""
    found = None
    for m in CLEAN.finditer(text):
        if m.group(1).lower() == repo and m.group(2) == num:
            found = (m.start(), m.group(3))
    return found


def drift_after(text, repo, num, after):
    """True when a base-drift report for THIS PR follows position *after*.

    The drift message names no PR, so it is attributed to the checker run whose
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != TOOL:
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    owner, name = tool_input.get("owner"), tool_input.get("repo")
    num = tool_input.get("pullNumber")
    if not (isinstance(owner, str) and isinstance(name, str) and num is not None):
        return 0
    repo, num = f"{owner}/{name}".lower(), str(num)
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
