#!/usr/bin/env python3
"""PreToolUse guard: a `git add` that would stage an embedded repository,
such as a worktree-isolated agent under `.claude/worktrees/`, as a gitlink no
clone can resolve (ai-config#3884). Read-only: `git ls-files -o` on the add's
own pathspecs lists an untracked repository as `dir/`, and it takes no index
lock. `-u` and `--pathspec-from-file` are not checked. `ALLOW_SCRATCH_ADD=1`
clears one command. Fails open when a helper cannot load, the line does not
parse, `--git-dir`, `--work-tree`, `GIT_DIR` or `GIT_WORK_TREE` redirect the
repository, or git fails.
Rule: [`shared-git-state`](../shared/workflow/shared-git-state.md).
"""

import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
try:
    sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "scripts", "lib"))
    from shellcmd import (simple_commands_with_scope, walk_dirs,
                          git_subcommand, env_value)
    from sibling import load_sibling
    _STASH = load_sibling(__file__, "no-bare-stash-pop.py", "_nbsp")
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-add-sweeping-scratch: helpers did not load ({_exc})", file=sys.stderr)
    _STASH = None

SHELL_TOOLS = {"Bash", "bash", "run_command", "execute_command", "terminal", "shell"}
OVERRIDE = "ALLOW_SCRATCH_ADD"
EMBEDDED = (
    "Refused: `{segment}` would stage `{path}`, which holds its own `.git`, as "
    "a gitlink no clone can resolve (ai-config#3884). Ignore it (agents live "
    "under `.claude/worktrees/`), or name the paths you mean to add.")
FOOTER = (" Override for one command: ALLOW_SCRATCH_ADD=1. "
          "Rule: shared/workflow/shared-git-state.md.")


def git(cwd, *args):
    """stdout lines of `git -C cwd args`, or None when it fails."""
    try:
        p = subprocess.run(["git", "-C", cwd, *args], capture_output=True,
                           text=True, timeout=10, encoding="utf-8")
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.splitlines() if p.returncode == 0 else None


def embedded_repo(cwd, rest):
    """The first untracked directory holding `.git` that `git add <rest>`
    would stage, or None. `-u` adds no untracked path."""
    if {"-u", "--update"} & set(rest) or any(a.startswith("--pathspec-from")
                                            for a in rest):
        return None
    cut = rest.index("--") if "--" in rest else len(rest)
    specs = [a for a in rest[:cut] if not a.startswith("-")] + rest[cut + 1:]
    if not specs and not {"-A", "--all"} & set(rest):
        return None
    for rel in git(cwd, "ls-files", "-o", "--exclude-standard",
                   "--", *(specs or [":/"])) or []:
        if rel.endswith("/") and os.path.exists(os.path.join(cwd, rel, ".git")):
            return rel
    return None


def evaluate(command, cwd, environ=None):
    """The deny reason, or None."""
    environ = os.environ if environ is None else environ
    if _STASH is None or environ.get(OVERRIDE) == "1":
        return None
    for argv, env, _rest, cur in walk_dirs(
            simple_commands_with_scope(command) or [], cwd):
        parsed = git_subcommand(argv)
        if (cur is None or parsed is None or env_value(env, OVERRIDE) == "1"
                or any(env_value(env, v) is not None
                       for v in ("GIT_DIR", "GIT_WORK_TREE"))):
            continue
        dirs, ok = _STASH._git_dir_opt(argv)
        if not ok:
            continue
        for d in dirs:
            cur = os.path.normpath(os.path.join(cur, os.path.expanduser(d)))
        sub, rest, _env = parsed
        if sub == "add" and not {"-n", "--dry-run"} & set(rest):
            path = embedded_repo(cur, rest)
            if path:
                return EMBEDDED.format(segment=" ".join(argv), path=path) + FOOTER
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
        print(f"no-add-sweeping-scratch: could not evaluate ({exc})", file=sys.stderr)
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
