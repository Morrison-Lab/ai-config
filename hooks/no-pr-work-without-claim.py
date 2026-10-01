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

A release ("unclaiming") comment is not modelled either: it only keeps a
comment containing `unclaim` from counting as a claim. A claim whose session
later released it still satisfies this check. Known limit.

A PR from a fork (head repo under another owner) is not found by the
`head=<owner>:<branch>` query, so the hook stays silent for it. Known limit.

The directory a command runs in is the payload `cwd` moved by earlier `cd`s
and the command's own `git -C` (`scripts/lib/shellcmd.py`'s
`resolve_cd_target`); an unresolvable move (`cd -`, `$VAR`, `--git-dir`) is a
visible fail-open, not a guess. Subshell scoping of a `cd` is not modelled
(`simple_commands` flattens it).

A push is judged by its first refspec's destination branch (`git push origin
HEAD:foo` checks `foo`; a tag push is skipped); with no refspec it is the
checkout's current branch. A push of several branches is judged by the first.

The activity warning compares each push's `after` SHA to local `HEAD`, so a
session that amended, rebased or force-pushed its own earlier pushes sees them
as foreign, and so does a main-sync merge pushed by the @claude bot. It is a
warning, never a deny, for that reason. At most MAX_ACTIVITY_CHECKS pushes are
examined.

Every subprocess shares one TOTAL_BUDGET-second deadline (under the hooks.json
timeout); running out is a visible fail-open.

Cost: one to three forge reads per matched commit or push, uncached. Accepted
because a stale cached "claimed" answer is exactly the failure being guarded.

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

`PR_CLAIM_GH_CMD` replaces the `gh` executable (shlex-split) and
`PR_CLAIM_TOTAL_BUDGET` sets the shared subprocess budget in seconds
(default 20); tests use both.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from urllib.parse import quote

OVERRIDE = "ALLOW_UNCLAIMED_PR_WORK"
OWNERS = {"morrison-lab"}
AGENT_MARKER = "posted by claude code (ai agent)"
NET_TIMEOUT = 8
# One budget for every subprocess the hook runs, kept under the hooks.json
# timeout (30s) so a slow forge is a visible fail-open rather than a harness
# kill. Set at the start of main().
TOTAL_BUDGET = float(os.environ.get("PR_CLAIM_TOTAL_BUDGET", "20"))
_DEADLINE = [None]
MAX_ACTIVITY_CHECKS = 10
SKIP_BRANCHES = {"HEAD", "main", "master"}
# `git push` options that consume the NEXT token as a value.
PUSH_VALUE_OPTS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec",
                   "--recurse-submodules", "--signed"}

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (GIT_VALUE_OPTS, env_value, resolve_cd_target,
                          simple_commands, strip_env)
except Exception as _exc:  # broken install: fail open, and say so
    print(f"no-pr-work-without-claim: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    env_value = simple_commands = strip_env = resolve_cd_target = None
    GIT_VALUE_OPTS = frozenset()

# Raised when the directory a command runs in cannot be named statically.
class Indeterminate(Exception):
    pass

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

DENY_PEER_CLAIM = """\
`git {verb}` on branch `{branch}` ({pr_url}): the PR has a claim that does not
name this session, and this session has none of its own.

    that claim:   {peer_url}  ({peer_at})

It is either another session's, or your own posted without a `Session
worktree:` / `Session id:` line (re-post it with one). If it is another
session's, that session is working this branch now. Do not post a competing
claim over it and do not commit: stand down, or take over only after theirs has lapsed
or been released (shared/workflow/claim-pr.md, 2-hour rule), by posting a fresh
claim that names this session.

{override}=1 clears this refusal; say why.
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
    timeout = NET_TIMEOUT
    if _DEADLINE[0] is not None:
        timeout = min(timeout, _DEADLINE[0] - time.monotonic())
        if timeout <= 0:
            raise TimeoutError(f"the hook's {TOTAL_BUDGET}s budget is spent")
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def git(cwd, *args):
    r = run(["git", *args], cwd=cwd)
    return r.stdout.strip() if r.returncode == 0 else None


def gh_json(path, paginate=True):
    """GET `path` through `gh api`; raises on any failure (caller fails open).

    `--paginate` prints one JSON array per page, back to back. They are decoded
    one at a time with `raw_decode` rather than joined by rewriting `][`, which
    would also rewrite a comment body containing `] [`.
    """
    cmd = shlex.split(os.environ.get("PR_CLAIM_GH_CMD", "gh"))
    r = run([*cmd, "api", *(["--paginate"] if paginate else []), path])
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {r.stderr.strip()[:200]}")
    text, items, pos = r.stdout, [], 0
    decoder = json.JSONDecoder()
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            return items
        page, pos = decoder.raw_decode(text, pos)
        if isinstance(page, list):
            items.extend(page)
        else:
            items.append(page)


def norm(text):
    return text.replace("\\", "/").lower()


def is_claim(body):
    """A claim comment: agent marker, `working on this`, and hold-off wording.

    Every emitter in skills/ carries one of the two wordings (claim-pr, ardi,
    handoff, and the review-only form all say `hold off`; the older emitters
    say `paws off`), so that is the invariant. A release comment ("unclaiming")
    and a negated mention ("no need to hold off") are not claims.
    """
    low = (body or "").lower()
    return (AGENT_MARKER in low
            and re.search(r"(?<!need to )(?<!not )(?<!n't )hold off|paws off",
                          low) is not None
            and "unclaim" not in low)


def names_session(body, session_id, worktree):
    """True when `body` names this session's id or this exact worktree path.

    Both tests are token-bounded: an id or path that is merely a PREFIX of a
    longer one (`...-ab`, `.../.claude/worktrees/x`) does not match.
    """
    low = norm(body or "")
    if session_id:
        sid = re.escape(session_id.lower())
        if re.search(r"(?<![\w-])" + sid + r"(?![\w-])", low):
            return True
    if worktree:
        wt = re.escape(norm(worktree).rstrip("/"))
        # Left boundary: `/work/repo` must not match inside `/home/u/work/repo`.
        # Right boundary: a sentence-final `.` after the path is fine, but
        # `.x` or `/x` or `-x` continues the path.
        return re.search(r"(?<![\w./-])" + wt + r"(?![\w/-]|\.\w)",
                         low) is not None
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


def is_dry_run(sub, rest):
    """Last-occurrence-wins over `--dry-run` / `--no-dry-run` (and push `-n`).

    `git commit -n` is `--no-verify`, so the short form counts for push only.
    """
    dry = False
    for tok in rest:
        if tok == "--":
            break
        if tok == "--dry-run" or (sub == "push" and re.fullmatch(
                r"-[A-Za-z]*n[A-Za-z]*", tok)):
            dry = True
        elif tok == "--no-dry-run":
            dry = False
    return dry


def git_options(rest_after_git):
    """(index of the subcommand, list of `-C` dirs); raises Indeterminate on
    `--git-dir` / `--work-tree`, which move the repository itself."""
    i, c_dirs = 0, []
    while i < len(rest_after_git) and rest_after_git[i].startswith("-"):
        tok = rest_after_git[i]
        if tok in ("--git-dir", "--work-tree") or tok.startswith(
                ("--git-dir=", "--work-tree=")):
            raise Indeterminate("--git-dir/--work-tree")
        if tok == "-C" and i + 1 < len(rest_after_git):
            c_dirs.append(rest_after_git[i + 1])
        i += 2 if tok in GIT_VALUE_OPTS else 1
    return i, c_dirs


def matched_command(command, start_dir):
    """`(verb, workdir)` for the first commit/push worth guarding, else None.

    `workdir` is where that command runs: the payload cwd moved by any earlier
    `cd` in the same compound command, then by the command's own `git -C`.
    Raises Indeterminate when that cannot be named (`cd -`, `$VAR`, ...), which
    the caller turns into a visible fail-open.
    """
    cmds = simple_commands(command)
    if not cmds:
        return None
    cur = start_dir
    for argv in cmds:
        env, rest = strip_env(argv)
        if not rest:
            continue
        if rest[0] in ("cd", "pushd", "popd"):
            cur = resolve_cd_target(rest, cur)
            continue
        if rest[0] != "git":
            continue
        idx, c_dirs = git_options(rest[1:])
        if idx + 1 >= len(rest):
            continue
        sub, args = rest[1 + idx], rest[2 + idx:]
        if sub not in ("commit", "push"):
            continue
        if is_dry_run(sub, args) or (sub == "push" and (
                "--delete" in args or "-d" in args)):
            continue
        if env_value(env, OVERRIDE) == "1":
            continue
        workdir = cur
        for d in c_dirs:
            if workdir is None:
                break
            workdir = d if os.path.isabs(d) else os.path.join(workdir, d)
        if workdir is None:
            raise Indeterminate("a `cd` target that cannot be resolved statically")
        return sub, workdir, (push_target(args) if sub == "push" else None)
    return None


def push_target(args):
    """The branch a `git push` writes, from its first refspec.

    `None` when the push names no refspec (the current branch is meant),
    `"HEAD"` for `HEAD` (also the current branch), `"!skip"` for a ref that is
    not a branch (a tag), else the destination branch name. Only the first
    refspec is read; a push of several branches is judged by the first. Known
    limit.
    """
    pos, i = [], 0
    while i < len(args):
        tok = args[i]
        if tok == "--":
            pos.extend(args[i + 1:])
            break
        if tok.startswith("-"):
            i += 2 if tok in PUSH_VALUE_OPTS else 1
            continue
        pos.append(tok)
        i += 1
    if len(pos) < 2:
        return None
    spec = pos[1].lstrip("+")
    dst = spec.split(":", 1)[1] if ":" in spec else spec
    if dst in ("", "HEAD"):
        return "HEAD"
    if dst.startswith("refs/heads/"):
        return dst[len("refs/heads/"):]
    if dst.startswith("refs/"):
        return "!skip"
    return dst


def activity_warning(owner, repo, branch, since, cwd):
    """Foreign pushes since `since`, as a warning string or None.

    One page only: the endpoint lists newest first and only entries newer than
    the claim matter, so walking the branch's whole history (`--paginate`)
    would spend the network timeout for nothing.
    """
    items = gh_json(f"repos/{owner}/{repo}/activity"
                    f"?ref=refs/heads/{quote(branch, safe='/')}&per_page=50",
                    paginate=False)
    foreign, checked, capped = [], 0, False
    for it in items:
        if it.get("activity_type") not in ("push", "force_push"):
            continue
        if (it.get("timestamp") or "") <= since:
            continue
        after = it.get("after") or ""
        if not after:
            continue
        checked += 1
        if checked > MAX_ACTIVITY_CHECKS:
            capped = True
            break
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
            + (" (more pushes not examined)" if capped else "")
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
    try:
        hit = matched_command(command, payload.get("cwd") or os.getcwd())
    except Indeterminate as exc:
        return {"open_error": f"cannot tell which repository the command "
                              f"runs in ({exc})"}
    if hit is None:
        return None
    verb, cwd, target = hit
    if target == "!skip":
        return None
    branch = (target if target not in (None, "HEAD")
              else git(cwd, "rev-parse", "--abbrev-ref", "HEAD"))
    if not branch or branch in SKIP_BRANCHES:
        return None
    m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$",
                  git(cwd, "remote", "get-url", "origin") or "")
    if not m or m.group(1).lower() not in OWNERS:
        return None
    owner, repo = m.group(1), m.group(2)
    worktree = git(cwd, "rev-parse", "--show-toplevel") or ""
    session_id = payload.get("session_id") or ""

    try:
        prs = gh_json(f"repos/{owner}/{repo}/pulls?state=open"
                      f"&head={quote(owner + ':' + branch, safe=':/')}")
        if not prs:
            return None
        pr = prs[0]
        comments = gh_json(f"repos/{owner}/{repo}/issues/{pr['number']}"
                           f"/comments?per_page=100")
        mine, theirs, anonymous = classify_claims(comments, session_id,
                                                  worktree)
        pr_url = pr.get("html_url") or f"#{pr['number']}"
        if not mine and (theirs or anonymous):
            peer = max(theirs + anonymous, key=lambda c: c["created_at"])
            return {"decision": "deny", "reason": DENY_PEER_CLAIM.format(
                verb=verb, branch=branch, pr_url=pr_url,
                peer_url=peer.get("html_url", "?"), peer_at=peer["created_at"],
                override=OVERRIDE)}
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
            # Its own try: a 403/404 from the activity endpoint (it needs push
            # access) must not discard the claim outcomes already computed.
            try:
                warning = activity_warning(owner, repo, branch, latest_mine,
                                           cwd)
            except Exception as exc:
                warning = (f"could not read the forge activity for this "
                           f"branch ({type(exc).__name__}: {exc}); check for "
                           f"other writers by hand before pushing.")
                print(f"no-pr-work-without-claim: {warning}", file=sys.stderr)
            if warning:
                notes.append(warning)
        return {"context": " ".join(notes)} if notes else None
    except Exception as exc:  # network, gh missing, bad JSON: visible fail-open
        return {"open_error": f"{type(exc).__name__}: {exc}"}


def main():
    _DEADLINE[0] = time.monotonic() + TOTAL_BUDGET
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
