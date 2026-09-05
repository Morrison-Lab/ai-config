#!/usr/bin/env python3
"""PreToolUse guard: a `git push` whose branch conflicts with the default
branch, where the conflict may be a silent REVERSION of a merged sibling PR.

## The incident

`ucdavis/bcs#913`, 2026-09-03. A branch was cut from `main` at 19:23:33Z and
an early edit reflowed a paragraph in `vignettes/articles/simulation.qmd`.
That paragraph was also the subject of `ucdavis/bcs#908`, which the session
had inspected at the start, seen was open, and deliberately DEFERRED TO on
that exact sentence.

#908 merged at 23:55:21Z -- four and a half hours later, mid-session -- as
commit `f36b0c2f`, replacing "known exactly by construction" with a Monte
Carlo standard-error bound. The session's later commits kept editing the
pre-#908 paragraph, so the branch ended up proposing to put back the sentence
#908 had deliberately removed. An adversarial reviewer found it. This command
would have found it first:

    git merge-tree --write-tree origin/main HEAD

## Why the existing guards do not cover this

`no-clobbering-push.py` runs on the same event and asks a genuinely different
question: has the REMOTE BRANCH moved under me. That is a different ref and a
different collision -- it reads `refs/heads/<pushed-branch>` on the remote,
never the base -- so a branch nobody else has touched passes it while
diverging arbitrarily far from `main`.

`shared/workflow/sync-with-main.md`'s opening rule does look at the base, and
frames a moved `main` as STALENESS: a branch falling behind, whose cost is a
merge you owe later. That framing is what makes the warning skippable. The
cost here is not a merge; it is someone else's fix, deleted, in text that
reads as intentional -- a re-added sentence is indistinguishable from a
sentence you meant to write.

## Why it warns rather than blocks

A conflict with the base is frequently legitimate: two branches editing one
region on purpose, a rename, a deliberate revert. Nothing in the command or
the tree says which, and this hook cannot tell a reversion from a genuine
disagreement -- only the author can. Per README's "A hook that misfires is
worse than a missing one", it only ever ADDS context: `additionalContext` and
a `systemMessage`, never `permissionDecision`.

## Why it fetches, and why it fetches ONLY the base

`merge-tree` reads the remote-tracking ref. Against an unfetched
`origin/<base>` it compares HEAD to the `main` you cloned and reports clean,
which is `batch-merge-and-resolve.md`'s detector-that-never-ran: a clean
result and a check that never saw the new commits are the same output. So the
fetch is what makes the check non-vacuous, not a convenience.

A fetch is not free of consequence, though, and the consequence is named in
`shared/workflow/check-before-pushing.md`: a background fetch silently
satisfies a `--force-with-lease`, because the lease compares against the
remote-tracking ref it just refreshed. A guard that fetched the branch being
pushed would defeat the sibling guard's whole protection.

Fetching only the BASE is what avoids that, and it is sound because the lease
for a push of branch X reads `refs/remotes/origin/X` -- never
`refs/remotes/origin/<base>`. The one case where those coincide is a push OF
the base branch itself, which this hook skips outright.

Scoping the fetch by refspec is not an alternative. Measured on git 2.50.1
against two local repositories:

    git fetch origin '+main:refs/ai-config-hooks/base'

still advanced `refs/remotes/origin/main` to the new tip -- git's opportunistic
remote-tracking update happens regardless of the refspec given. So there is no
way to read the base's new tip into the object store without refreshing that
one ref, and the safety argument has to rest on WHICH ref, not on avoiding the
write.

## The match condition

  M1  the tool is `Bash` and the command contains a real `git push` simple
      command, as decided by `no-push-without-self-review.py`'s `iter_pushes`
      -- the same reuse `warn-new-line-breaks-on-push.py` makes, so all three
      guards agree on what counts as a push
  M2  the push's own repository resolves (its `-C`, or the directory a
      `cd`/`pushd` put it in); a `REDIRECTED` push is skipped, since the
      sibling could not say which repository it targets
  M3  a default branch resolves for that repository, from the repository
      itself -- `refs/remotes/origin/HEAD` first, never `origin/main` by
      assumption; `memories/preferences.md` records a measured
      `fatal: invalid reference: origin/main` on a repo whose default is
      named otherwise
  M4  HEAD is not the base branch itself. This half is load-bearing:
      without it, pushing the base warns about its own divergence.
  M4b HEAD is not already at or behind the base. This half is a pure
      short-circuit and guards no correctness case. When HEAD is an
      ancestor of the base, the merge base IS HEAD, so one side of the
      three-way diff is empty by construction and `merge-tree` cannot
      report a conflict whatever the content. Removing it changes no
      verdict, only the cost of a subprocess carrying a 20s timeout.
  M5  `git merge-tree --write-tree origin/<base> HEAD` exits non-zero, whose
      status IS the signal for this form. The legacy three-argument form
      always exits 0, which is why it is not used here

Fails OPEN on any parse trouble, outside a git repository, when `git` is
unreachable, and on any timeout -- consistent with every other guard here.

`ALLOW_BASE_CONFLICT=1` is not offered: the hook never blocks, so there is
nothing to override.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys

# Test seam: pin the base branch name instead of resolving it. Tests set this
# so a fixture repository need not carry a `refs/remotes/origin/HEAD`.
BASE_REF_ENV = "BASE_CONFLICT_BASE_REF"
# Test seam: skip the fetch. Fixtures use local path remotes, so the real
# fetch runs offline in the suite by default; this exists for the fetch-failure
# path, which has to be reachable without breaking the network.
NO_FETCH_ENV = "BASE_CONFLICT_NO_FETCH"

# `git merge-tree`'s conflict lines, e.g.
#   CONFLICT (content): Merge conflict in vignettes/articles/simulation.qmd
RX_CONFLICT = re.compile(r"^CONFLICT \(([^)]+)\): (.*)$", re.M)

MAX_PATHS_SHOWN = 10

# Only consulted after `refs/remotes/origin/HEAD` fails, and each candidate is
# verified to exist before it is used -- so this is a fallback, not a default.
FALLBACK_BASES = ("main", "master", "trunk", "develop", "devel")


def _load_sibling():
    """`no-push-without-self-review.py`, whose `iter_pushes` decides what a
    push is. Loaded by path because the filename is not an identifier."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "no-push-without-self-review.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location(
        "no_push_without_self_review", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


_SIBLING = _load_sibling()

# Marks `--repo` having been seen, so its VALUE is the next token.
_NEXT = object()


def _git(args, cwd=None, timeout=10):
    """Run git; `(returncode, stdout)`, or `None` when it could not run."""
    try:
        res = subprocess.run(["git"] + args, capture_output=True, text=True,
                             cwd=cwd, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.returncode, res.stdout


def _git_ok(args, cwd=None, timeout=10):
    """Stripped stdout on success, else None."""
    got = _git(args, cwd=cwd, timeout=timeout)
    if got is None or got[0] != 0:
        return None
    return got[1].strip()


def _git_root(directory):
    return _git_ok(["rev-parse", "--show-toplevel"], cwd=directory) or None


# `git push` options that consume the NEXT token, so that token is a value
# rather than the positional remote. `--repo` is handled separately because
# its value IS the remote.
_PUSH_VALUE_OPTS = {"-o", "--push-option", "--receive-pack", "--exec"}


def push_remote(argv, cwd):
    """The remote a `git push` actually targets, defaulting to `origin`.

    Mirrors `no-clobbering-push.py`'s `_target`: `--repo <r>` names the remote
    when no positional one does, otherwise the first positional after `push`
    is the remote, otherwise the checked-out branch's configured remote,
    otherwise `origin`.

    Hard-coding `origin` was the earlier behaviour and is wrong in two ways at
    once. Where no `origin` exists the guard finds no base and skips silently,
    and in a fork-style checkout carrying both remotes it compares against a
    base the push was never aimed at. Either way the answer is about a branch
    nobody is pushing.

    `argv` is the token list `iter_pushes` yields, `git push ...` included, so
    this walks past the leading `git`, any pre-command git options, and `push`
    itself before reading positionals.

    `_PUSH_VALUE_OPTS` lists ONLY options whose value is a separate token.
    `--force-with-lease`, `--force-if-includes`, `--signed` and
    `--recurse-submodules` take a value in their `=` form alone, so listing
    them would eat the following token -- which is the remote. Measured while
    writing this: with `--force-with-lease` listed,
    `git push --force-with-lease origin feat/x` resolved to `feat/x`.
    """
    tokens = list(argv)
    while tokens and tokens[0] != "push":
        tokens.pop(0)
    if tokens:
        tokens.pop(0)  # drop `push` itself

    repo_opt = None
    positionals = []
    skip = False
    for tok in tokens:
        if skip:
            skip = False
            continue
        if tok == "--":
            continue
        if tok.startswith("--repo="):
            repo_opt = tok[len("--repo="):]
            continue
        if tok == "--repo":
            repo_opt = _NEXT
            continue
        if repo_opt is _NEXT:
            repo_opt = tok
            continue
        if tok in _PUSH_VALUE_OPTS:
            skip = True
            continue
        if tok.startswith("-"):
            continue
        positionals.append(tok)

    if repo_opt and repo_opt is not _NEXT:
        return repo_opt
    if positionals:
        return positionals[0]

    head = _git_ok(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    if head and head != "HEAD":
        configured = _git_ok(["config", "--get", f"branch.{head}.remote"],
                             cwd=cwd)
        if configured:
            return configured
    return "origin"


def resolve_base_branch(git_root, remote="origin"):
    """The repository's default branch NAME, or None.

    Resolved from the repository rather than assumed. `origin/main` is only
    ever reached through `FALLBACK_BASES`, and only after being verified to
    exist -- the assumption this ordering exists to avoid is the measured
    `fatal: invalid reference: origin/main` on a repo whose default is not
    named `main`.
    """
    pinned = os.environ.get(BASE_REF_ENV, "").strip()
    if pinned:
        return pinned

    prefix = f"{remote}/"
    head = _git_ok(["symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD"],
                   cwd=git_root)
    if head:
        return head[len(prefix):] if head.startswith(prefix) else head

    for name in FALLBACK_BASES:
        if _git_ok(["rev-parse", "--verify", "--quiet",
                    f"refs/remotes/{remote}/{name}^{{commit}}"], cwd=git_root):
            return name
    return None


def _current_branch(git_root):
    name = _git_ok(["rev-parse", "--abbrev-ref", "HEAD"], cwd=git_root)
    return None if not name or name == "HEAD" else name


def conflicting_paths(git_root, base_ref):
    """Paths `merge-tree` reports conflicting between `base_ref` and HEAD.

    `[]` means the merge is clean. `None` means the question could not be
    asked -- git unavailable, the ref missing, a timeout -- which the caller
    treats as silence rather than as an all-clear.

    The `--write-tree` form's EXIT STATUS is the signal: 0 clean, non-zero
    conflicted. The legacy three-argument form always exits 0, so a guard
    keyed on status there can never fire.
    """
    got = _git(["merge-tree", "--write-tree", base_ref, "HEAD"], cwd=git_root,
               timeout=20)
    if got is None:
        return None
    code, out = got
    if code == 0:
        return []
    paths = [m.group(2) for m in RX_CONFLICT.finditer(out)]
    # A non-zero exit with no parsable CONFLICT line is still a conflict --
    # report it rather than swallowing it, since the empty list would read as
    # a clean merge.
    return paths or ["(path not reported by git merge-tree)"]


def _fetch_base(git_root, base, remote="origin"):
    """Refresh `<remote>/<base>` only. True on success.

    Deliberately never fetches the branch being pushed: that ref is what a
    `--force-with-lease` compares against, and refreshing it would satisfy a
    lease over the very commits it exists to protect.
    """
    if os.environ.get(NO_FETCH_ENV, "").strip() == "1":
        return False
    got = _git(["fetch", "--quiet", remote, base], cwd=git_root, timeout=20)
    return got is not None and got[0] == 0


NOTE = (
    "`git merge-tree --write-tree {base_ref} HEAD` reports this branch "
    "CONFLICTS with `{base}`, in {count} file(s):\n\n"
    "{paths}\n\n"
    "{freshness}"
    "The risk here is not the conflict. It is that resolving it toward THIS "
    "branch would silently REVERT whatever a sibling PR merged into `{base}` "
    "while you were working -- and a re-added sentence or restored function "
    "is indistinguishable from one you meant to write, so nothing downstream "
    "flags it. `shared/workflow/sync-with-main.md` records the measured case: "
    "a session deferred to an open PR on one paragraph, that PR merged four "
    "hours later, and the branch went on to propose putting back the exact "
    "sentence it had removed.\n\n"
    "A deferral to another open PR is a claim about LIVE STATE, and it "
    "expires. The record of the decision survives; its premise does not.\n\n"
    "Before pushing, merge the base in and read what the merge did:\n\n"
    "    git merge {base_ref}\n"
    "    git diff <pre-merge-tip> HEAD -- <each conflicting path>\n\n"
    "A line appearing there only as a DELETION, with nothing re-added in the "
    "same hunk, is a fix the resolution discarded. Note that "
    "`git diff {base_ref}...HEAD` cannot show this: a reverted line now "
    "matches the base again, so it produces no diff at all."
)

FRESH_OK = ""
FRESH_STALE = (
    "(The `git fetch {remote} {base}` could not be run, so this compares "
    "against the `{base_ref}` already in your object store. The conflict "
    "reported is real; a CLEAN result would not have been trustworthy.)\n\n"
)


def evaluate(command):
    """`(note, summary)` when a push's branch conflicts with its base, else
    `None`."""
    if _SIBLING is None:
        return None
    try:
        pushes = list(_SIBLING.iter_pushes(command))
    except Exception:
        return None
    if not pushes:
        return None

    redirected = getattr(_SIBLING, "REDIRECTED", object())
    for _env, rest, directory in pushes:
        if directory is redirected:
            continue  # M2: the sibling could not say which repository
        git_root = _git_root(directory if directory is not None else os.getcwd())
        if not git_root:
            continue

        remote = push_remote(rest, git_root)
        base = resolve_base_branch(git_root, remote)  # M3
        if not base:
            continue
        if _current_branch(git_root) == base:
            continue  # M4: pushing the base itself; nothing to compare

        fresh = _fetch_base(git_root, base, remote)
        base_ref = f"{remote}/{base}"
        if not _git_ok(["rev-parse", "--verify", "--quiet",
                        f"{base_ref}^{{commit}}"], cwd=git_root):
            continue

        if _git_ok(["merge-base", "--is-ancestor", "HEAD", base_ref],
                   cwd=git_root) is not None:
            continue  # M4b: HEAD is already contained in the base

        paths = conflicting_paths(git_root, base_ref)  # M5
        if not paths:
            continue  # clean, or unanswerable -- both stay silent

        shown = paths[:MAX_PATHS_SHOWN]
        listing = "\n".join(f"    {p}" for p in shown)
        if len(paths) > len(shown):
            listing += f"\n    ... and {len(paths) - len(shown)} more"

        note = NOTE.format(
            base=base, base_ref=base_ref, count=len(paths), paths=listing,
            freshness=(FRESH_OK if fresh
                       else FRESH_STALE.format(base=base, base_ref=base_ref,
                                               remote=remote)),
        )
        summary = (
            f"`git push` carries a branch that conflicts with `{base}` in "
            f"{len(paths)} file(s); resolving toward this branch could revert "
            "a merged sibling PR."
        )
        return note, summary

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"flag-conflict-with-base: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0

    if not isinstance(payload, dict) or payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell"
    ):
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = (
        tool_input.get("command")
        or tool_input.get("CommandLine")
        or tool_input.get("cmd")
        or tool_input.get("script")
    )
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        verdict = evaluate(command)
    except Exception as exc:
        print(f"flag-conflict-with-base: evaluation failed ({exc})",
              file=sys.stderr)
        return 0

    if verdict is None:
        return 0

    note, summary = verdict
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
        "systemMessage": summary,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
