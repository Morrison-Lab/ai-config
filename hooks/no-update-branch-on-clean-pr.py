#!/usr/bin/env python3
"""PreToolUse deny: do not merge the base into a PR that is already fully clean.

ai-config#5093. On 2026-11-07 ids#47 lost its Clean verdict at head 98ed862a
when main was merged into it. Merging main into a PR branch is always allowed
(shared/workflow/sync-with-main.md), but on a PR that already passed
`check-pr-fully-clean.py` the merge moves the head, so the Clean review and the
checker pass stop applying and the PR needs a new review round.

Denies `mcp__github__update_pull_request_branch`, and a Bash command running
`gh api` on `repos/<o>/<r>/pulls/<N>/update-branch` or `gh pr update-branch`,
when the transcript holds the checker's line
`<owner>/<repo>#<N> is FULLY CLEAN on HEAD <sha8>! [stale-base rule]` for that
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
prefixes, shell keywords and wrappers (`env`, `sudo -u x`, `timeout 5`), and
either its first argument is `api` and one whole argument is the path, or
its first two are `pr update-branch` and it names the PR. A PR URL names
repository and number; a number takes the repository from `-R`/`--repo`, a
`GH_REPO=` prefix or earlier `export`, or else the origin remote of the
working directory. So a commit message, a comment, or a body passed to
another command that quotes either form is not denied.

Not covered, so these fail open and the prose rule in
shared/workflow/fully-clean.md carries them:
- `git merge origin/main` followed by `git push`, since the push names no PR
  number to match against a clean line;
- a `gh api` path built from shell variables (`repos/$REPO/pulls/$N/...`),
  whose values the hook cannot read;
- a `gh pr update-branch` given a branch name or no PR, or given a bare
  number after a `cd` or inside a `bash -c` string, since the PR or the
  directory its repository comes from is then unknown;
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
import subprocess
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
# A wrapper's numeric argument, such as `timeout 5` or `nice -n 10`.
NUMBER = re.compile(r"\A\d+(?:\.\d+)?[smhd]?\Z")
# The PR argument of `gh pr update-branch`: a URL, or a number.
PR_URL = re.compile(r"\Ahttps?://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)(?:[/?#].*)?\Z")
PR_NUMBER = re.compile(r"\A#?(\d+)\Z")
# github.com remotes, and the cloud proxy form (http://...@127.0.0.1:N/git/<o>/<r>).
REMOTE = re.compile(r"(?:github\.com[:/]|/git/)([\w.-]+/[\w.-]+?)(?:\.git)?/?$")
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


def targets_of(tool, tool_input, cwd=None):
    """Every (owner, name, number) the update call names; empty when none.

    The MCP tool names all three. A Bash command counts when it runs `gh api`
    on `repos/<owner>/<name>/pulls/<N>/update-branch`, or
    `gh pr update-branch` on a PR it names (see `pr_update_target`).
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
    for depth, line in enumerate(shell_c_expansions(tool_input["command"])):
        # A nested `bash -c` shell starts in a directory the text cannot show,
        # and a `cd` moves the rest of the line, so neither resolves origin.
        where, repo_env = (cwd if depth == 0 else None), None
        for argv in simple_commands(line) or []:
            if argv[0] in ("cd", "pushd", "popd"):
                where = None
            if argv[0] == "export":
                repo_env = gh_repo(argv[1:]) or repo_env
            args = gh_args(argv)
            if args and args[0] == "api":
                found += [m.groups() for m in map(API_PATH.match, args[1:]) if m]
            elif args and args[:2] == ["pr", "update-branch"]:
                prefix = argv[:len(argv) - len(args)]
                target = pr_update_target(args[2:], gh_repo(prefix) or repo_env, where)
                found += [target] if target else []
    return found


def gh_repo(tokens):
    """The value of the last `GH_REPO=` assignment among *tokens*, or None."""
    values = [t.split("=", 1)[1] for t in tokens if t.startswith("GH_REPO=")]
    return values[-1] if values else None


def pr_update_target(rest, repo, cwd):
    """(owner, name, number) for `gh pr update-branch <rest>`, or None.

    The PR is the first positional argument: a URL names repository and
    number, and a number (`47`, `#47`) takes its repository from `-R`/`--repo`,
    else *repo* (a `GH_REPO` prefix or an earlier `export`), else the origin
    remote of *cwd*. A branch name or no argument names no PR the text can
    match, so it is left alone (fails open), as is a number whose repository
    is unknown.
    """
    pr = None
    for i, tok in enumerate(rest):
        if tok in ("-R", "--repo"):
            repo = rest[i + 1] if i + 1 < len(rest) else None
        elif tok.startswith("--repo="):
            repo = tok.split("=", 1)[1]
        elif tok.startswith("-R"):
            repo = tok[2:].lstrip("=")
        elif pr is None and not tok.startswith("-") and rest[i - 1:i] not in (["-R"], ["--repo"]):
            pr = tok
    url = PR_URL.match(pr or "")
    if url:
        return url.groups()
    num = PR_NUMBER.match(pr or "")
    if not num:
        return None
    parts = (repo or origin_repo(cwd) or "").split("/")[-2:]
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0], parts[1], num.group(1)


def origin_repo(cwd):
    """owner/name of the origin remote of *cwd*, or None."""
    if not isinstance(cwd, str):
        return None
    try:
        url = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    m = REMOTE.search(url)
    return m.group(1) if m else None


def gh_args(argv):
    """The arguments after `gh` when `gh` is the program of *argv*, else None.

    Assignments and shell keywords before it are skipped, and so is a
    wrapper's own arguments within shellcmd's look-ahead window, counted from
    the wrapper: an option, the value after an option (`sudo -u x`), an
    assignment (`env A=1`) or a number (`timeout 5`). Any other word after a
    wrapper is the program it runs (`time echo gh ...` runs `echo`), so the
    command is not a `gh` call. A value-less option before such a program
    (`sudo -E echo gh ...`) is read as taking that word as its value, which
    errs toward a denial.
    """
    wrapper_at, after_option = None, False
    for i, tok in enumerate(argv):
        name = os.path.basename(tok)
        if name == "gh":
            return argv[i + 1:]
        if name in COMMAND_WRAPPERS:
            wrapper_at, after_option = i, False
        elif wrapper_at is None:
            if not (ENV_ASSIGNMENT.match(tok) or tok in SHELL_KEYWORDS):
                return None
        elif i - wrapper_at > WRAPPER_ARG_WINDOW:
            return None
        elif tok.startswith("-"):
            after_option = "=" not in tok
        elif after_option or ENV_ASSIGNMENT.match(tok) or NUMBER.match(tok):
            after_option = False
        else:
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
    targets = targets_of(payload.get("tool_name"), tool_input, payload.get("cwd"))
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
