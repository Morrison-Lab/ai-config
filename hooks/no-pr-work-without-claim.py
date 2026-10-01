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
    agent)`) and the `hold off` (or legacy `paws off` / `back off`) wording, per
    `skills/claim-pr/SKILL.md`;
  * it is THIS session's when its body contains the payload's `session_id` or
    this worktree's path (`/c/x` and `C:/x` spellings are equal). The forge
    login is shared by every session under one account, so the comment must
    say which session it is; the skills/claim-pr template now does.
  * no claim at all, or only claims naming a DIFFERENT session: DENY.
  * only claims that name NO session (every other emitter's template, until
    ai-config#4160 lands): WARN, because such a claim may be this session's
    own and a hard deny would block every existing claim flow.
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

claim-pr.md's 2-hour expiry is applied to a PEER's claim only, through the
PR's `updated_at` (which over-approximates freshness, so a stale verdict is
definitive): when the only claim names another session and the PR has shown no
activity for 2 hours, the hook warns instead of denying. An OWN claim is
accepted whatever its age, because every session's own pushes would otherwise
count as fresh activity. Known limit.

A release comment is not modelled beyond keeping an "unclaiming" / "releasing
my claim" comment from counting as a claim. A claim whose session later
released it with other wording still satisfies this check. Known limit.

Push destinations built by the shell (`$BRANCH`, `$(git branch --show-current)`)
cannot be read statically and fall back to the checkout's current branch. A
remote URL whose host is an SSH alias beginning `github.com` is accepted; any
other alias is not matched and the hook stays silent.

Session identity is the worktree path (the model rarely knows its own
`session_id`), so two sessions sharing ONE checkout cannot be told apart.
Known limit; it is the same-checkout shape of the 2026-09-30 incident that this
hook cannot see. The converse also holds: an isolated subagent worktree has a
different path from its parent, so a PR branch the parent claimed reads as a
PEER's claim to the subagent, which is denied until it posts a claim of its
own (or sets the override). That is the intended reading for a second writer
on a claimed branch, and subagents normally work branches of their own.

A commit or push nested in a shell's `-c` starts in a directory this scan
cannot know, so it is a visible fail-open (not evaluated) unless the piece
`cd`s to an absolute path first.

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
An argument-less `git push` goes to the branch's upstream remote, which is
assumed to be `origin`.

The activity warning compares each push's `after` SHA to local `HEAD`, so a
session that amended, rebased or force-pushed its own earlier pushes sees them
as foreign, and so does a main-sync merge pushed by the @claude bot, and so
does any push whose commit this clone has not fetched (a stale or shallow
clone). It is a
warning, never a deny, for that reason. Only the newest page (50 entries) of
the activity feed is read, and at most MAX_ACTIVITY_CHECKS pushes of it are
examined, so on a busy branch older foreign pushes are not seen.

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
from datetime import datetime, timezone
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
# The release terms claim-pr.md already tells every claim detector to check
# for ("unclaiming", the retired "paws off released", the "PR is free" and
# "now mergeable" forms), plus "releasing my claim". A bare "will release the
# claim when done" is a claim, not a release.
RELEASE_TERMS = (r"unclaim|released|pr is free|now mergeable"
                 r"|releasing (?:my |the |this )?claim")
# claim-pr.md: a claim is live for 2 hours from the PR's last push or comment.
STALE_HOURS = 2
SKIP_BRANCHES = {"HEAD", "main", "master"}
# Options that consume the NEXT token as a value when written without `=`.
# (`git push --signed` and `--recurse-submodules` take their value attached
# with `=` only, so they are deliberately absent.)
PUSH_VALUE_OPTS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
COMMIT_VALUE_OPTS = {"-m", "--message", "-F", "--file", "-C", "--reuse-message",
                     "-c", "--reedit-message", "--author", "--date",
                     "--cleanup", "-t", "--template", "--fixup", "--squash"}
# A short-option cluster ending in one of these takes the next token as value
# (`git commit -am "msg"`).
SHORT_VALUE_LETTERS = {"commit": "mFCct", "push": "o"}

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (GIT_VALUE_OPTS, env_value, resolve_cd_target,
                          shell_c_expansions, simple_commands, strip_env)
except Exception as _exc:  # broken install: fail open, and say so
    print(f"no-pr-work-without-claim: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    env_value = simple_commands = strip_env = resolve_cd_target = None
    shell_c_expansions = None
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
`git {verb}` on branch `{branch}` ({pr_url}): the PR has a claim naming a
different session, and this session has none of its own.

    that claim:   {peer_url}  ({peer_at})

That session is working this branch now. Do not post a competing claim over
it and do not commit: stand down. To take over, first confirm theirs has
lapsed or been released (shared/workflow/claim-pr.md, 2-hour rule; this hook
does not check either), then post a fresh claim that names this session.

{override}=1 clears this refusal; say why.
"""

DENY_SUPERSEDED = """\
`git {verb}` on branch `{branch}` ({pr_url}): another session claimed this PR
after you did.

    your latest claim:   {mine_at}
    their claim:         {theirs_url}  ({theirs_at})

That session is the live owner now. Stop and read their claim before touching
the branch; take over only by posting a fresh claim of your own once theirs has
lapsed or been released (shared/workflow/claim-pr.md, 2-hour rule; this hook
checks neither).

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
    """stdout of a git call in `cwd`, or None (also when `cwd` does not exist:
    git could not run the user's command there either, so there is nothing to
    guard and no reason to warn)."""
    try:
        r = run(["git", *args], cwd=cwd)
    except OSError:
        return None
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
    """Lowercase, forward slashes, and Git Bash `/c/x` read as `c:/x`.

    Applied to the claim body and the worktree path alike, so a session that
    wrote its path from `pwd` in Git Bash still matches `git rev-parse
    --show-toplevel`'s `C:/x` form.
    """
    text = text.replace("\\", "/").lower()
    return re.sub(r"(?<![\w/])/([a-z])/(?=[\w.-])", r"\1:/", text)


def is_claim(body):
    """A claim comment: the agent marker plus hold-off wording.

    Every emitter in skills/ carries one of the three wordings claim-pr.md
    tells claim readers to match (claim-pr, ardi, handoff and the review-only
    form say `hold off`; the older emitters say `paws off` or `back off`), so
    that is the invariant. A release comment ("unclaiming",
    "releasing my claim") and a negated mention ("no need to hold off") are
    not claims.
    """
    # The session lines are data, not prose: a worktree named after an issue
    # slug ("fix-unclaim-wording") must not read as a release term.
    low = re.sub(r"(?m)^[ \t]*session (?:worktree|id):.*$", "",
                 (body or "").lower())
    return (AGENT_MARKER in low
            and re.search(r"(?<!need to )(?<!not )(?<!n't )(?:hold|back) off"
                          r"|paws off", low) is not None
            and re.search(RELEASE_TERMS, low) is None)


def pr_is_stale(pr):
    """True when the PR shows no activity for STALE_HOURS (claim-pr's rule).

    `updated_at` moves on more events than pushes and comments, so it only
    over-approximates freshness: a stale verdict is definitive, a borderline
    one respects the claim. A PR with no readable `updated_at` is not stale.
    """
    stamp = pr.get("updated_at")
    if not stamp:
        return False
    try:
        then = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - then).total_seconds() > STALE_HOURS * 3600


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
        return re.search(r"(?<![\w./-])" + wt + r"(?![\w-]|/[\w.-]|\.\w)",
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
    dry, skip = False, False
    value_opts = COMMIT_VALUE_OPTS if sub == "commit" else PUSH_VALUE_OPTS
    for tok in rest:
        if skip:  # the value of the previous option, e.g. a `-m` message
            skip = False
            continue
        if tok == "--":
            break
        if tok in value_opts or (re.fullmatch(r"-[A-Za-z]+", tok)
                                 and tok[-1] in SHORT_VALUE_LETTERS[sub]):
            skip = True
            continue
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
    # The command itself, then every command line nested in a shell's `-c`.
    # A nested piece starts in a directory this scan cannot know, so a
    # commit/push found there is Indeterminate (a visible fail-open) rather
    # than silently skipped, unless the piece `cd`s to an absolute path first.
    texts = ([(command, start_dir)]
             + [(t, None) for t in shell_c_expansions(command)[1:]])
    for text, text_dir in texts:
        hit = _scan(text, text_dir)
        if hit is not None:
            return hit
    return None


def _scan(command, start_dir):
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
    if any(t in ("--tags", "--all", "--mirror") for t in args):
        return "!skip"  # pushes a ref SET, not one branch
    if pos and pos[0] != "origin":
        return "!skip"  # the PR lookup is against origin's repository
    if len(pos) < 2:
        return None
    spec = pos[1].lstrip("+")
    if spec.startswith(":"):
        return "!skip"  # `:old` deletes a remote branch
    dst = spec.split(":", 1)[1] if ":" in spec else spec
    if dst in ("", "HEAD") or any(c in dst for c in "$`("):
        # `HEAD`, or a name built by the shell (`$BRANCH`, `$(git branch
        # --show-current)`) that cannot be read statically: the current branch.
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
        # A broken install must not be a silent bypass; only commands that
        # mention git are worth a warning.
        if re.search(r"\bgit\b", command):
            return {"open_error": "scripts/lib/shellcmd.py could not be "
                                  "loaded, so this command was not examined"}
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
    m = re.search(r"github\.com[\w.-]*[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$",
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
        notes = []
        if not mine and theirs and pr_is_stale(pr):
            # claim-pr.md's 2-hour rule: a claim on a PR idle that long has
            # lapsed. `updated_at` over-approximates freshness, so "stale" is
            # definitive; a PR touched since then keeps the deny below.
            notes.append(
                f"The only claim on {pr_url} names another session, but the "
                f"PR has shown no activity for over {STALE_HOURS} hours, so "
                f"it is treated as lapsed. Post your own claim naming this "
                f"session (`Session worktree: {worktree}`) before continuing.")
            since = max(c["created_at"] for c in theirs)
        elif not mine and theirs:
            peer = max(theirs, key=lambda c: c["created_at"])
            return {"decision": "deny", "reason": DENY_PEER_CLAIM.format(
                verb=verb, branch=branch, pr_url=pr_url,
                peer_url=peer.get("html_url", "?"), peer_at=peer["created_at"],
                override=OVERRIDE)}
        elif not mine and anonymous:
            # A claim that names no session may be this session's own, posted
            # with a template that predates the session line (ai-config#4160).
            # Unattributable, so it warns rather than denies: a hard deny here
            # would block every existing claim flow on first commit.
            notes.append(
                f"The PR {pr_url} has a claim that names no session "
                f"({anonymous[-1].get('html_url', '?')}). It may be yours or "
                f"another session's, and this hook cannot tell. Re-post it "
                f"with a `Session worktree: {worktree}` line so it can be "
                f"attributed; if it is another session's, stand down.")
            since = max(c["created_at"] for c in anonymous)
        elif not mine:
            return {"decision": "deny", "reason": DENY_NO_CLAIM.format(
                verb=verb, branch=branch, pr_url=pr_url, pr_number=pr["number"],
                worktree=worktree, session_id=session_id or "<session id>",
                override=OVERRIDE)}
        else:
            since = max(c["created_at"] for c in mine)
            newer = [c for c in theirs if c["created_at"] > since]
            if newer:
                t = max(newer, key=lambda c: c["created_at"])
                return {"decision": "deny", "reason": DENY_SUPERSEDED.format(
                    verb=verb, branch=branch, pr_url=pr_url, mine_at=since,
                    theirs_url=t.get("html_url", "?"),
                    theirs_at=t["created_at"], override=OVERRIDE)}
            if any(c["created_at"] > since for c in anonymous):
                notes.append("A claim that names no session was posted after "
                             "yours; it may be another session's. Read the PR "
                             "comments before continuing.")
        if verb == "push":
            # Its own try: a 403/404 from the activity endpoint (it needs push
            # access) must not discard the claim outcomes already computed.
            try:
                warning = activity_warning(owner, repo, branch, since, cwd)
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
