#!/usr/bin/env python3
"""PreToolUse guard: a bare `git stash pop` or `apply` in a repository with
more than one worktree.

`refs/stash` is shared by every worktree, so a bare pop takes `stash@{0}`,
whoever pushed it (ai-config#1907, #3584); a clean foreign pop drops the entry
and exits 0. Denies `git stash pop|apply` with no argument but options and
redirections, run (after `cd`/`pushd`/`popd`, `git -C`, and inside `sh -c`)
in a repository with more than one live worktree. `-h`/`--help` and a named
entry, even `stash@{0}`, pass. `ALLOW_BARE_STASH_POP=1` clears it. Fails open
when shellcmd cannot load, the line does not parse, `--git-dir`,
`--work-tree` or `GIT_DIR` redirect the repository, or `git worktree list`
fails. Rule: [`shared-git-state`](../shared/workflow/shared-git-state.md).
"""

import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
try:
    _LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (simple_commands_with_scope, strip_env, walk_dirs,
                          git_subcommand, env_value, nested_shell_commands,
                          GIT_VALUE_OPTS)
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-bare-stash-pop: shellcmd did not load ({_exc})", file=sys.stderr)
    simple_commands_with_scope = None

SHELL_TOOLS = {"Bash", "bash", "run_command", "execute_command", "terminal", "shell"}
OVERRIDE = "ALLOW_BARE_STASH_POP"
TAKERS = frozenset({"pop", "apply"})
# A redirection token: group 1 is its target when attached (`>f`, `2>&1`).
REDIR = re.compile(r"^(?:\d+|&)?(?:>>|>&|<&|<<<|<<|>|<)(.*)$")

DENY = (
    "Refused: `{segment}` names no stash entry, and this repository has "
    "{count} worktrees sharing one stash stack, so the top entry may be "
    "another session's (ai-config#1907). Apply by the SHA you recorded after "
    "`git stash push -u -m \"<tag>\"`, or use `git worktree add --detach` or "
    "`git show <ref>:<path>` for a baseline. Override: ALLOW_BARE_STASH_POP=1."
    " Rule: shared/workflow/shared-git-state.md.")


def _git_dir_opt(argv):
    """`(dirs, ok)`: the command's `git -C` values in order, and False when
    `--git-dir` or `--work-tree` redirect the repository."""
    _env, rest = strip_env(argv)
    dirs, i = [], 1
    while i < len(rest) and rest[i].startswith("-"):
        opt = rest[i]
        if opt.split("=")[0] in ("--git-dir", "--work-tree"):
            return dirs, False
        if opt == "-C" and i + 1 < len(rest):
            dirs.append(rest[i + 1])
        i += 2 if opt in GIT_VALUE_OPTS else 1
    return dirs, True


def bare_take(argv):
    """True when `argv` is `git stash pop|apply` naming no entry. shlex leaves
    redirections in argv (`2`, `>&`, `1`, or whole `2>/dev/null`): skip them.
    shlex drops spacing, so `pop 0 > f` reads `0` as an fd and is denied."""
    sub, rest, _env = git_subcommand(argv) or (None, [], None)
    if sub != "stash" or not rest or rest[0] not in TAKERS:
        return False
    args, i = rest[1:], 0
    while i < len(args):
        arg, nxt = args[i], args[i + 1] if i + 1 < len(args) else ""
        redir = REDIR.match(arg)
        if arg.isdigit() and REDIR.match(nxt):
            i += 1
        elif redir:
            i += 1 if redir.group(1) else 2
        elif arg in ("-h", "--help") or not arg.startswith("-"):
            return False
        else:
            i += 1
    return True


def worktree_count(directory):
    """Live worktrees of the repository at `directory`, or None when unknown.
    An entry git marks `prunable` (its directory is gone) is not counted."""
    try:
        proc = subprocess.run(
            ["git", "-C", directory, "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=8, encoding="utf-8")
    except (OSError, subprocess.SubprocessError):
        return None
    blocks = proc.stdout.strip().split("\n\n") if proc.returncode == 0 else None
    return None if blocks is None else sum(
        1 for b in blocks if b.startswith("worktree ") and "\nprunable" not in b)


def evaluate(command, cwd, environ=None, depth=0):
    """The deny reason, or None. A nested `sh -c` line is checked from the
    directory its shell starts in; `eval`, `xargs`, `$VAR` git are not."""
    environ = os.environ if environ is None else environ
    if simple_commands_with_scope is None or environ.get(OVERRIDE) == "1":
        return None
    for argv, env, _rest, cur in walk_dirs(
            simple_commands_with_scope(command) or [], cwd):
        for inner in nested_shell_commands(argv) if depth < 3 else []:
            reason = cur and evaluate(inner, cur, environ, depth + 1)
            if reason:
                return reason
        redirected = any(env_value(env, v) is not None
                         for v in ("GIT_DIR", "GIT_WORK_TREE"))
        if (cur is None or redirected or env_value(env, OVERRIDE) == "1"
                or not bare_take(argv)):
            continue
        dirs, ok = _git_dir_opt(argv)
        for d in dirs:
            cur = os.path.normpath(os.path.join(cur, os.path.expanduser(d)))
        count = worktree_count(cur) if ok else None
        if count is not None and count > 1:
            return DENY.format(segment=" ".join(argv), count=count)
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
        print(f"no-bare-stash-pop: could not evaluate ({exc})", file=sys.stderr)
        return 0
    if not reason:
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
