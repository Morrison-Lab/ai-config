#!/usr/bin/env python3
"""PreToolUse deny: do not merge the base into a PR that is already fully clean.

ai-config#5093. On 2026-11-07 ids#47 lost its Clean verdict at head 98ed862a
when main was merged into it. Merging main into a PR branch is always allowed
(shared/workflow/sync-with-main.md), but on a PR that already passed
`check-pr-fully-clean.py` the merge moves the head, so the Clean review and the
checker pass stop applying and the PR needs a new review round.

Denies `mcp__github__update_pull_request_branch`, and a Bash command running
`gh api` on `repos/<o>/<r>/pulls/<N>/update-branch`, when the transcript holds
the checker's line `<owner>/<repo>#<N> is FULLY CLEAN on HEAD <sha8>! [stale-base rule]` for that
PR and no later checker report that the branch needs the base. Those reports
are the cases where updating is required: base drift that added a CI gate the
head never ran ("<base> gained N commit(s) since this head's merge base",
ai-config#2982), a conflict (`mergeable_state 'dirty'`), or a base that requires
an up-to-date branch (`mergeable_state 'behind'`). Drift that is only other
PRs' content is not one of them: Ezra decided on 2026-11-14 that such a PR
merges on its current head (ai-config#5675). A PR with no clean line in the
transcript is untouched, so syncing a not-yet-clean PR stays free.

A Bash command is split into simple commands by scripts/lib/shellcmd.py, the
splitter the other command-parsing hooks share: it keeps each quoted string
as one argument, blanks heredoc bodies and `#` comments, and joins
backslash-continued lines, and `shell_c_expansions` follows a `bash -c`
string. A simple command counts when its program is `gh`, after `VAR=value`
prefixes, shell keywords and wrappers (`env`, `sudo -u x`, `timeout 5`), its
first argument is `api`, and one whole argument is the path. So a commit
message, a comment, or a body passed to another command that quotes the form
is not denied.

Not covered, so these fail open and the prose rule in
shared/workflow/fully-clean.md carries them:
- `git merge origin/main` followed by `git push`, since the push names no PR
  number to match against a clean line;
- a `gh api` path built from shell variables (`repos/$REPO/pulls/$N/...`),
  whose values the hook cannot read;
- `gh pr update-branch`, whose repository comes from the working directory;
  its form is the second half of ai-config#5677;
- the holes shellcmd.py's own docstring lists, such as `xargs`, `eval`, and
  a wrapper chain longer than its look-ahead window;
- a script a shell reads from a heredoc (`bash <<'EOF'`), since heredoc
  bodies are blanked so that a quoted commit message or note is not denied.

The clean line is searched in the whole transcript text, not only in trusted
tool results (block-merge-without-clean-checker.py does that stricter parse for
merges): a deny here costs one message, so the broader match errs the safe way.
Fails open on any parse trouble, including an unreadable transcript.
"""
import json
import os
import re
import sys

try:
    _LIB = os.path.join(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__))), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (COMMAND_WRAPPERS, ENV_ASSIGNMENT, SHELL_KEYWORDS,
                          WRAPPER_ARG_WINDOW, shell_c_expansions, simple_commands)
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-update-branch-on-clean-pr: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); no Bash command will be checked", file=sys.stderr)
    shell_c_expansions = None

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
# One whole argument of `gh api`; `?...` query parameters are allowed.
API_PATH = re.compile(r"/?repos/([\w.-]+)/([\w.-]+)/pulls/(\d+)/update-branch(?:\?.*)?\Z")

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


def targets_of(tool, tool_input):
    """Every (owner, name, number) the update call names; empty when none.

    The MCP tool names all three. A Bash command counts when it runs `gh api`
    on `repos/<owner>/<name>/pulls/<N>/update-branch`.
    A compound command is checked for every update it runs, not only the first.
    """
    if tool == TOOL:
        owner, name = tool_input.get("owner"), tool_input.get("repo")
        num = tool_input.get("pullNumber")
        if isinstance(owner, str) and isinstance(name, str) and num is not None:
            return [(owner, name, str(num))]
        return []
    if tool != "Bash" or not isinstance(tool_input.get("command"), str):
        return []
    if shell_c_expansions is None:
        return []
    found = []
    for line in shell_c_expansions(tool_input["command"]):
        for argv in simple_commands(line) or []:
            args = gh_args(argv)
            if args and args[0] == "api":
                found += [m.groups() for m in map(API_PATH.match, args[1:]) if m]
    return found


def gh_args(argv):
    """The arguments after `gh` when `gh` is the program of *argv*, else None.

    Assignments, shell keywords and wrappers before it are skipped, and a
    wrapper's own arguments (`sudo -u x`, `timeout 5`) within shellcmd's
    look-ahead window.
    """
    after_wrapper = False
    for i, tok in enumerate(argv):
        if os.path.basename(tok) == "gh":
            return argv[i + 1:]
        if ENV_ASSIGNMENT.match(tok) or tok in SHELL_KEYWORDS:
            after_wrapper = False
        elif os.path.basename(tok) in COMMAND_WRAPPERS:
            after_wrapper = True
        elif not after_wrapper or i > WRAPPER_ARG_WINDOW:
            return None
    return None


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
    targets = targets_of(payload.get("tool_name"), tool_input)
    if not targets:
        return 0
    try:
        with open(payload.get("transcript_path"), encoding="utf-8", errors="replace") as f:
            text = f.read()
    except (OSError, TypeError, ValueError):
        return 0
    for owner, name, num in targets:
        repo = f"{owner}/{name}".lower()
        clean = last_clean(text, repo, num)
        if clean is not None and not drift_after(text, repo, num, clean[0]):
            break
    else:
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
