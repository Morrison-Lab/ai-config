#!/usr/bin/env python3
"""PreToolUse guard: a `git push` that could discard another agent's commits.

## The gap this closes

A branch you cut, whose PR you opened, and whose review round you are driving
is the branch you are *least* likely to check before pushing to. Ownership is
the thing that suppresses the check, and the belief is usually wrong:
`shared/workflow/claim-pr.md` already records that the `@claude` agent pushes
to your branch on PR activity, that a second CLI session can pick the same PR
up, and that a human can push to it -- and it carries three separate
procedures for recovering from a push that came back rejected.

Every one of those recoveries runs AFTER the collision. Nothing made the check
happen before the push, and a `git fetch` from earlier in the session is not
evidence about the remote now: it is a measurement, and it expired the moment
somebody else pushed.

`skills/push/SKILL.md` states the pre-push checks well, but a skill only runs
when it is invoked, and a bare `git push` in the middle of an ARDI round never
passes through it. That is the gap a hook closes -- it runs on the command
itself, independent of whether the moment felt like it warranted a check.

## Two behaviours, and why only one of them refuses

**It REFUSES a bare `--force` / `-f`** (deny), because that is the one case
that is decidable from the command text alone and has a remedy that costs one
word. `git push --force-with-lease --force-if-includes` does everything
`--force` does except overwrite a remote tip you have not seen; it is never
the worse choice, and where the remote ref does not exist the lease succeeds
trivially. So the refusal is always satisfiable, and being wrong about it
costs a retype rather than a lost commit.

The escape hatch is real and this corpus documents the case that needs it:
`memories/git.md` records `--force-with-lease` failing with `stale info` when
the remote branch was *deleted* (squash-merge with auto-delete), where the
lease is unsatisfiable rather than violated. Prefix the command with
`ALLOW_FORCE_PUSH=1` for that.

**It WARNS on everything else** (`additionalContext`, no `permissionDecision`),
because whether a divergence matters is a judgment this hook cannot make: a
rebase you did on purpose and a parallel session's commits look identical from
here. Per README's "A hook that misfires is worse than a missing one", the
warning path only ever adds context.

## The measurement

The warning is not a transcript heuristic about whether you fetched recently.
It is a fresh reading taken at the moment of the push:

    git ls-remote --heads <remote> <branch>

`ls-remote` is read-only -- it updates no remote-tracking ref and writes
nothing -- so the hook cannot itself change the state it is reporting on.
The reading is then classified:

  - remote ref absent          -> nothing to collide with; silent
  - remote tip == local HEAD   -> already pushed; silent
  - remote tip is an ancestor  -> fast-forward; silent (the common case, so
                                  the hook stays quiet in normal operation)
  - remote tip is NOT an ancestor of HEAD -> WARN, and say what is at risk

In that last case the hook tries to describe the divergent commits. Whether it
can turns on one thing worth distinguishing in the report:

  - the object IS present locally (a prior fetch brought it): list the commits
    with their authors and dates, so a parallel session is nameable.
  - the object is NOT present locally: that is the sharper signal, not the
    weaker one -- the remote moved since your last fetch and you cannot even
    see what is there. Say exactly that.

## The match condition

  M1  the tool is `Bash` and `tool_input.command` parses into simple commands
  M2  one of those is `git push`, after skipping env assignments, lead words,
      and `git`'s own global options (`-C <dir>`, `-c <cfg>`, `--git-dir=...`)
  M3  it is not a `--dry-run` / `-n` push (which transfers nothing)
  M4  it is not a `--delete` / `-d` push (branch deletion is
      `skills/clean-branches`' territory, not this guard's)

Deny additionally requires a `--force` or `-f` token with no
`--force-with-lease` beside it and no `ALLOW_FORCE_PUSH=1` prefix.

`--mirror` and `--all` are deliberately out of scope: they push ref sets rather
than one branch, so the single-branch reading below would misdescribe them.

Fails OPEN on any parse trouble, outside a git repository, when `git` or the
network is unreachable, and on any `ls-remote` timeout.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys

RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
LEAD_WORDS = {"then", "do", "else", "!", "time", "sudo", "command", "exec",
              "nohup", "env"}

_SHELL_OPS = set("();|&")

# `ALLOW_FORCE_PUSH=1` counts only as a real env assignment at the start of
# the same simple command, never as a mention of the string elsewhere. Same
# shape as `no-unauthorized-merge.py`'s `ALLOW_MERGE=1` anchor and for the
# same reason: a guard that its own documentation disables is worthless.
OVERRIDE = "ALLOW_FORCE_PUSH"

# `git push` options that consume the FOLLOWING token, so a value like
# `origin` sitting after one is not the remote.
PUSH_VALUE_OPTS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
# `git`'s own global options that consume the following token.
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                  "--exec-path"}

# Short-option letters `git push` accepts, none of which is a value-taking
# flag except `-o` -- so an `f` inside a cluster of these unambiguously means
# `--force` (`git push -fu origin HEAD` is real, accepted bash).
SHORT_CLUSTER = re.compile(r"^-[46dfnqutv]+$")


def _simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error.

    Same construction as `flag-reset-hard-uncommitted-work.py`'s
    `_simple_commands`: join backslash-continued lines, blank heredoc bodies,
    turn unquoted newlines into `;`, then let `shlex` split and dequote.
    """
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


def _push_argv(argv):
    """The `push`-and-after tokens of a `git push` simple command, plus whether
    the command was prefixed with the override. `(None, False)` if this argv
    is not a `git push`."""
    i = 0
    override = False
    while i < len(argv) and (ASSIGNMENT.match(argv[i]) or argv[i] in LEAD_WORDS):
        if argv[i].startswith(OVERRIDE + "="):
            override = argv[i].split("=", 1)[1].strip() == "1"
        i += 1
    if i >= len(argv) or argv[i] != "git":
        return None, False
    i += 1
    # Skip git's own global options.
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] in GIT_VALUE_OPTS:
            i += 2
        else:
            i += 1
    if i >= len(argv) or argv[i] != "push":
        return None, False
    return argv[i + 1:], override


def _flags(rest):
    """`(is_force, has_lease, is_dry_run, is_delete, is_refset)` for a push."""
    force = lease = dry = delete = refset = False
    skip = False
    for tok in rest:
        if skip:
            skip = False
            continue
        if tok in PUSH_VALUE_OPTS:
            skip = True
            continue
        if tok == "--force" or tok == "-f":
            force = True
        elif tok.startswith("--force-with-lease"):
            lease = True
        elif tok in ("--dry-run", "-n"):
            dry = True
        elif tok in ("--delete", "-d"):
            delete = True
        elif tok in ("--mirror", "--all"):
            refset = True
        elif SHORT_CLUSTER.match(tok):
            if "f" in tok:
                force = True
            if "n" in tok:
                dry = True
            if "d" in tok:
                delete = True
    return force, lease, dry, delete, refset


def _git(args, timeout=8):
    """Run a git command; return stdout on success, else None."""
    try:
        out = subprocess.run(["git"] + args, capture_output=True, text=True,
                             timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _target(rest):
    """`(remote, branch)` the push is aimed at, or `(None, None)`.

    Handles the shapes that actually occur: a bare `git push`, `git push
    origin`, `git push origin HEAD`, `git push -u origin HEAD`, `git push
    origin HEAD:branch`, and a leading `+` on the refspec.
    """
    positional = []
    skip = False
    for tok in rest:
        if skip:
            skip = False
            continue
        if tok in PUSH_VALUE_OPTS:
            skip = True
            continue
        if tok.startswith("-"):
            continue
        positional.append(tok)

    head = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    head = head.strip() if head else None
    if head == "HEAD":
        head = None  # detached; no branch to reason about

    remote = positional[0] if positional else None
    if remote is None:
        remote = "origin"
        if head:
            up = _git(["config", "--get", f"branch.{head}.remote"])
            if up and up.strip():
                remote = up.strip()

    if len(positional) < 2:
        return remote, head

    spec = positional[1].lstrip("+")
    dst = spec.split(":", 1)[1] if ":" in spec else spec
    dst = dst.rsplit("/", 1)[-1] if dst.startswith("refs/heads/") else dst
    if dst in ("HEAD", ""):
        dst = head
    return remote, dst


DENY = (
    "This is a bare `git push --force`. It overwrites the remote branch tip "
    "unconditionally -- including commits pushed by another agent since you "
    "last looked.\n\n"
    "  command:  {segment}\n\n"
    "A branch you cut, whose PR you opened, and whose review you are driving "
    "is exactly the branch this happens on: ownership is what suppresses the "
    "check. The `@claude` agent pushes to your branch on PR activity, a "
    "second CLI session can claim the same PR, and a human can push to it -- "
    "`shared/workflow/claim-pr.md` records all three.\n\n"
    "Use the lease instead:\n\n"
    "    git push --force-with-lease --force-if-includes\n\n"
    "`--force-with-lease` refuses when the remote tip is not the one your "
    "remote-tracking ref names. `--force-if-includes` (git 2.30+) is the half "
    "usually left off, and without it the lease is defeatable: the lease "
    "compares against your remote-tracking ref, so ANY background `git fetch` "
    "-- a poller, another tool in the same checkout, a `--recurse-submodules` "
    "fetch -- silently refreshes that ref, and the lease then passes over the "
    "very commits it existed to protect. `--force-if-includes` additionally "
    "requires that those commits are reachable from what you are pushing.\n\n"
    "Where the remote ref does not exist, the lease succeeds trivially -- so "
    "this is never the worse command.\n\n"
    "The one case that genuinely needs bare `--force` is a lease that is "
    "UNSATISFIABLE rather than violated: `memories/git.md` records "
    "`--force-with-lease` failing with `stale info` after a squash-merge with "
    "auto-delete removed the branch your ref still names. For that, and for "
    "any other deliberate override, prefix the command with "
    "`ALLOW_FORCE_PUSH=1` (a real env assignment, not a mention)."
)

WARN_HEAD = (
    "Checked `{remote}/{branch}` just now with `git ls-remote`: its tip is "
    "**{tip}**, which is NOT an ancestor of your local HEAD ({local}).\n\n"
    "  command:  {segment}\n\n"
)

WARN_KNOWN = (
    "{n} commit(s) on the remote are not in what you are about to push:\n\n"
    "{commits}\n\n"
)

WARN_UNKNOWN = (
    "That commit is not in your local object store at all, which is the "
    "sharper signal rather than the weaker one: the remote moved after your "
    "last fetch and you cannot see what is there.\n\n"
)

WARN_TAIL = (
    "Somebody else is driving this branch -- most likely the `@claude` agent "
    "reacting to PR activity, or a second session that claimed the PR. A "
    "plain push will be rejected; a forced one would discard the commits "
    "above.\n\n"
    "Reconcile rather than overwrite:\n\n"
    "    git fetch origin {branch}\n"
    "    git log --oneline HEAD..origin/{branch}\n"
    "    git merge origin/{branch}      # or rebase, if the branch is yours alone\n\n"
    "Before deciding it is your own earlier work, compare trees and parents -- "
    "`shared/workflow/claim-pr.md` distinguishes an identical merge (reset onto "
    "it) from a differently-resolved one (merge the two commits, never reset)."
)


def _describe(local, tip, limit=10):
    """Formatted commit list for `local..tip`, or None if the object is absent."""
    if _git(["cat-file", "-e", tip + "^{commit}"], timeout=5) is None:
        return None
    out = _git(["log", "--format=    %h  %an, %ar  %s", f"{local}..{tip}"],
               timeout=5)
    if out is None:
        return None
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if not lines:
        return None
    shown = lines[:limit]
    text = "\n".join(shown)
    if len(lines) > limit:
        text += f"\n    ... and {len(lines) - limit} more"
    return len(lines), text


def evaluate(command):
    """`('deny', reason)`, `('warn', context)`, or `None`."""
    cmds = _simple_commands(command)
    if cmds is None:
        return None

    for argv in cmds:
        rest, override = _push_argv(argv)
        if rest is None:
            continue
        force, lease, dry, delete, refset = _flags(rest)
        if dry or delete or refset:
            continue
        segment = " ".join(argv)

        if force and not lease and not override:
            return "deny", DENY.format(segment=segment)

        remote, branch = _target(rest)
        if not remote or not branch:
            continue

        ls = _git(["ls-remote", "--heads", remote, branch], timeout=8)
        if not ls or not ls.strip():
            continue  # ref absent remotely, or the read failed -- fail open
        tip = ls.split()[0]

        local = _git(["rev-parse", "HEAD"], timeout=5)
        if not local:
            continue
        local = local.strip()
        if tip == local:
            continue

        anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip, "HEAD"],
            capture_output=True, text=True, timeout=5)
        if anc.returncode == 0:
            continue  # plain fast-forward; nothing at risk

        body = WARN_HEAD.format(remote=remote, branch=branch, tip=tip[:12],
                                local=local[:12], segment=segment)
        described = _describe(local, tip)
        if described:
            n, commits = described
            body += WARN_KNOWN.format(n=n, commits=commits)
        else:
            body += WARN_UNKNOWN
        body += WARN_TAIL.format(branch=branch)
        return "warn", body

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail open, but say so
        print(f"no-clobbering-push: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        verdict = evaluate(command)
    except Exception as exc:  # fail open on any parse or subprocess trouble
        print(f"no-clobbering-push: could not evaluate command ({exc})",
              file=sys.stderr)
        return 0

    if verdict is None:
        return 0

    kind, text = verdict
    hso = {"hookEventName": "PreToolUse"}
    if kind == "deny":
        hso["permissionDecision"] = "deny"
        hso["permissionDecisionReason"] = text
    else:
        hso["additionalContext"] = text
    print(json.dumps({"hookSpecificOutput": hso}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
