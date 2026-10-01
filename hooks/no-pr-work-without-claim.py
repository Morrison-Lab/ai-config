#!/usr/bin/env python3
"""PreToolUse guard: `git commit` / `git push` on a PR branch needs this session's claim.

## The gap this closes

On 2026-09-30 two agent sessions worked the same three PR branches at once and
neither posted a claim comment (ai-config#4155). A cloud session's "restore"
commit on PR #4134 left `memories/preferences.md` at 706 lines instead of 1177.
`shared/workflow/claim-pr.md` already says to claim before working; nothing
enforced it, and `ListAgents` cannot see a cloud session, so the local session
had no other way to find the peer. A rule is read at planning time and skipped
at commit time, so the check moves onto the commit itself.

## What it does

Matches a `git commit` or `git push` (over an argv split from
`scripts/lib/shellcmd.py`, so a quoted message or a heredoc body naming either
command cannot trip it; `--dry-run` is skipped, as is a `--delete` push).

When the checkout's branch has an OPEN PR in a Morrison-Lab repo it reads the
PR's issue comments and DENIES unless one is a claim from THIS session:

  * a claim is a comment carrying the agent marker (`Posted by Claude Code (AI
    agent)`) and the `hold off` (or legacy `paws off`) wording, per
    `skills/claim-pr/SKILL.md`;
  * it is THIS session's when its body contains the payload's `session_id` or
    this worktree's path. claim-pr's stock wording carries neither -- the
    forge login is shared by every session under one account, so the comment
    must say which session it is. The deny text gives the one-line addition.
  * a claim from a DIFFERENT session posted AFTER this session's latest claim
    is a takeover: DENY. (A newer claim that names no session at all is not
    attributable, so it only warns.)

Before a PUSH it also reads the forge activity endpoint
(`repos/<o>/<r>/activity?ref=refs/heads/<branch>`) and WARNS (never denies)
when a push since this session's claim landed a commit that is not an ancestor
of local HEAD: that is a push this session neither made nor merged, which is
what the 2026-09-30 collision looked like from the forge side.

## What it does not do

It cannot see the cloud half: hooks are inert in remote and web sessions
(ai-config#2004), so a cloud session is only covered by its own instructions or
a server-side check. This is the local half of #4155 only.

A claim's 2-hour expiry (claim-pr.md) is not evaluated. An own claim is
accepted whatever its age; staleness over-approximation via `updatedAt` would
mark every session's own pushes as fresh activity. Known limit.

## Failure policy

Fails OPEN on any parse trouble, outside a git repo, off a Morrison-Lab remote,
with no open PR, when `gh` is missing, on a network error or timeout -- and in
every network-failure case says so in `additionalContext` and on stderr rather
than going quiet, because a silent open is indistinguishable from a guard that
never ran (`shared/principles/fail-fast.md`).

## The override

`ALLOW_UNCLAIMED_PR_WORK=1`, as an env prefix on the commit or push, as the
call's leading `export`, or in the process environment. It is for a case this
guard did not foresee; reaching for it means saying why.

`PR_CLAIM_GH_CMD` replaces the `gh` executable (shlex-split); tests use it.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

OVERRIDE = "ALLOW_UNCLAIMED_PR_WORK"
OWNERS = {"morrison-lab"}
AGENT_MARKER = "posted by claude code (ai agent)"
CLAIM_PHRASES = ("hold off", "paws off")
NET_TIMEOUT = 8
SKIP_BRANCHES = {"HEAD", "main", "master"}

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import env_value, git_subcommand, simple_commands
except Exception as _exc:  # broken install: fail open, and say so
    print(f"no-pr-work-without-claim: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    env_value = git_subcommand = simple_commands = None

LEADING_OVERRIDE = re.compile(
    r"\A[ \t]*(?:export[ \t]+)?" + OVERRIDE + r"=1[ \t]*(?:;|&&|\|\||\r?\n|\Z)")

DENY_NO_CLAIM = """\
`git {verb}` on branch `{branch}`, which has open PR {pr_url}, but that PR has
no claim comment from THIS session.

Two sessions on one branch is how #4134 lost 471 lines of memories/preferences.md
on 2026-09-30 (ai-config#4155). Post a claim first, naming this session so a
second session under the same login can tell the two apart:

    Claude Code CLI (local session) is working on this --- please hold off on pushing to this branch until I'm done.

    Session worktree: `{worktree}`  Session id: `{session_id}`

    _Posted by Claude Code (AI agent) --- not written by a human._

Post it with `gh pr comment {pr_number} --body-file <file>`, then retry. If a
claim from another session is already live on the PR, do not post over it:
that session is working this branch, and the second one stands down.

{override}=1 clears this refusal (env prefix on the command, a leading
`export`, or the process environment) -- for a case this guard did not foresee,
and say why.
"""

DENY_SUPERSEDED = """\
`git {verb}` on branch `{branch}` ({pr_url}): another session claimed this PR
after you did.

    your latest claim:   {mine_at}
    their claim:         {theirs_url}  ({theirs_at})

That session is the live owner now. Stop and read their claim before touching
the branch; take over only by posting a fresh claim of your own once theirs has
lapsed or been released (shared/workflow/claim-pr.md, 2-hour rule).

{override}=1 clears this refusal; say why.
"""


def emit(decision=None, reason=None, context=None):
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    spec = out["hookSpecificOutput"]
    if decision:
        spec["permissionDecision"] = decision
        spec["permissionDecisionReason"] = reason
    if context:
        spec["additionalContext"] = context
    print(json.dumps(out))


def warn_open(message):
    """Visible fail-open: stderr plus context, never a silent allow."""
    print(f"no-pr-work-without-claim: {message}", file=sys.stderr)
    emit(context=f"no-pr-work-without-claim could not verify a claim: "
                 f"{message}. Allowed; check the PR's claim comments by hand.")


def run(argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          timeout=NET_TIMEOUT)


def git(cwd, *args):
    r = run(["git", *args], cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else None


def gh_json(path):
    """GET `path` through `gh api`; raises on any failure (caller fails open)."""
    cmd = shlex.split(os.environ.get("PR_CLAIM_GH_CMD", "gh"))
    r = run([*cmd, "api", "--paginate", path])
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {r.stderr.strip()[:200]}")
    text = r.stdout.strip()
    if not text:
        return []
    # --paginate concatenates one JSON array per page: ][ -> ,
    return json.loads(re.sub(r"\]\s*\[", ",", text))


def norm(text):
    return text.replace("\\", "/").lower()


def is_claim(body):
    low = (body or "").lower()
    return AGENT_MARKER in low and any(p in low for p in CLAIM_PHRASES)


def names_session(body, session_id, worktree):
    low = norm(body or "")
    if session_id and session_id.lower() in low:
        return True
    if worktree:
        wt = re.escape(norm(worktree).rstrip("/"))
        return re.search(wt + r"(?![\w.-])", low) is not None
    return False


def classify_claims(comments, session_id, worktree):
    """(mine, theirs, anonymous): claim comments split by attributable session."""
    mine, theirs, anonymous = [], [], []
    for c in comments:
        if not is_claim(c.get("body")):
            continue
        if names_session(c["body"], session_id, worktree):
            mine.append(c)
        elif re.search(r"session (?:id|worktree)", c["body"], re.I):
            theirs.append(c)
        else:
            anonymous.append(c)
    return mine, theirs, anonymous


def matched_command(command):
    """(verb, env) for the first commit/push worth guarding, else None."""
    cmds = simple_commands(command)
    if not cmds:
        return None
    for argv in cmds:
        parsed = git_subcommand(argv)
        if parsed is None:
            continue
        sub, rest, env = parsed
        if sub not in ("commit", "push"):
            continue
        if "--dry-run" in rest or (sub == "push" and (
                "--delete" in rest or "-d" in rest)):
            continue
        if env_value(env, OVERRIDE) == "1":
            continue
        return sub, env
    return None


def activity_warning(owner, repo, branch, since, cwd):
    """Foreign pushes since `since`, as a warning string or None."""
    items = gh_json(f"repos/{owner}/{repo}/activity"
                    f"?ref=refs/heads/{branch}&per_page=50")
    foreign = []
    for it in items:
        if it.get("activity_type") not in ("push", "force_push"):
            continue
        if (it.get("timestamp") or "") <= since:
            continue
        after = it.get("after") or ""
        if not after:
            continue
        if run(["git", "merge-base", "--is-ancestor", after, "HEAD"],
               cwd=cwd).returncode == 0:
            continue
        actor = (it.get("actor") or {}).get("login", "?")
        foreign.append(f"{it.get('timestamp')} {actor} -> {after[:8]}")
    if not foreign:
        return None
    return ("Pushes to this branch since your claim that are NOT in your local "
            "history (another session or person, or a force-push of yours): "
            + "; ".join(foreign[:5])
            + ". Fetch and read them before pushing "
              "(shared/workflow/claim-pr.md; ai-config#4155).")


def evaluate(payload):
    """Returns None (silent allow) or a dict of emit() kwargs."""
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not isinstance(command, str) or not command.strip():
        return None
    if simple_commands is None:
        return None
    if os.environ.get(OVERRIDE) == "1" or LEADING_OVERRIDE.match(command):
        return None
    hit = matched_command(command)
    if hit is None:
        return None
    verb = hit[0]

    cwd = payload.get("cwd") or os.getcwd()
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch in SKIP_BRANCHES:
        return None
    m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?$",
                  git(cwd, "remote", "get-url", "origin") or "")
    if not m or m.group(1).lower() not in OWNERS:
        return None
    owner, repo = m.group(1), m.group(2)
    worktree = git(cwd, "rev-parse", "--show-toplevel") or ""
    session_id = payload.get("session_id") or ""

    try:
        prs = gh_json(f"repos/{owner}/{repo}/pulls?state=open"
                      f"&head={owner}:{branch}")
        if not prs:
            return None
        pr = prs[0]
        comments = gh_json(f"repos/{owner}/{repo}/issues/{pr['number']}"
                           f"/comments?per_page=100")
        mine, theirs, anonymous = classify_claims(comments, session_id,
                                                  worktree)
        pr_url = pr.get("html_url") or f"#{pr['number']}"
        if not mine:
            return {"decision": "deny", "reason": DENY_NO_CLAIM.format(
                verb=verb, branch=branch, pr_url=pr_url, pr_number=pr["number"],
                worktree=worktree, session_id=session_id or "<session id>",
                override=OVERRIDE)}
        latest_mine = max(c["created_at"] for c in mine)
        newer = [c for c in theirs if c["created_at"] > latest_mine]
        if newer:
            t = max(newer, key=lambda c: c["created_at"])
            return {"decision": "deny", "reason": DENY_SUPERSEDED.format(
                verb=verb, branch=branch, pr_url=pr_url, mine_at=latest_mine,
                theirs_url=t.get("html_url", "?"), theirs_at=t["created_at"],
                override=OVERRIDE)}
        notes = []
        if any(c["created_at"] > latest_mine for c in anonymous):
            notes.append("A claim that names no session was posted after "
                         "yours; it may be another session's. Read the PR "
                         "comments before continuing.")
        if verb == "push":
            warning = activity_warning(owner, repo, branch, latest_mine, cwd)
            if warning:
                notes.append(warning)
        return {"context": " ".join(notes)} if notes else None
    except Exception as exc:  # network, gh missing, bad JSON: visible fail-open
        return {"open_error": f"{type(exc).__name__}: {exc}"}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"no-pr-work-without-claim: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") not in (
            "Bash", "bash", "run_command", "execute_command", "terminal",
            "shell"):
        return 0
    try:
        result = evaluate(payload)
    except Exception as exc:
        warn_open(f"could not evaluate ({exc})")
        return 0
    if result is None:
        return 0
    if "open_error" in result:
        warn_open(result["open_error"])
    else:
        emit(result.get("decision"), result.get("reason"),
             result.get("context"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
