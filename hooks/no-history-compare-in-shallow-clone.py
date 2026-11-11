#!/usr/bin/env python3
"""PreToolUse guard: refuse history comparisons and branch deletions in a shallow clone.

## The incident

On 2026-11-11 a thread was asked what the 44 working branches of
Morrison-Lab/lds were for. Cloud sessions clone with `--depth`, so the checkout
was shallow, and the session never checked. It then ran:

    git log --reverse --format='%cs %s' origin/main | head -1
    git merge-base origin/main origin/claude/clustering-definition
    git rev-list --count origin/main..origin/<branch>

In a shallow clone each of those answers from the truncated history.
`git log --reverse` called a 2026-11-04 commit main's first. Main actually
begins on 2026-09-04. `git merge-base` found no common ancestor.
`rev-list --count` called whole histories "ahead".
The report told Ezra that 23 branches shared no history with main.
It recommended deleting 41 branches, 12 of which hold commits that are on no
other branch and never had a PR. Ezra said "pause" seconds before the
deletion ran, then: "that was almost a huge mistake" and "make sure that can
never happen again".

## Why a deny, not a warning

The condition is exactly decidable before the command runs:
`git rev-parse --is-shallow-repository` prints `true` or `false`. And the
failure is silent. Every command above exits 0 and prints a plausible number,
so nothing downstream can notice. A warning is context that a session reads
past (ai-config#4741). This case gives no second signal, so the guard refuses.

## What it refuses

Each `git` simple command in the Bash call whose repository is shallow, when
the command is one of:

    git merge-base ...                   ancestry
    git rev-list ...                     counts, ranges, reachability
    git cherry ...                       unmerged-commit listing
    git log ... A..B / A...B / --reverse / --root
                                         ranges and "first commit" reads
    git branch / git for-each-ref / git tag with --merged, --no-merged,
        --contains or --no-contains
    git bundle create ...                a backup missing the cut-off history
    git push --delete / -d / :<ref>      deleting a remote branch on the
                                         strength of the comparisons above

A plain `git log -5` is left alone. A recent-commits read is right in a
shallow clone, as long as it is within the depth fetched.

The repository is the one the command runs in. The guard reads `git -C <dir>`
when the command has one. Otherwise it follows `cd` moves earlier in the
same call, starting from the hook payload's `cwd`. A move it cannot resolve
(`cd -`, `cd $VAR`) leaves the directory unknown. An unknown directory is
skipped rather than guessed.

## The way out

The deny names the fix: `git fetch --unshallow`, then run the command again.
Some proxies refuse `--unshallow`. Then use a bounded deepen,
`git fetch --depth=100000 origin`, which reaches the root of any repository
this lab has. For a deliberate read of the shallow history, prefix the
command with `ALLOW_SHALLOW_HISTORY=1`.

## Fails open

The guard is silent when `shellcmd` cannot load, when the command does not
parse, when `git` is missing, when the directory is not a repository, and
when `rev-parse` fails or times out. A PreToolUse hook that raises blocks
the call, which would make an outage of a history read.

## Not covered

- `mcp__remote-devices__device_bash` runs on another machine whose
  repository this hook cannot inspect.
- `gh api -X DELETE repos/.../git/refs/...` deletes a ref through the API and
  needs no local repository. The classification that justifies such a
  deletion is what this guard stops, and it happens locally.
"""
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
try:
    _LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (simple_commands_with_scope, strip_env, git_subcommand,
                          resolve_cd_target, env_value)
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-history-compare-in-shallow-clone: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); no guard will run", file=sys.stderr)
    simple_commands_with_scope = None

SHELL_TOOLS = frozenset({"Bash", "bash", "run_command", "execute_command",
                         "terminal", "shell"})
OVERRIDE = "ALLOW_SHALLOW_HISTORY"
REF_FILTER_FLAGS = ("--merged", "--no-merged", "--contains", "--no-contains")
CD_WORDS = frozenset({"cd", "pushd", "popd"})

DENY = (
    "Refused: `{segment}` compares or deletes history, and the repository at "
    "{repo} is a SHALLOW clone. In a shallow clone, merge-base, rev-list, "
    "--merged/--contains, log ranges and `log --reverse` answer from the "
    "truncated history and still exit 0. On 2026-11-11 this made 23 lds "
    "branches look unrelated to main and nearly deleted 12 branches of "
    "unmerged work.\n\n"
    "Fix: `git -C {repo} fetch --unshallow origin` (or, where a proxy refuses "
    "that, `git -C {repo} fetch --depth=100000 origin`), then re-run. "
    "For a deliberate read of the shallow history, prefix the command with "
    "`ALLOW_SHALLOW_HISTORY=1`."
)


def _git_c_dir(argv, base):
    """The directory a `git -C <dir>` points at, resolved against `base`."""
    _env, rest = strip_env(argv)
    out = base
    i = 1
    while i < len(rest) and rest[i].startswith("-"):
        if rest[i] == "-C" and i + 1 < len(rest):
            target = rest[i + 1]
            if out is None and not os.path.isabs(target):
                return None
            out = os.path.normpath(os.path.join(out or "/", os.path.expanduser(target)))
            i += 2
        elif rest[i] in ("-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"):
            i += 2
        else:
            i += 1
    return out


def _is_history_op(sub, rest):
    """True when `git <sub> <rest>` reads ancestry or deletes a remote ref."""
    if sub in ("merge-base", "rev-list", "cherry"):
        return True
    if sub == "log":
        for tok in rest:
            if tok in ("--reverse", "--root"):
                return True
            if not tok.startswith("-") and ".." in tok:
                return True
        return False
    if sub in ("branch", "for-each-ref", "tag"):
        return any(tok == f or tok.startswith(f + "=")
                   for tok in rest for f in REF_FILTER_FLAGS)
    if sub == "bundle":
        return bool(rest) and rest[0] == "create"
    if sub == "push":
        for tok in rest:
            if tok in ("--delete", "-d"):
                return True
            if (tok.startswith("-") and not tok.startswith("--")
                    and "d" in tok[1:] and tok[1:].isalpha()):
                return True
            if tok.startswith(":") and len(tok) > 1:
                return True
        return False
    return False


def _is_shallow(repo):
    try:
        res = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--is-shallow-repository"],
            capture_output=True, text=True, timeout=5)
    except Exception:
        return False
    return res.returncode == 0 and res.stdout.strip() == "true"


def evaluate(command, base_cwd):
    """`('deny', reason)` or `None`."""
    if simple_commands_with_scope is None:
        return None
    cmds = simple_commands_with_scope(command)
    if cmds is None:
        return None
    dirs = {(): base_cwd}
    for scope, argv in cmds:
        for n in range(1, len(scope) + 1):
            dirs.setdefault(scope[:n], dirs[scope[:n - 1]])
        env, rest = strip_env(argv)
        if rest and rest[0] in CD_WORDS:
            dirs[scope] = resolve_cd_target(rest, dirs[scope])
            continue
        parsed = git_subcommand(argv)
        if parsed is None:
            continue
        sub, sub_rest, env = parsed
        if env_value(env, OVERRIDE) == "1":
            continue
        if not _is_history_op(sub, sub_rest):
            continue
        repo = _git_c_dir(argv, dirs[scope])
        if repo is None or not os.path.isdir(repo):
            continue
        if _is_shallow(repo):
            return "deny", DENY.format(segment=" ".join(argv), repo=repo)
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") not in SHELL_TOOLS:
        return 0
    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = inp.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0
    try:
        verdict = evaluate(command, payload.get("cwd") or os.getcwd())
    except Exception as exc:  # fail open
        print(f"no-history-compare-in-shallow-clone: could not evaluate ({exc})",
              file=sys.stderr)
        return 0
    if verdict is None:
        return 0
    _kind, text = verdict
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": text}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
