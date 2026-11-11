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
never happen again" (ai-config#5323).

## Why a deny, not a warning

The condition is exactly decidable before the command runs:
`git rev-parse --is-shallow-repository` prints `true` or `false`. And the
failure is silent. Every command above exits 0 and prints a plausible number,
so nothing downstream can notice. A warning is context that a session reads
past (ai-config#4741). This case gives no second signal, so the guard refuses.

## What it refuses

Each `git` simple command in the Bash call whose repository is shallow, when
the command is one of:

    git merge-base, git cherry           ancestry
    git rev-list                         unless it is a bare `-n N` lookup
                                         with no range, `--count`, `--reverse`
                                         or `--max-parents`
    git log with a range                 `A..B`, `A...B`, `^A`, `--not`
    git log --reverse / --root / --max-parents=0
                                         "first commit" reads
    git log ... | tail                   the same read, spelled with tail
    git branch / for-each-ref / tag      with --merged, --no-merged,
                                         --contains, --no-contains, or an
                                         unambiguous prefix such as --merg
    git bundle create                    a backup missing the cut-off history
    git push that can delete a ref       --delete, -d, `:ref`, `+:ref`,
                                         --prune, --mirror

A plain `git log -5` or `git log -- ../file` is left alone. A recent-commits
read is right in a shallow clone, as long as it is within the depth fetched.

## Which repository

The repository is the one the command runs in: `GIT_DIR=` or `--git-dir`,
else `git -C <dir>`, else the `cd` moves earlier in the same call, starting
from the hook payload's `cwd`. A `cd` to a directory that does not exist
leaves the directory where it was, as the shell does after a failed `cd`.
A move it cannot resolve (`cd -`, `cd $VAR`) leaves the directory unknown,
and an unknown directory is skipped rather than guessed.

A command inside `bash -c "..."` or `sh -c '...'` is checked too, from the
payload's `cwd`, but only when the outer command makes no `cd` move, since
the nested shell's starting directory is otherwise unknown
(`scripts/lib/shellcmd.py`'s `shell_c_expansions` says why).

## The way out

The deny names the fix: `git fetch --unshallow`, then run the command again.
Some proxies refuse `--unshallow`. Then use a bounded deepen,
`git fetch --depth=100000 origin`, which reaches the root of any repository
this lab has. For a deliberate read of the shallow history, prefix the one
command with `ALLOW_SHALLOW_HISTORY=1`. The prefix covers only the command it
is written on.

## Fails open

The guard is silent when `shellcmd` cannot load, when the command does not
parse, when `git` is missing, when the directory is not a repository, and
when `rev-parse` fails or times out. A PreToolUse hook that raises blocks
the call, which would make an outage of a history read.

## Not covered

- `eval "git ..."` and commands built from variables, which no argv split
  can read.
- `mcp__remote-devices__device_bash` runs on another machine whose
  repository this hook cannot inspect.
- `gh api -X DELETE repos/.../git/refs/...` deletes a ref through the API and
  needs no local repository. The classification that justifies such a
  deletion is what this guard stops, and it happens locally.
- `git describe`, `git diff A...B`, `range-diff` and `show-branch` are
  allowed: in a shallow clone they fail loudly ("no merge base") rather than
  answer wrongly.
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
    from shellcmd import (simple_commands_with_scope, strip_env, git_subcommand,
                          resolve_cd_target, env_value, shell_c_expansions)
except Exception as _exc:  # broken install: degrade, never block
    print(f"no-history-compare-in-shallow-clone: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); no guard will run", file=sys.stderr)
    simple_commands_with_scope = None

SHELL_TOOLS = frozenset({"Bash", "bash", "run_command", "execute_command",
                         "terminal", "shell"})
OVERRIDE = "ALLOW_SHALLOW_HISTORY"
CD_WORDS = frozenset({"cd", "pushd", "popd"})

# Ref filters of `git branch`, `for-each-ref` and `tag`. These commands use
# git's parse-options, which accepts any unambiguous prefix of a long option,
# so `--merg` is `--merged`. A prefix must be at least this long to count.
REF_FILTERS = ("--merged", "--no-merged", "--contains", "--no-contains")
MIN_PREFIX = 5

# `git push` options that can delete a remote ref, matched by prefix too.
PUSH_DELETERS = ("--delete", "--prune", "--mirror")

# `git log` / `rev-list` options whose value is a separate word, so the value
# is never read as a revision range (`--author a..b`, `-S x..y`).
LOG_VALUE_OPTS = frozenset({
    "-n", "--max-count", "--skip", "--author", "--committer", "--grep",
    "-S", "-G", "--since", "--until", "--after", "--before", "--format",
    "--pretty", "--date", "--encoding", "-L", "-O", "--diff-filter",
    "--output", "--decorate-refs", "--decorate-refs-exclude", "--exclude",
    "--glob", "--branches", "--tags", "--remotes",
})
FIRST_COMMIT_FLAGS = ("--reverse", "--root")
GIT_VALUE_OPTS = ("-c", "--namespace", "--exec-path", "--work-tree")

RX_LOG_TO_TAIL = re.compile(r"\bgit\b[^|;&\n]*\blog\b[^|;&\n]*\|\s*tail\b")

DENY = (
    "Refused: `{segment}` compares or deletes history, and the repository at "
    "{repo} is a SHALLOW clone. In a shallow clone, merge-base, rev-list, "
    "--merged/--contains, log ranges and first-commit reads answer from the "
    "truncated history and still exit 0. On 2026-11-11 this made 23 lds "
    "branches look unrelated to main and nearly deleted 12 branches of "
    "unmerged work (ai-config#5323).\n\n"
    "Fix: `git -C {repo} fetch --unshallow origin` (or, where a proxy refuses "
    "that, `git -C {repo} fetch --depth=100000 origin`), then re-run. "
    "For a deliberate read of the shallow history, prefix that one command "
    "with `ALLOW_SHALLOW_HISTORY=1`."
)


def _abbrev_of(tok, names, min_len=MIN_PREFIX):
    """True when `tok` (or its part before `=`) is one of `names` or an
    unambiguous-looking prefix of one, at least `min_len` characters long."""
    head = tok.split("=", 1)[0]
    if not head.startswith("--"):
        return False
    for name in names:
        if head == name:
            return True
        if len(head) >= min_len and name.startswith(head):
            return True
    return False


def _repo_dir(argv, base):
    """The repository directory one git argv acts on, or None if unknown."""
    env, rest = strip_env(argv)
    git_dir = env_value(env, "GIT_DIR")
    out = base
    i = 1
    while i < len(rest) and rest[i].startswith("-"):
        tok = rest[i]
        if tok == "-C" and i + 1 < len(rest):
            target = os.path.expanduser(rest[i + 1])
            if not os.path.isabs(target) and out is None:
                return None
            out = os.path.normpath(os.path.join(out or "/", target))
            i += 2
        elif tok == "--git-dir" and i + 1 < len(rest):
            git_dir = rest[i + 1]
            i += 2
        elif tok.startswith("--git-dir="):
            git_dir = tok.split("=", 1)[1]
            i += 1
        elif tok in GIT_VALUE_OPTS:
            i += 2
        else:
            i += 1
    if git_dir:
        git_dir = os.path.expanduser(git_dir)
        if not os.path.isabs(git_dir):
            if out is None:
                return None
            git_dir = os.path.join(out, git_dir)
        return os.path.normpath(git_dir)
    return out


def _positionals(rest):
    """Non-option words of a log/rev-list argv, stopping at `--`, skipping the
    separate values of value-taking options."""
    out = []
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--":
            break
        if tok.startswith("-"):
            if tok in LOG_VALUE_OPTS:
                i += 2
                continue
            i += 1
            continue
        out.append(tok)
        i += 1
    return out


def _is_range(tok, repo):
    """True when a positional word is a revision range rather than a path."""
    if tok.startswith("^") and len(tok) > 1:
        return True
    if ".." not in tok:
        return False
    if tok.startswith("../") or tok.startswith("./") or "/../" in tok or tok.endswith("/.."):
        return False
    if repo and os.path.exists(os.path.join(repo, tok)):
        return False
    return True


def _has_limit(rest):
    """True when a rev-list/log argv caps its output with -n N, -N or --max-count."""
    for i, tok in enumerate(rest):
        if tok == "--":
            break
        if re.fullmatch(r"-\d+", tok) or re.fullmatch(r"-n\d+", tok):
            return True
        if tok == "-n" and i + 1 < len(rest):
            return True
        if tok.startswith("--max-count="):
            return True
        if tok == "--max-count" and i + 1 < len(rest):
            return True
    return False


def _range_like(rest, repo):
    if any(tok == "--not" for tok in rest):
        return True
    return any(_is_range(tok, repo) for tok in _positionals(rest))


def _first_commit_flag(rest):
    for tok in rest:
        if tok == "--":
            break
        if tok in FIRST_COMMIT_FLAGS:
            return True
        if tok.startswith("--max-parents"):
            return True
    return False


def _push_can_delete(rest):
    for tok in rest:
        if tok == "--":
            continue
        if tok == "-d" or _abbrev_of(tok, PUSH_DELETERS, min_len=5):
            return True
        if (tok.startswith("-") and not tok.startswith("--")
                and tok[1:].isalpha() and "d" in tok[1:]):
            return True
        bare = tok[1:] if tok.startswith("+") else tok
        if bare.startswith(":") and len(bare) > 1:
            return True
    return False


def _is_history_op(sub, rest, repo):
    """True when `git <sub> <rest>` reads ancestry or can delete a remote ref."""
    if sub in ("merge-base", "cherry"):
        return True
    if sub == "rev-list":
        if any(tok == "--count" or tok == "--reverse" for tok in rest):
            return True
        if _first_commit_flag(rest):
            return True
        if not _has_limit(rest):
            return True
        return _range_like(rest, repo)
    if sub == "log":
        return _first_commit_flag(rest) or _range_like(rest, repo)
    if sub in ("branch", "for-each-ref", "tag"):
        return any(_abbrev_of(tok, REF_FILTERS) for tok in rest)
    if sub == "bundle":
        return bool(rest) and rest[0] == "create"
    if sub == "push":
        return _push_can_delete(rest)
    return False


class _ShallowCache:
    def __init__(self):
        self._seen = {}

    def __call__(self, repo):
        if repo not in self._seen:
            try:
                res = subprocess.run(
                    ["git", "-C", repo, "rev-parse", "--is-shallow-repository"],
                    capture_output=True, text=True, timeout=5)
                self._seen[repo] = (res.returncode == 0
                                    and res.stdout.strip() == "true")
            except Exception:
                self._seen[repo] = False
        return self._seen[repo]


def _evaluate_line(command, base_cwd, is_shallow, log_to_tail):
    cmds = simple_commands_with_scope(command)
    if cmds is None:
        return None
    dirs = {(): base_cwd}
    for scope, argv in cmds:
        for n in range(1, len(scope) + 1):
            dirs.setdefault(scope[:n], dirs[scope[:n - 1]])
        _env, rest = strip_env(argv)
        if rest and rest[0] in CD_WORDS:
            target = resolve_cd_target(rest, dirs[scope])
            if target is None or os.path.isdir(target):
                dirs[scope] = target
            # A cd to a missing directory fails; the shell stays put.
            continue
        parsed = git_subcommand(argv)
        if parsed is None:
            continue
        sub, sub_rest, env = parsed
        if env_value(env, OVERRIDE) == "1":
            continue
        repo = _repo_dir(argv, dirs[scope])
        if repo is None or not os.path.isdir(repo):
            continue
        hit = _is_history_op(sub, sub_rest, repo)
        if not hit and sub == "log" and log_to_tail and not _has_limit(sub_rest):
            hit = True
        if hit and is_shallow(repo):
            return "deny", DENY.format(segment=" ".join(argv), repo=repo)
    return None


def _has_cd(command):
    cmds = simple_commands_with_scope(command) or []
    for _scope, argv in cmds:
        _env, rest = strip_env(argv)
        if rest and rest[0] in CD_WORDS:
            return True
    return False


def evaluate(command, base_cwd):
    """`('deny', reason)` or `None`."""
    if simple_commands_with_scope is None:
        return None
    is_shallow = _ShallowCache()
    log_to_tail = bool(RX_LOG_TO_TAIL.search(command))
    verdict = _evaluate_line(command, base_cwd, is_shallow, log_to_tail)
    if verdict:
        return verdict
    if _has_cd(command):
        return None
    for nested in list(shell_c_expansions(command))[1:]:
        verdict = _evaluate_line(nested, base_cwd, is_shallow,
                                 bool(RX_LOG_TO_TAIL.search(nested)))
        if verdict:
            return verdict
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
    cwd = payload.get("cwd")
    try:
        if not isinstance(cwd, str) or not os.path.isabs(cwd):
            cwd = os.getcwd()
        verdict = evaluate(command, cwd)
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
