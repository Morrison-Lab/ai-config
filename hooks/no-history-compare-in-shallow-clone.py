#!/usr/bin/env python3
"""PreToolUse guard: refuse history reads that a shallow clone answers wrongly.

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

The failure is silent: every command above exits 0 and prints a plausible
answer, so nothing downstream can notice. A warning is context that a session
reads past (ai-config#4741). The guard refuses.

## Exact where it can be

A shallow clone is not wrong about everything. `git log origin/main..HEAD` is
correct when the walk stays inside the fetched history, and routine skills
run it in every cloud session. Refusing it would block ordinary work, so for
a revision walk the guard asks git whether the walk reaches the cut-off:

    git rev-list --boundary A...B

where A and B are the two commits the range names (`A..B`, `^A B` and
`B --not A` all name A and B). The cut-off commits are listed in the
repository's `shallow` file. The symmetric walk goes from each side down to
their common ancestors, so it includes a cut-off commit exactly when either
side runs out of history first: the positive side, which would undercount,
or the excluded side, which would stop excluding and overcount. A cut-off
commit that appears only as a boundary (`-<sha>`) is a common ancestor, so
the answer is still right. When that query fails or times out, or the range
names more than two commits, the guard refuses rather than guess.

## What it refuses, in a shallow repository

Walk-checked (refused only when the walk A...B includes a cut-off commit):

    git log / rev-list with a range      A..B, A...B, ^A B, B --not A
    git merge-base A B, git cherry U H

Always refused, because the read is of the whole history or has no walk the
guard can check:

    git log --root / --max-parents       first-commit reads
    git log / rev-list --reverse         unless -n N limits it first
    git log ... | tail / tac / wc / sort the same reads, spelled with a pipe
    git rev-list with no range           unless -n N limits it
    git merge-base with other arguments  --octopus, --fork-point,
                                         --independent, 3+ commits
                                         (--is-ancestor and --all with two
                                         commits are walk-checked)
    git branch / for-each-ref / tag      with --merged, --no-merged,
                                         --contains, --no-contains, or any
                                         prefix git accepts as one of them
    git for-each-ref %(ahead-behind:..)  ahead/behind counts
    git show-branch, git range-diff      both exit 0 with no common commit
    git bundle create                    a backup missing the cut-off history
    git push that can delete a ref       --delete, -d, :ref, +:ref, --prune,
                                         --mirror, or a prefix of one;
                                         a --dry-run push is allowed

Remote deletion is refused in a shallow clone even when shallowness does not
change what it deletes, because the decision to delete is what a shallow
clone gets wrong. Unshallow first, then delete.

A plain `git log -5` or `git log -- ../file` is left alone.

## Which repository

`GIT_DIR=` or `--git-dir`, else `git -C <dir>`, else `env -C <dir>`, else the
`cd` moves earlier in the same call, starting from the hook payload's `cwd`.
A `cd` to a missing directory leaves the directory where it was, as the shell
does after a failed `cd`. A move it cannot resolve (`cd -`, `cd $VAR`) leaves
the directory unknown, and an unknown directory is skipped.
`xargs ... git ...` is read as the git command it runs.
A command inside `bash -c` or `sh -c` is checked from the payload's `cwd`,
and only when the outer command makes no `cd` move, since the nested shell's
starting directory is otherwise unknown (`shell_c_expansions` says why).

## The way out

`git fetch --unshallow`, then run the command again. Where a proxy refuses
that, `git fetch --depth=100000 origin`. For a deliberate read of the shallow
history, prefix that one command with `ALLOW_SHALLOW_HISTORY=1`.

## Fails open

The guard is silent when `shellcmd` cannot load, when the command does not
parse, when `git` is missing, and when the directory is not a repository or
its shallowness cannot be read. A PreToolUse hook that raises blocks the call.

## Not covered

- `eval "git ..."`, commands built from variables, and `git` reached through
  a script file.
- `git blame`, `git log -S` and `--follow`, which `memories/git.md` covers.
- `git status -sb`, `git branch -vv` and `%(upstream:track)`, which compare
  against an upstream and are routine; they are wrong only when the upstream
  forked below the cut-off.
- `mcp__remote-devices__device_bash` and `gh api -X DELETE .../git/refs/...`,
  which act on another machine or through the API.
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
WALK_TIMEOUT = 8

# git's parse-options accepts any prefix of a long option that names exactly
# one option. To decide "is this token one of the dangerous options", the
# token must be a prefix of a dangerous name and of no other option the
# command takes. These are the long options of each command (git 2.43).
REF_FILTERS = ("--merged", "--no-merged", "--contains", "--no-contains")
REF_CMD_OPTS = {
    "branch": REF_FILTERS + (
        "--abbrev", "--all", "--color", "--column", "--copy", "--create-reflog",
        "--delete", "--edit-description", "--force", "--format", "--ignore-case",
        "--list", "--move", "--no-abbrev", "--no-color", "--no-column",
        "--no-track", "--omit-empty", "--points-at", "--quiet",
        "--recurse-submodules", "--remotes", "--set-upstream-to",
        "--show-current", "--sort", "--track", "--unset-upstream", "--verbose"),
    "tag": REF_FILTERS + (
        "--annotate", "--cleanup", "--color", "--column", "--create-reflog",
        "--delete", "--edit", "--file", "--force", "--format", "--ignore-case",
        "--list", "--local-user", "--message", "--no-column", "--no-sign",
        "--omit-empty", "--points-at", "--sign", "--sort", "--trailer",
        "--verify"),
    "for-each-ref": REF_FILTERS + (
        "--count", "--exclude", "--format", "--ignore-case",
        "--include-root-refs", "--omit-empty", "--perl", "--points-at",
        "--python", "--shell", "--sort", "--start-after", "--stdin", "--tcl"),
}
PUSH_DELETERS = ("--delete", "--prune", "--mirror")
PUSH_OPTS = PUSH_DELETERS + (
    "--all", "--branches", "--tags", "--dry-run", "--porcelain", "--force",
    "--force-with-lease", "--force-if-includes", "--repo", "--set-upstream",
    "--thin", "--no-thin", "--quiet", "--verbose", "--progress",
    "--recurse-submodules", "--verify", "--no-verify", "--atomic",
    "--push-option", "--signed", "--ipv4", "--ipv6", "--receive-pack",
    "--exec", "--follow-tags", "--no-signed", "--no-atomic",
)

# Options of log / rev-list whose value is a separate word, so the value is
# never read as a revision (`--author a..b`, `-S x..y`).
LOG_VALUE_OPTS = frozenset({
    "-n", "--max-count", "--skip", "--author", "--committer", "--grep",
    "-S", "-G", "--since", "--until", "--after", "--before", "--format",
    "--pretty", "--date", "--encoding", "-L", "-O", "--diff-filter",
    "--output", "--decorate-refs", "--decorate-refs-exclude", "--exclude",
    "--glob", "--branches", "--tags", "--remotes",
})
GIT_VALUE_OPTS = ("-c", "--namespace", "--exec-path", "--work-tree")

RX_LOG_PIPED_WHOLE = re.compile(
    r"\bgit\b[^;&\n|]*\blog\b[^;&\n|]*(?:\|[^;&\n|]*)*"
    r"\|\s*(?:tail|tac|wc|sort|sed\s+-n\s+['\"]?\$)")

DENY = (
    "Refused: `{segment}` reads history that the repository at {repo} does "
    "not have: it is a SHALLOW clone{why}. Such a read still exits 0 and "
    "prints a plausible, wrong answer. On 2026-11-11 one made 23 lds "
    "branches look unrelated to main and nearly deleted 12 branches of "
    "unmerged work (ai-config#5323).\n\n"
    "Fix: `git -C {repo} fetch --unshallow origin` (or, where a proxy refuses "
    "that, `git -C {repo} fetch --depth=100000 origin`), then re-run. "
    "For a deliberate read of the shallow history, prefix that one command "
    "with `ALLOW_SHALLOW_HISTORY=1`."
)


def _is_option(tok, targets, all_opts):
    """True when `tok` names one of `targets`, in full or by a prefix that
    git would accept (one that matches no other option in `all_opts`)."""
    head = tok.split("=", 1)[0]
    if not head.startswith("--") or len(head) < 3:
        return False
    if head in targets:
        return True
    matches = {name for name in all_opts if name.startswith(head)}
    return bool(matches) and matches <= set(targets)


def _env_chdir(argv):
    """The directory of an `env -C <dir>` / `env --chdir=<dir>` wrapper."""
    if not argv or os.path.basename(argv[0]) != "env":
        return None
    i = 1
    while i < len(argv) and argv[i] != "git":
        tok = argv[i]
        if tok in ("-C", "--chdir") and i + 1 < len(argv):
            return argv[i + 1]
        if tok.startswith("--chdir="):
            return tok.split("=", 1)[1]
        i += 1
    return None


def _unwrap_xargs(argv):
    """`xargs [opts] git ...` -> `git ...`; anything else unchanged."""
    if argv and os.path.basename(argv[0]) == "xargs" and "git" in argv:
        return argv[argv.index("git"):]
    return argv


def _join(base, path):
    path = os.path.expanduser(path)
    if os.path.isabs(path):
        return os.path.normpath(path)
    if base is None:
        return None
    return os.path.normpath(os.path.join(base, path))


def _repo_dir(argv, base):
    """The repository directory one git argv acts on, or None if unknown."""
    chdir = _env_chdir(argv)
    if chdir is not None:
        base = _join(base, chdir)
    env, rest = strip_env(_unwrap_xargs(argv))
    git_dir = env_value(env, "GIT_DIR")
    out = base
    i = 1
    while i < len(rest) and rest[i].startswith("-"):
        tok = rest[i]
        if tok == "-C" and i + 1 < len(rest):
            out = _join(out, rest[i + 1])
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
        return _join(out, git_dir)
    return out


def _revisions(rest):
    """The revision words of a log/rev-list/merge-base argv, in order, with
    `--not` kept; stops at `--` and skips separate option values."""
    out = []
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--":
            break
        if tok == "--not":
            out.append(tok)
        elif tok.startswith("-"):
            if tok in LOG_VALUE_OPTS:
                i += 1
        else:
            out.append(tok)
        i += 1
    return out


def _is_range_word(tok, repo):
    if tok == "--not":
        return True
    if tok.startswith("^") and len(tok) > 1:
        return True
    if ".." not in tok:
        return False
    if tok.startswith(("../", "./")) or "/../" in tok or tok.endswith("/.."):
        return False
    if repo and os.path.exists(os.path.join(repo, tok)):
        return False
    return True


def _endpoints(revs):
    """The distinct commits a range names: `A..B`, `A...B`, `^A B` and
    `B --not A` all give [A, B]. An empty side of `..` is HEAD."""
    out = []
    for tok in revs:
        if tok == "--not":
            continue
        tok = tok[1:] if tok.startswith("^") else tok
        sep = "..." if "..." in tok else (".." if ".." in tok else None)
        parts = tok.split(sep, 1) if sep else [tok]
        for part in parts:
            part = part or "HEAD"
            if part not in out:
                out.append(part)
    return out


def _has_limit(rest):
    for i, tok in enumerate(rest):
        if tok == "--":
            break
        if re.fullmatch(r"-\d+", tok) or re.fullmatch(r"-n\d+", tok):
            return True
        if tok in ("-n", "--max-count") and i + 1 < len(rest):
            return True
        if tok.startswith("--max-count="):
            return True
    return False


def _flag(rest, *names):
    for tok in rest:
        if tok == "--":
            break
        if tok.split("=", 1)[0] in names:
            return True
    return False


def _push_can_delete(rest):
    if _flag(rest, "--dry-run") or "-n" in rest:
        return False
    for tok in rest:
        if tok == "--":
            continue
        if _is_option(tok, PUSH_DELETERS, PUSH_OPTS):
            return True
        if (tok.startswith("-") and not tok.startswith("--")
                and tok[1:].isalpha() and "d" in tok[1:]):
            return True
        bare = tok[1:] if tok.startswith("+") else tok
        if bare.startswith(":") and len(bare) > 1:
            return True
    return False


class _Repo:
    """Per-repository facts, each read once per hook run."""

    def __init__(self):
        self._shallow = {}

    def cutoff(self, repo):
        """The set of cut-off commits, empty if the repo is not shallow,
        or None if that cannot be read."""
        if repo in self._shallow:
            return self._shallow[repo]
        result = None
        try:
            flag = subprocess.run(
                ["git", "-C", repo, "rev-parse", "--is-shallow-repository",
                 "--git-common-dir"],
                capture_output=True, text=True, timeout=5)
            if flag.returncode == 0:
                lines = flag.stdout.split("\n")
                if lines[0].strip() == "false":
                    result = set()
                elif lines[0].strip() == "true" and len(lines) > 1:
                    common = _join(repo, lines[1].strip())
                    with open(os.path.join(common, "shallow"), encoding="utf-8") as fh:
                        result = {line.strip() for line in fh if line.strip()}
                    if not result:
                        result = None
        except Exception:
            result = None
        self._shallow[repo] = result
        return result

    @staticmethod
    def walk_hits_cutoff(repo, revisions, cutoff):
        """True when `rev-list --boundary <revisions>` includes a cut-off
        commit (not as a boundary), or when the query cannot answer."""
        try:
            res = subprocess.run(
                ["git", "-C", repo, "rev-list", "--boundary", *revisions, "--"],
                capture_output=True, text=True, timeout=WALK_TIMEOUT)
        except Exception:
            return True
        if res.returncode != 0:
            return True
        for line in res.stdout.split("\n"):
            sha = line.strip()
            if sha and not sha.startswith("-") and sha in cutoff:
                return True
        return False


def _verdict(sub, rest, repo, cutoff, piped_whole):
    """A short reason string when this git command must be refused, else None."""
    walk = _Repo.walk_hits_cutoff
    if sub in ("log", "rev-list"):
        revs = _revisions(rest)
        limited = _has_limit(rest)
        if _flag(rest, "--root", "--max-parents"):
            return "; --root and --max-parents read the cut-off as the first commit"
        if _flag(rest, "--reverse") and not limited:
            return "; an unlimited --reverse reads the cut-off as the first commit"
        if any(_is_range_word(tok, repo) for tok in revs):
            ends = _endpoints(revs)
            if len(ends) != 2:
                return "; a range with " + str(len(ends)) + " endpoints cannot be checked"
            if walk(repo, [ends[0] + "..." + ends[1]], cutoff):
                return "; this range's walk reaches the cut-off"
            return None
        if sub == "rev-list" and not limited:
            return "; an unlimited rev-list walks into the cut-off"
        if sub == "log" and piped_whole and not limited:
            return "; piping an unlimited log to tail/tac/wc/sort reads the cut-off"
        return None
    if sub in ("merge-base", "cherry"):
        revs = [tok for tok in _revisions(rest) if tok != "--not"]
        opts = [t for t in rest if t.startswith("--")]
        if sub == "merge-base" and any(t not in ("--is-ancestor", "--all") for t in opts):
            return "; merge-base " + " ".join(opts) + " cannot be checked"
        if len(revs) == 1 and sub == "cherry":
            revs = [revs[0], "HEAD"]
        if len(revs) != 2:
            return "; " + sub + " with " + str(len(revs)) + " commits"
        if walk(repo, [revs[0] + "..." + revs[1]], cutoff):
            return "; the walk between the two commits reaches the cut-off"
        return None
    if sub in ("branch", "for-each-ref", "tag"):
        if any(_is_option(tok, REF_FILTERS, REF_CMD_OPTS[sub]) for tok in rest):
            return "; --merged/--contains filters walk into the cut-off"
        if sub == "for-each-ref" and any("ahead-behind" in tok for tok in rest):
            return "; ahead-behind counts walk into the cut-off"
        return None
    if sub in ("show-branch", "range-diff"):
        return "; " + sub + " exits 0 with no common commit"
    if sub == "bundle" and rest and rest[0] == "create":
        return "; the bundle would lack the cut-off history"
    if sub == "push" and _push_can_delete(rest):
        return "; deleting a remote ref is refused until the history is complete"
    return None


def _evaluate_line(command, base_cwd, repos):
    cmds = simple_commands_with_scope(command)
    if cmds is None:
        return None
    piped_whole = bool(RX_LOG_PIPED_WHOLE.search(command))
    dirs = {(): base_cwd}
    for scope, argv in cmds:
        for n in range(1, len(scope) + 1):
            dirs.setdefault(scope[:n], dirs[scope[:n - 1]])
        _env, rest = strip_env(argv)
        if rest and rest[0] in CD_WORDS:
            target = resolve_cd_target(rest, dirs[scope])
            if target is None or os.path.isdir(target):
                dirs[scope] = target
            continue
        unwrapped = _unwrap_xargs(rest) if rest else rest
        parsed = git_subcommand(unwrapped if unwrapped is not rest else argv)
        if parsed is None:
            continue
        sub, sub_rest, env = parsed
        if env_value(env, OVERRIDE) == "1" or env_value(_env, OVERRIDE) == "1":
            continue
        repo = _repo_dir(argv, dirs[scope])
        if repo is None or not os.path.isdir(repo):
            continue
        cutoff = repos.cutoff(repo)
        if not cutoff:
            continue
        why = _verdict(sub, sub_rest, repo, cutoff, piped_whole)
        if why is not None:
            return "deny", DENY.format(segment=" ".join(argv), repo=repo, why=why)
    return None


def _has_cd(command):
    for _scope, argv in simple_commands_with_scope(command) or []:
        _env, rest = strip_env(argv)
        if rest and rest[0] in CD_WORDS:
            return True
        if _env_chdir(argv) is not None:
            return True
    return False


def evaluate(command, base_cwd):
    """`('deny', reason)` or `None`."""
    if simple_commands_with_scope is None:
        return None
    repos = _Repo()
    verdict = _evaluate_line(command, base_cwd, repos)
    if verdict:
        return verdict
    if _has_cd(command):
        return None
    for nested in list(shell_c_expansions(command))[1:]:
        verdict = _evaluate_line(nested, base_cwd, repos)
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
