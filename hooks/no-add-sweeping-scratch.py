#!/usr/bin/env python3
"""PreToolUse guard: a `git add` that would stage an embedded repository,
such as a worktree-isolated agent under `.claude/worktrees/`, as a gitlink no
clone can resolve (ai-config#3884). Read-only: `git ls-files -o` on the add's
own pathspecs lists an untracked repository as `dir/`, and it takes no index
lock; `-z` keeps a non-ASCII name unquoted, and a forced add (`-f`) lists
ignored paths too. `-u` and `--pathspec-from-file` are not checked.
Also a `git commit -F <file>` (`--file`, `-aF`) whose message file is staged
now or by an earlier add-everything (`-A`, `--all`, `.`) on the same line
(ai-config#3558), decided from the index and `check-ignore`; a commit limited
to pathspecs without `-i`, a message path the shell still expands (`$`, a
backtick), one under `.git/`, an add in another repository and a sweep a
later whole-index `git reset` undid all pass. `ALLOW_SCRATCH_ADD=1`
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
    _ADD = load_sibling(__file__, "flag-add-a-outside-pathspec.py", "_faop")
    _STASH = load_sibling(__file__, "no-bare-stash-pop.py", "_nbsp")
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-add-sweeping-scratch: helpers did not load ({_exc})", file=sys.stderr)
    _ADD = _STASH = None

SHELL_TOOLS = {"Bash", "bash", "run_command", "execute_command", "terminal", "shell"}
OVERRIDE = "ALLOW_SCRATCH_ADD"
# `git commit` options whose value is the next argument, so not a pathspec.
COMMIT_VALUE_OPTS = frozenset({
    "-m", "--message", "-F", "--file", "-C", "--reuse-message", "-c",
    "--reedit-message", "-t", "--template", "--author", "--date", "--fixup",
    "--squash", "--cleanup", "--trailer"})
EMBEDDED = (
    "Refused: `{segment}` would stage `{path}`, which holds its own `.git`, as "
    "a gitlink no clone can resolve (ai-config#3884). Ignore it (agents live "
    "under `.claude/worktrees/`), or name the paths you mean to add.")
MSGFILE = (
    "Refused: `{segment}` commits its own message file `{path}`, which {how} "
    "(ai-config#3558). Write the message outside the work tree, such as the "
    "session scratchpad or /tmp, and pass that path to -F.")
FOOTER = (" Override for one command: ALLOW_SCRATCH_ADD=1. "
          "Rule: shared/workflow/shared-git-state.md.")


def git(cwd, *args, nul=False):
    """stdout records of `git -C cwd args` (lines, or NUL-separated with
    `nul`), or None when it fails."""
    try:
        p = subprocess.run(["git", "-C", cwd, *args], capture_output=True,
                           text=True, timeout=10, encoding="utf-8")
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return [r for r in p.stdout.split("\0") if r] if nul else p.stdout.splitlines()


def has_flag(opts, short, long):
    """Whether `git add` options include `-<short>` or `--<long>`, the short
    form alone or in a cluster such as `-Af`."""
    return any(a == "--" + long or (a.startswith("-") and not a.startswith("--")
                                    and short in a[1:]) for a in opts)


def embedded_repo(cwd, rest):
    """The first untracked directory holding `.git` that `git add <rest>`
    would stage, or None. `-u` adds no untracked path."""
    if {"-u", "--update"} & set(rest) or any(a.startswith("--pathspec-from")
                                            for a in rest):
        return None
    cut = rest.index("--") if "--" in rest else len(rest)
    specs = [a for a in rest[:cut] if not a.startswith("-")] + rest[cut + 1:]
    if not specs and not has_flag(rest[:cut], "A", "all"):
        return None
    exclude = ([] if has_flag(rest[:cut], "f", "force")
               else ["--exclude-standard"])
    for rel in git(cwd, "ls-files", "-z", "-o", *exclude,
                   "--", *(specs or [":/"]), nul=True) or []:
        if rel.endswith("/") and os.path.exists(os.path.join(cwd, rel, ".git")):
            return rel
    return None


def message_file(rest):
    """The `-F`/`--file` value of a `git commit` argv tail, or None. A short
    cluster such as `-aF msg` counts; one where a value option comes first
    (`-mF`) does not."""
    for i, arg in enumerate(rest):
        nxt = rest[i + 1] if i + 1 < len(rest) else None
        if arg == "--":
            return None
        if arg == "--file":
            return nxt
        if arg.startswith("--file="):
            return arg[len("--file="):]
        if arg.startswith("-") and not arg.startswith("--"):
            for j, ch in enumerate(arg[1:], 1):
                if ch == "F":
                    return arg[j + 1:] or nxt
                if ch in "mCct":
                    break
    return None


def limited_commit(rest):
    """True when the commit names pathspecs without `-i`, so it commits only
    those paths and not the rest of the index."""
    if {"-i", "--include"} & set(rest):
        return False
    if "--" in rest[:-1]:
        return True
    skip = False
    for arg in rest:
        if skip:
            skip = False
        elif arg in COMMIT_VALUE_OPTS:
            skip = True
        elif arg.startswith("-") and not arg.startswith("--"):
            # A cluster ending in a value letter (`-aF`) takes the next arg.
            k = next((j for j, c in enumerate(arg[1:]) if c in "FmCct"), None)
            skip = k == len(arg) - 2
        elif not arg.startswith("-"):
            return True
    return False


def toplevel(cwd):
    """The real path of the work tree holding `cwd`, or None."""
    top = git(cwd, "rev-parse", "--show-toplevel")
    return os.path.realpath(top[0]) if top else None


def swept_message(cwd, path, sweeps):
    """Why the message file `path` lands in the commit, or None. A path the
    shell would still expand (`$VAR`, a backtick) is not resolved."""
    if path == "-" or "$" in path or "`" in path:
        return None
    full = os.path.realpath(os.path.join(cwd, os.path.expanduser(path)))
    top = toplevel(cwd)
    if not top or os.path.commonpath([top, full]) != top:
        return None
    rel = os.path.relpath(full, top)
    if rel.split(os.sep)[0] == ".git":  # git never stages its own directory
        return None
    if rel in (git(cwd, "diff", "--cached", "--name-only", "-z", nul=True) or []):
        return "is staged"
    if git(cwd, "check-ignore", "-q", "--", full) is not None:
        return None
    if git(cwd, "ls-files", "--error-unmatch", "--", full) is not None:
        return None
    for add_dir, add_top, scope, excludes in sweeps:
        if add_top != top:  # the add-everything ran in another repository
            continue
        root = os.path.realpath(top if scope == "repo" else add_dir)
        if (os.path.commonpath([root, full]) == root and not _ADD._is_excluded(
                os.path.relpath(full, os.path.realpath(add_dir)), excludes)):
            return "the earlier `git add` in this command stages"
    return None


def evaluate(command, cwd, environ=None):
    """The deny reason, or None."""
    environ = os.environ if environ is None else environ
    if _ADD is None or _STASH is None or environ.get(OVERRIDE) == "1":
        return None
    sweeps = []
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
        segment = " ".join(argv)
        if sub == "add" and not {"-n", "--dry-run"} & set(rest):
            path = embedded_repo(cur, rest)
            if path:
                return EMBEDDED.format(segment=segment, path=path) + FOOTER
            everything = _ADD._add_everything(rest)
            if everything:
                sweeps.append((cur, toplevel(cur), *everything))
        elif sub == "reset" and "--soft" not in rest and all(
                a.startswith("-") or a == "HEAD" for a in rest):
            # A whole-index reset unstages what an earlier sweep staged.
            sweeps = [s for s in sweeps if s[1] != toplevel(cur)]
        elif sub == "commit" and not limited_commit(rest):
            msg = message_file(rest)
            how = msg and swept_message(cur, msg, sweeps)
            if how:
                return MSGFILE.format(segment=segment, path=msg, how=how) + FOOTER
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
