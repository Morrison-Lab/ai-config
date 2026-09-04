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

`ALLOW_FORCE_PUSH=1` is the escape hatch, and it is deliberately not tied to a
worked example. The case that looks like it needs one is not: `memories/git-branches.md`
records `--force-with-lease` failing with `stale info` after a squash-merge with
auto-delete removed the branch, and says the lease is unsatisfiable rather than
violated, so a PLAIN push is the fix and `--force` is unnecessary. That is
consistent with the paragraph above -- where the remote ref does not exist,
there is nothing for any force to overwrite. So the hatch exists for a case this
guard did not foresee, not for a known one.

The refusal also does NOT consult `--force-with-lease`, because `--force`
disables the lease check. Git's documentation for `-f, --force` says so, and
the two wordings in circulation differ enough to be worth attributing:

  upstream master (Documentation/git-push.adoc) --- "This flag disables that
  check, the other safety checks in PUSH RULES below, and the checks in
  `--force-with-lease`."

  the man page shipped with git 2.50.1 --- "when --force-with-lease option is
  used, the command refuses to update a remote ref whose current value does not
  match what is expected. / This flag disables these checks"

So `--force --force-with-lease` is a plain force push, and treating the lease
as clearing the refusal was a bypass rather than a nicety.

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

  - remote ref absent            -> nothing to collide with; silent
  - remote tip == the pushed ref -> already pushed; silent
  - remote tip is an ancestor    -> fast-forward; silent (the common case, so
                                    the hook stays quiet in normal operation)
  - remote tip is NOT an ancestor of the pushed ref -> WARN, say what is at risk

The local side of every comparison above is the ref being PUSHED, which is
`HEAD` only when the refspec says so -- see `_target`'s docstring. The warning
names it explicitly rather than saying "HEAD", because on `git push origin
feature-x` from `main` the two are different branches.

In that last case the hook tries to describe the divergent commits. Whether it
can turns on one thing worth distinguishing in the report:

  - the object IS present locally (a prior fetch brought it): list the commits
    with their authors and dates, so a parallel session is nameable.
  - the object is NOT present locally: that is the sharper signal, not the
    weaker one -- the remote moved since your last fetch and you cannot even
    see what is there. Say exactly that.

## Where the reading is taken

`HEAD` is per-worktree, so WHERE the local ref is resolved is part of the
reading rather than an implementation detail. Resolving it in the session's
own directory made every cross-worktree push report a divergence that did not
exist: a session sitting in one worktree, pushing from another, was told that
its own commits of a few minutes earlier belonged to somebody else, and was
prescribed a `git merge origin/<branch>` that would have merged a branch into
itself (ai-config#2451).

So each push is read in the directory it actually runs in: the payload's
`cwd`, moved by any `cd` earlier in the same compound command, then moved
again by the push's own `git -C`. When a `cd` cannot be resolved statically
--- `cd -`, a directory stack, an unexpanded variable --- the directory is
INDETERMINATE and the reading is declined, because a reading taken in the
wrong repository is worse than no reading at all. That is the same choice
`_target` already makes when the destination is not a single named branch.

One narrower gap remains, stated rather than papered over: `_simple_commands`
models no nesting, so a `cd` inside a subshell --- `(cd elsewhere && git
push)` --- is applied to that push, correctly, and then leaks past the closing
parenthesis onto any later push in the same command.
`no-push-without-self-review.py` tracks parenthesis depth for exactly this and
is the fuller treatment; matching it here means a second structural parser, so
this file resolves the unnested case and carries the leak knowingly.

## The match condition

  M1  the tool is `Bash` and `tool_input.command` parses into simple commands
  M2  one of those is `git push`, after skipping env assignments, lead words,
      and `git`'s own global options (`-C <dir>`, `-c <cfg>`, `--git-dir=...`)
  M3  it is not a `--dry-run` / `-n` push (which transfers nothing)
  M4  it is not a `--delete` / `-d` push (branch deletion is
      `skills/clean-branches`' territory, not this guard's)

Deny additionally requires a `--force` or `-f` token and no
`ALLOW_FORCE_PUSH=1` prefix. It deliberately does NOT look at
`--force-with-lease`, for the reason given above: `--force` disables the lease
check, so the pair is a plain force push.

`--mirror` and `--all` are deliberately out of scope: they push ref sets rather
than one branch, so the single-branch reading below would misdescribe them.

Fails OPEN on any parse trouble, outside a git repository, when `git` or the
network is unreachable, and on any `ls-remote` timeout.
"""
from __future__ import annotations

import json
import os
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

# `git`'s own global options that consume the following token, skipped before
# `push` is looked for so `git -C /repo push` matches.
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                  "--exec-path"}

# `git push` long options that consume the FOLLOWING token when written without
# `=`. `--repo` is in here AND is read back out in `_target`, because its value
# IS the remote -- skipping it as a mere value was a defect: `git push --repo
# origin HEAD` was resolved against the current branch's configured remote
# rather than against `origin`.
LONG_VALUE_OPTS = {"--push-option", "--repo", "--receive-pack", "--exec",
                   "--recurse-submodules"}

# Every `git push` short option, taken from `git push -h` rather than guessed:
# -4 -6 -d -f -n -o -q -u -v. Only `-o` consumes a value, and that is what makes
# a cluster like `-fo ci.skip` dangerous: it is accepted bash, it IS a force
# push, and a matcher that does not know `o` swallows a value both misses the
# force and mistakes `ci.skip` for the remote.
SHORT_BOOL = {"4": None, "6": None, "d": "delete", "f": "force",
              "n": "dry_run", "q": None, "u": None, "v": None}
SHORT_VALUE = {"o"}

# Long options this guard cares about, and their negations. EVERY `git push`
# option has a `--[no-]` form, so a positive-only scan is order-blind:
# `git push --dry-run --no-dry-run --force` really does transfer, and reading
# only the `--dry-run` made the guard skip a live force push.
LONG_FLAG = {
    "--force": "force",
    "--dry-run": "dry_run",
    "--delete": "delete",
    "--mirror": "refset",
    "--all": "refset",
    "--branches": "refset",   # `git push -h`: "alias of --all"
}


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


def _lead_prefix(argv):
    """`(index of the first real word, whether the override was assigned)`.

    Shared with the `cd` scan in `evaluate`, which has to skip the same env
    assignments and shell lead words: a `cd` behind a keyword
    (`while true; do cd other; git push`) is the retry-loop shape
    `skills/push/SKILL.md` prescribes, so it is reachable by ordinary use.
    """
    i = 0
    override = False
    while i < len(argv) and (ASSIGNMENT.match(argv[i]) or argv[i] in LEAD_WORDS):
        if argv[i].startswith(OVERRIDE + "="):
            override = argv[i].split("=", 1)[1].strip() == "1"
        i += 1
    return i, override


def _push_argv(argv):
    """The `push`-and-after tokens of a `git push` simple command, whether the
    command was prefixed with the override, and its own `-C` values.
    `(None, False, ())` if this argv is not a `git push`.

    The `-C` values are collected rather than merely skipped because they move
    the directory the push runs in, and `HEAD` is per-worktree -- so
    `git -C <other-worktree> push origin HEAD` resolved against the session's
    own `HEAD` reads an unrelated branch. Git applies each `-C` relative to the
    last, so they are kept in order rather than reduced to the first.
    """
    i, override = _lead_prefix(argv)
    if i >= len(argv) or argv[i] != "git":
        return None, False, ()
    i += 1
    # Skip git's own global options, keeping the `-C` values.
    cdirs = []
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] in GIT_VALUE_OPTS:
            if argv[i] == "-C" and i + 1 < len(argv):
                cdirs.append(argv[i + 1])
            i += 2
        else:
            i += 1
    if i >= len(argv) or argv[i] != "push":
        return None, False, ()
    return argv[i + 1:], override, tuple(cdirs)


# `cd` moves the directory a later push runs in; `pushd`/`popd` move it too,
# and this scan does not simulate a directory stack, so they are recognized
# only in order to DECLINE.
CD_WORDS = ("cd", "pushd", "popd")


def _resolve_cd(argv, cur):
    """The directory `argv` leaves the shell in, or `None` for indeterminate.

    `None` is a real answer rather than a failure: the caller declines the
    reading instead of falling back to the session's own directory, which is
    the substitution this resolution exists to stop.

    Deliberately narrower than `no-push-without-self-review.py`'s
    `_resolve_cd_target`, which resolves the same grammar for a different
    guard. Importing it would give this hook a dependency on a sibling that
    execs a sibling of its own, in a process that starts on every Bash call,
    and the import would fail wherever this file runs as a copy -- including
    this hook's own mutation harness, where the failure would read as a
    behaviour change rather than a missing import. So the forms below are
    resolved the same way and every other form is declined rather than
    guessed.
    """
    if argv[0] != "cd":
        return None  # a directory stack this scan does not simulate
    target = None
    for i, tok in enumerate(argv[1:], start=1):
        if tok == "--":
            target = argv[i + 1] if i + 1 < len(argv) else None
            break
        if tok.startswith("-") and tok != "-":
            continue  # `-P`, `-L`, `-e`, `-@` take no value
        target = tok
        break
    if target is None or target == "-":
        return None  # bare `cd` goes home; `cd -` needs OLDPWD
    if "$" in target or "`" in target:
        return None  # unexpanded; resolving it means simulating the shell
    if target.startswith("~"):
        target = os.path.expanduser(target)
        if target.startswith("~"):
            return None  # an unknown user
    if os.path.isabs(target):
        return os.path.normpath(target)
    if cur is None:
        return None
    return os.path.normpath(os.path.join(cur, target))


def _push_cwd(cur, cdirs):
    """Where a push carrying `cdirs` runs, or `None` for indeterminate."""
    for d in cdirs:
        if os.path.isabs(d):
            cur = os.path.normpath(d)
        elif cur is None:
            return None
        else:
            cur = os.path.normpath(os.path.join(cur, d))
    return cur


def _parse_push(rest):
    """Parse a `git push` argument list.

    Returns `(flags, positionals, repo_opt, ok)`.

    `ok` is False when a token could not be classified --- an unrecognized
    short cluster, whose letters might or might not consume the next word. The
    force scan still runs on a not-ok parse (erring toward the refusal, which
    is cheap), while destination resolution does not (erring toward silence,
    since a wrong remote is worse than no remote).
    """
    flags = {"force": False, "lease": False, "dry_run": False,
             "delete": False, "refset": False}
    positionals, repo_opt, ok = [], None, True
    i, end_of_opts = 0, False

    while i < len(rest):
        tok = rest[i]
        i += 1

        if end_of_opts or not tok.startswith("-") or tok == "-":
            positionals.append(tok)
            continue
        if tok == "--":
            end_of_opts = True
            continue

        if tok.startswith("--"):
            name, sep, inline = tok.partition("=")
            negated = name.startswith("--no-")
            base = "--" + name[len("--no-"):] if negated else name

            if base == "--force-with-lease" or name.startswith("--force-with-lease"):
                flags["lease"] = not negated
                continue
            if base in LONG_FLAG:
                flags[LONG_FLAG[base]] = not negated
                continue
            if base in LONG_VALUE_OPTS:
                value = inline if sep else (rest[i] if i < len(rest) else None)
                if not sep:
                    i += 1
                if base == "--repo" and not negated:
                    repo_opt = value
                continue
            continue  # any other long option is a boolean we do not care about

        # A short cluster. Scan left to right; a value-taking letter consumes
        # the cluster's remainder, or the next word when it is the last letter.
        letters = tok[1:]
        for pos, ch in enumerate(letters):
            if ch in SHORT_VALUE:
                if pos == len(letters) - 1:
                    i += 1  # its value is the next word, not the remote
                break
            if ch not in SHORT_BOOL:
                ok = False
                break
            field = SHORT_BOOL[ch]
            if field:
                flags[field] = True

    return flags, positionals, repo_opt, ok


def _git(args, timeout=8, cwd=None):
    """Run a git command in `cwd`; return stdout on success, else None.

    A `cwd` that does not exist raises `FileNotFoundError`, an `OSError`, so a
    stale directory fails open here like every other trouble.
    """
    try:
        out = subprocess.run(["git"] + args, capture_output=True, text=True,
                             timeout=timeout, cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _target(positionals, repo_opt, cwd):
    """`(remote, branch, source, on_source)` the push is aimed at, or all-`None`.

    Handles the shapes that occur: a bare `git push`, `git push origin`,
    `git push origin HEAD`, `git push origin <branch>`, `git push -u origin
    HEAD`, `git push origin HEAD:branch`, a leading `+`, and `--repo
    <repository>`.

    `source` is the LOCAL ref being pushed, and it is not always `HEAD`.
    `git push origin feature-x` run while `main` is checked out pushes local
    `feature-x`, so comparing the remote tip against `HEAD` compares it against
    the wrong branch -- silently, and in both directions: a remote commit that
    happens to be an ancestor of `main` reads as a fast-forward while local
    `feature-x` genuinely diverges, which is a false negative in the exact
    situation this guard exists for.

    `on_source` says whether the ref being pushed IS the checked-out one, and
    it is computed by comparing `source` against the resolved head rather than
    by testing `source == "HEAD"`. Those differ: the `"HEAD"` sentinel appears
    only when the refspec omits a source, so `git push origin main` run on
    `main` yields `source == "main"` -- it would fail a sentinel test while
    being the same branch, and the advice would then tell a reader to check out
    the branch they are already on.

    Returns all-`None` rather than a guess whenever the destination is not a
    single named branch --- a wildcard refspec, a deletion refspec, or a
    detached HEAD with nothing to name. A wrong branch here would send
    `ls-remote` at the wrong ref and report on something the push never
    touches, which is worse than reporting nothing.
    """
    head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    head = head.strip() if head else None
    if head == "HEAD":
        head = None  # detached; no branch to reason about

    # `--repo <repository>` names the remote when no positional one does, so
    # the first positional is then the refspec rather than the remote.
    if repo_opt:
        remote, specs = repo_opt, positionals
    elif positionals:
        remote, specs = positionals[0], positionals[1:]
    else:
        remote, specs = None, []

    if remote is None:
        remote = "origin"
        if head:
            up = _git(["config", "--get", f"branch.{head}.remote"], cwd=cwd)
            if up and up.strip():
                remote = up.strip()

    if not specs:
        return remote, head, "HEAD", True
    if len(specs) > 1:
        return None, None, None, None  # several refspecs; no branch

    spec = specs[0].lstrip("+")
    if ":" in spec:
        src, dst = spec.split(":", 1)
    else:
        src = dst = spec
    if dst.startswith("refs/heads/"):
        dst = dst[len("refs/heads/"):]
    if dst == "HEAD":
        dst = head
    return remote, dst, src, src in ("HEAD", head)


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
    "checks the remote-tracking tip against the local branch's REFLOG, so a "
    "fetch you never saw no longer satisfies the lease.\n\n"
    "Where the remote ref does not exist, the lease succeeds trivially -- so "
    "this is never the worse command.\n\n"
    "A `stale info` refusal is NOT a reason to force. `memories/git-branches.md` "
    "records that case -- a squash-merge with auto-delete removed the branch "
    "your ref still names -- and states that the lease is unsatisfiable "
    "rather than violated, so `--force` is unnecessary and there is nothing "
    "to race. One read settles it: `git ls-remote --heads origin <branch>`, "
    "where empty output means the next push CREATES the branch, so a plain "
    "push is the fix (or `git fetch --prune` and a retry).\n\n"
    "`ALLOW_FORCE_PUSH=1` (a real env assignment, not a mention) is an escape "
    "valve for a case this guard did not foresee, not a shortcut for a known "
    "one. If you reach for it, say what the lease refused and why forcing is "
    "right -- and if the answer is `stale info`, it is not."
)

WARN_HEAD = (
    "Checked `{remote}/{branch}` just now with `git ls-remote`: its tip is "
    "**{tip}**, which is NOT an ancestor of {srclabel} ({local}).\n\n"
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
    "{reconcile}\n"
    "Before deciding it is your own earlier work, compare trees and parents -- "
    "`shared/workflow/claim-pr.md` distinguishes an identical merge (reset onto "
    "it) from a differently-resolved one (merge the two commits, never reset)."
)


def _describe(local, tip, cwd, limit=10):
    """Formatted commit list for `local..tip`, or None if the object is absent."""
    if _git(["cat-file", "-e", tip + "^{commit}"], timeout=5, cwd=cwd) is None:
        return None
    out = _git(["log", "--format=    %h  %an, %ar  %s", f"{local}..{tip}"],
               timeout=5, cwd=cwd)
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


def evaluate(command, base_cwd=None):
    """`('deny', reason)`, `('warn', context)`, or `None`.

    `base_cwd` is the directory the Bash call starts in -- the payload's own
    `cwd` -- and a `cd` earlier in the same compound command moves it, as the
    push's own `git -C` moves it again. It is threaded through every read
    below rather than left to the hook process's own directory, because `HEAD`
    is per-worktree and this guard's whole output is a comparison against it.

    TWO passes over the compound command, deliberately, and the refusal pass
    runs first.

    A single pass returning on the first verdict let a `warn` on an earlier
    push suppress the `deny` a later one deserved:
    `git push origin diverged; git push --force origin mine` returned `warn`,
    which attaches context and does NOT block, so the bare force push ran.
    A refusal blocks the whole Bash call regardless of position, so scanning
    every simple command for one before reporting any warning is both correct
    and cheaper -- the refusal is decided from the command text alone and
    spends no network read.
    """
    cmds = _simple_commands(command)
    if cmds is None:
        return None

    parsed = []
    cwd = base_cwd or os.getcwd()
    for argv in cmds:
        head = argv[_lead_prefix(argv)[0]:]
        if head and head[0] in CD_WORDS:
            cwd = _resolve_cd(head, cwd)
            continue
        rest, override, cdirs = _push_argv(argv)
        if rest is None:
            continue
        flags, positionals, repo_opt, ok = _parse_push(rest)
        parsed.append((argv, flags, positionals, repo_opt, ok, override,
                       _push_cwd(cwd, cdirs)))

    # Pass 1 -- refusal. Lexical, so no network read, and any command in the
    # compound counts. It is deliberately blind to the directory: `--force` is
    # a force push wherever it runs, so nothing about the refusal depends on
    # resolving one.
    for argv, flags, _pos, _repo, _ok, override, _cwd in parsed:
        if flags["force"] and not flags["dry_run"] and not override:
            return "deny", DENY.format(segment=" ".join(argv))

    # Pass 2 -- the reading. Only reached when nothing is refused.
    for argv, flags, positionals, repo_opt, ok, _override, cwd in parsed:
        segment = " ".join(argv)

        # An indeterminate directory declines the reading rather than falling
        # back to the hook's own. A comparison against the wrong repository is
        # exactly what ai-config#2451 reported, and it is worse than silence:
        # it names a cause and prescribes a merge.
        if cwd is None:
            continue

        # Everything below reports on ONE branch, so anything that is not one
        # ordinary branch push is out of scope rather than guessed at.
        if flags["dry_run"] or flags["delete"] or flags["refset"] or not ok:
            continue

        remote, branch, source, on_source = _target(positionals, repo_opt, cwd)
        if not remote or not branch:
            continue
        # `source` is deliberately NOT tested for emptiness here. An empty
        # source is `git push origin :main`, a deletion, and the `rev-parse
        # --verify` below already declines it (`^{commit}` resolves to
        # nothing). Testing it twice would leave whichever check ran first
        # untestable, which is what the removed wildcard guard did.

        # Resolve the LOCAL side first, before spending a network read.
        #
        # It is the ref being PUSHED, which is `HEAD` only when the refspec
        # says so. Resolving it as `HEAD` unconditionally compared
        # `origin/feature-x` against `main` on any `git push origin
        # feature-x`, and read a remote commit that happened to be an ancestor
        # of `main` as a fast-forward -- a false negative in the exact
        # situation this guard exists for.
        #
        # It doubles as the "is this one ordinary branch" test, which is why
        # there is no separate check for a deletion or wildcard refspec: the
        # source of `origin :main` is empty and the source of
        # `refs/heads/*:refs/heads/*` contains a `*`, and `git rev-parse
        # --verify` resolves neither (measured: both exit 1 with no output).
        local = _git(["rev-parse", "--verify", "--quiet", source + "^{commit}"],
                     timeout=5, cwd=cwd)
        if not local:
            continue  # names no single local ref -- fail open, no network read
        local = local.strip()

        ls = _git(["ls-remote", "--heads", remote, branch], timeout=8, cwd=cwd)
        if not ls or not ls.strip():
            continue  # ref absent remotely, or the read failed -- fail open
        tip = ls.split()[0]

        if tip == local:
            continue

        anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip, local],
            capture_output=True, text=True, timeout=5, cwd=cwd)
        if anc.returncode == 0:
            continue  # plain fast-forward; nothing at risk

        # Name the ref actually compared. Saying "your local HEAD" here was
        # wrong in precisely the case the source-ref fix exists for: on
        # `git push origin feature-x` from `main` it labelled `feature-x`'s
        # tip as HEAD, so a reader would reconcile against the wrong branch.
        srclabel = ("your local HEAD" if source == "HEAD"
                    else f"your local `{source}`")
        body = WARN_HEAD.format(remote=remote, branch=branch, tip=tip[:12],
                                local=local[:12], segment=segment,
                                srclabel=srclabel)
        described = _describe(local, tip, cwd)
        if described:
            n, commits = described
            body += WARN_KNOWN.format(n=n, commits=commits)
        else:
            body += WARN_UNKNOWN
        # The remediation commands must operate on the ref being pushed, for
        # the same reason the label above does. Emitting
        # `git merge origin/feature-x` while `main` is checked out merges
        # `feature-x`'s remote content INTO `main` -- wrong branch, and
        # destructive, in precisely the scenario this guard exists for.
        if on_source:
            reconcile = (f"    git fetch origin {branch}\n"
                         f"    git log --oneline {source}..origin/{branch}\n"
                         f"    git merge origin/{branch}"
                         "      # or rebase, if the branch is yours alone\n")
        else:
            reconcile = (f"    git fetch origin {branch}\n"
                         f"    git log --oneline {source}..origin/{branch}\n"
                         f"    git checkout {source}"
                         "      # you are not on the branch being pushed\n"
                         f"    git merge origin/{branch}"
                         "      # or rebase, if the branch is yours alone\n")
        body += WARN_TAIL.format(branch=branch, reconcile=reconcile)
        return "warn", body

    return None


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True

    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"no-clobbering-push: unreadable hook input ({exc})",

              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input") or {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script")
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    try:
        verdict = evaluate(command, payload.get("cwd"))
    except Exception as exc:  # fail open on any parse or subprocess trouble
        print(f"no-clobbering-push: could not evaluate command ({exc})",
              file=sys.stderr)
        return 0

    if verdict is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
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
