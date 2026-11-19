#!/usr/bin/env python3
"""PreToolUse guard: a branch change in the main worktree of a repository
that has linked worktrees.

Once a repository has linked worktrees, other sessions and subagents work
beside its main checkout and read it, so its branch and index are shared
state. A `git checkout -B <b>` run from the wrong directory left the main
checkout on a fixer's branch with a stale index (ai-config#4233), and a
switch under a running subagent put a commit on the wrong branch
(ai-config#3204). Denies `git switch` and a branch-changing `git checkout`
(a commit, a branch name only a remote has, `-`, `-b`, `-B`, `-d`,
`--orphan`, `--detach`, stuck or clustered as in `-qb`), run (after `cd`,
`git -C` and inside `sh -c`) in the main worktree while more than one live
worktree exists. Redirections such as `2>&1` are ignored. Path checkouts
(paths after `--`, `-p`, two or more names, one name that is no commit), a
checkout of the current branch, and a remote-only name under `--no-guess`
pass. Backtick substitution and `env -C` are not followed.
`ALLOW_MAIN_CHECKOUT_SWITCH=1` clears one command. Fails open when a helper
cannot load, the line does not parse, the repository is redirected, or git
fails. Rule: [`shared-git-state`](../shared/workflow/shared-git-state.md).
"""

import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
try:
    sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "scripts", "lib"))
    from shellcmd import (simple_commands_with_scope, walk_dirs, git_subcommand,
                          env_value, nested_shell_commands)
    from sibling import load_sibling
    _STASH = load_sibling(__file__, "no-bare-stash-pop.py", "_nbsp")
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-switch-in-main-checkout: helpers did not load ({_exc})", file=sys.stderr)
    _STASH = None

SHELL_TOOLS = {"Bash", "bash", "run_command", "execute_command", "terminal", "shell"}
OVERRIDE = "ALLOW_MAIN_CHECKOUT_SWITCH"
DENY = (
    "Refused: `{segment}` changes the branch of `{top}`, the main worktree of "
    "a repository with {count} worktrees. Other sessions and subagents read "
    "that checkout (ai-config#4233, #3204). Work in a worktree of your own: "
    "`git worktree add <dir> <branch>`. Override: ALLOW_MAIN_CHECKOUT_SWITCH=1."
    " Rule: shared/workflow/shared-git-state.md.")


def git(cwd, *args):
    """stdout of `git -C cwd args`, stripped, or None when it fails."""
    try:
        p = subprocess.run(["git", "-C", cwd, *args], capture_output=True,
                           text=True, timeout=8, encoding="utf-8")
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def without_redirections(rest):
    """`rest` with shell redirections (`2>/dev/null`, `> out`, `2>&1`) and
    their targets removed, since the shell, not git, consumes them."""
    out, i = [], 0
    while i < len(rest):
        redir = _STASH.REDIR.match(rest[i])
        nxt = rest[i + 1] if i + 1 < len(rest) else ""
        if rest[i].isdigit() and _STASH.REDIR.match(nxt):
            i += 1
        elif redir:
            i += 1 if redir.group(1) else 2
        else:
            out.append(rest[i])
            i += 1
    return out


def checkout_option(arg):
    """'branch' when a `git checkout` option changes the branch (`-b`, `-B`,
    `-d`, `--orphan`, `--detach`, alone, stuck or in a cluster such as
    `-qb`), 'paths' when it makes the command a path checkout or help, and
    None otherwise."""
    if arg == "-":
        return "branch"
    if arg.startswith("--"):
        name = arg.split("=", 1)[0]
        if name in ("--orphan", "--detach"):
            return "branch"
        if name in ("--patch", "--help", "--pathspec-from-file"):
            return "paths"
        return None
    for ch in arg[1:]:
        if ch in "bBd":
            return "branch"
        if ch in "ph":
            return "paths"
    return None


def remote_only_branch(cwd, name):
    """True when `name` is no local ref and no path, but names exactly one
    remote-tracking branch, so `git checkout <name>` creates and switches to
    it (git's DWIM guess)."""
    if os.path.exists(os.path.join(cwd, name)):
        return False
    refs = git(cwd, "for-each-ref", "--format=%(refname)",
               f"refs/remotes/*/{name}")
    return bool(refs) and len(refs.splitlines()) == 1


def is_current(cwd, name):
    """True when checking out `name` keeps HEAD where it is: `HEAD`, or the
    name of the branch already checked out. Git special-cases a bare
    `git checkout HEAD`: it leaves HEAD on its branch and does not detach it
    (checked with git 2.43; `HEAD^0` or `--detach` would detach)."""
    return name == "HEAD" or git(cwd, "symbolic-ref", "-q", "--short",
                                 "HEAD") == name


def changes_branch(sub, rest, cwd):
    """True when `git <sub> <rest>` would move HEAD to another branch."""
    rest = without_redirections(rest)
    if sub == "switch":
        return not {"-h", "--help"} & set(rest)
    if sub != "checkout":
        return False
    cut = rest.index("--") if "--" in rest else len(rest)
    kinds = {checkout_option(a) for a in rest[:cut] if a.startswith("-")}
    if "paths" in kinds:
        return False
    if "branch" in kinds:
        return True
    if rest[cut + 1:]:  # `checkout [<tree-ish>] -- <path>...` restores files
        return False
    args = [a for a in rest[:cut] if not a.startswith("-")]
    # `checkout <tree-ish> <path>...` restores files and keeps the branch.
    if len(args) != 1 or is_current(cwd, args[0]):
        return False
    if git(cwd, "rev-parse", "--verify", "-q", args[0] + "^{commit}") is not None:
        return True
    # A name only a remote has makes git create and switch to a tracking branch.
    return "--no-guess" not in rest[:cut] and remote_only_branch(cwd, args[0])


def main_worktree(cwd):
    """`(top, count)` when `cwd` is in the main worktree of a repository with
    more than one live worktree, else None."""
    top = git(cwd, "rev-parse", "--show-toplevel")
    listing = git(cwd, "worktree", "list", "--porcelain")
    count = _STASH.worktree_count(cwd)
    if not top or not listing or not count or count < 2:
        return None
    first = listing.split("\n\n")[0]
    if "\nbare" in first or not first.startswith("worktree "):
        return None
    main = first.splitlines()[0][len("worktree "):]
    return (top, count) if os.path.realpath(main) == os.path.realpath(top) else None


def evaluate(command, cwd, environ=None, depth=0):
    """The deny reason, or None."""
    environ = os.environ if environ is None else environ
    if _STASH is None or environ.get(OVERRIDE) == "1":
        return None
    for argv, env, _rest, cur in walk_dirs(
            simple_commands_with_scope(command) or [], cwd):
        if cur is None or env_value(env, OVERRIDE) == "1" or any(
                env_value(env, v) is not None for v in ("GIT_DIR", "GIT_WORK_TREE")):
            continue
        for inner in nested_shell_commands(argv) if depth < 3 else []:
            reason = evaluate(inner, cur, environ, depth + 1)
            if reason:
                return reason
        sub, rest, _env = git_subcommand(argv) or (None, [], None)
        dirs, ok = _STASH._git_dir_opt(argv)
        for d in dirs:
            cur = os.path.normpath(os.path.join(cur, os.path.expanduser(d)))
        if not ok or not changes_branch(sub, rest, cur):
            continue
        found = main_worktree(cur)
        if found:
            return DENY.format(segment=" ".join(argv), top=found[0], count=found[1])
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") not in SHELL_TOOLS:
        return 0
    inp = payload.get("tool_input")
    command = inp.get("command") if isinstance(inp, dict) else None
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not os.path.isabs(cwd):
        cwd = os.getcwd()
    try:
        reason = evaluate(command, cwd) if isinstance(command, str) else None
    except Exception as exc:  # fail open
        print(f"no-switch-in-main-checkout: could not evaluate ({exc})", file=sys.stderr)
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
