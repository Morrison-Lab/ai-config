#!/usr/bin/env python3
"""PreToolUse guard: a `git` command that stages every modified tracked path
-- `git commit -a`/`--all`, `git add -u`/`--update`, `git add -A`/`--all`
(`--no-ignore-removal`), or a `git add .`/`git add <dir>` covering a
submodule -- while that submodule's checked-out commit differs from the one
the index pins.

## The incident

2026-10-15, `Morrison-Lab/lds#1026`: `git commit -am "..."` ran in a checkout
whose `latex-macros` submodule sat at a different commit than the index
recorded. `-a` stages every modified TRACKED path, and a submodule whose HEAD
has moved is a modified tracked path (a gitlink, mode 160000). So the commit
carried the intended `CLAUDE.md` edit AND moved the pin from `6e227b6` to the
older `85c285b`. The PR bot flagged it as blocking.

`flag-add-a-outside-pathspec.py` covers `git add -A` and untracked files. It
does not read `git commit -a`, does not read `git add -u` (its M4 clause
exempts `-u` because `-u` never stages an UNTRACKED file), and does not look
at submodules at all. Checked with git 2.x: `git add -u`, `git add -A`,
`git add .` and `git add <dir>` all stage a moved gitlink, as does
`git commit -a`.

## Why a hook rather than a rule

Nothing in the command text says the submodule moved. Whether a pin is about to
change is a fact about the live working tree, which only `git status` at the
moment of the commit can answer -- the same reasoning as the sibling guard.

## Why this warns rather than blocks

A deliberate pin bump (`git commit -am "bump macros"`) is legitimate and is
often exactly what `-a` is for. The hook cannot tell it from an accident, so it
only ADDS context: `additionalContext` and a `systemMessage`, never a
`permissionDecision`. See README's "A hook that misfires is worse than a
missing one".

## The match condition

  M1  the tool is `Bash` and `tool_input.command` parses into simple commands
  M2  one of them is `git`, after skipping leading env-var assignments and
      lead words, and `-C <dir>` / `-c <k=v>` global options
  M3  its subcommand is `commit` with `-a`/`--all` (also inside a combined
      short cluster such as `-am`, `-av`, `-sam`; a cluster is read left to
      right and stops at a letter that takes a value, so `-ma` -- message
      "a" -- is NOT `-a`, and also at `S` and `u`, whose values are optional
      and attached, so `-uall` is NOT `-a` while `-S -a` and `-u -a` ARE),
      or `add` with `-u`/`--update`, `-A`/`--all`, or a pathspec that covers
      a submodule from above (`git add .`, `git add <dir>`); a dry run
      (`commit --dry-run`/`--short`/`--porcelain`/`--long`, `add -n`/
      `--dry-run`) stages and commits nothing and is silent. Every match in
      the command is checked, not only the first
  M4  the target repository is the `-C` directory, applied on top of the
      session cwd (`tool_input.Cwd`, else the payload's `cwd`, else the
      hook's own) and of any earlier `cd <dir>` in the same command, scoped
      to its subshell; `cd -P`
      and `cd -L` are read, and a bare `cd` or `cd -` makes the directory
      unknown, so a later relative target is skipped (see below)
  M5  `git status --porcelain=v1 -z --ignore-submodules=dirty` there lists
      an entry whose worktree column is `M` and whose path has mode 160000
      in `git ls-files -s`
  M6  the submodule's own HEAD differs from the commit the index pins -- an
      ` M` that is only dirty submodule CONTENT leaves the gitlink unchanged
      and cannot be swept in, so it stays silent (the status flag already
      drops it; this comparison is defence in depth). A pin bump already staged
      (`M ` with HEAD still equal to the staged pin) is silent too, while
      `MM` (staged, then the submodule moved again) warns
  M7  for `git add -u|-A <pathspec>`, only a submodule at or under a pathspec
      counts, but a magic (`:/`) or glob pathspec is not evaluated and warns;
      for a plain `git add <pathspec>`, only a pathspec covering the submodule
      from above counts (naming it is how a pin is bumped on purpose, and a
      magic or glob pathspec is not evaluated and stays silent); relative
      paths are compared through realpath. `commit -a` takes no pathspec
      (git refuses the combination)

Fails OPEN on any parse trouble, on git failing or timing out, and outside a
git repository. Every git call shares an 8 s deadline, inside the 10 s the
hook gets in hooks.json, and runs with GIT_OPTIONAL_LOCKS=0.

## Documented silent cases

The hook cannot know the target repository, so it says nothing, rather than
check the wrong one, when:

  - the command carries `--git-dir` or `--work-tree`, which name another
    repository than the cwd, `-C` and `cd` resolve to;
  - the target directory is not a directory at match time, which includes
    `cd ~` and `cd $VAR` (the text is not expanded) and any `cd` into a
    directory the command itself creates;
  - a bare `cd` or `cd -` came earlier, so the directory is unknown (an
    absolute `git -C /path` after it is still read);
  - a `GIT_DIR=...` or `GIT_WORK_TREE=...` prefix (also after `env`) names
    another repository, like `--git-dir`; an earlier `export GIT_DIR=...;`
    statement or any other redirecting variable is not read;
  - git is not reached as `git` after the shared parser's normalisation
    (`/usr/bin/git` and `timeout 60 git` ARE read): an alias, a shell
    function, or `pushd`/`popd` directory changes are not followed;
  - a `cd` inside a subshell `( ... )` is scoped to it, as in the shell, so a
    git command after the subshell runs where the subshell started; a `cd` in
    a `{ ... }` group moves the caller and is followed;
  - the commit names its paths: `git commit <pathspec>` and `git commit -i
    <pathspec>` also commit a moved gitlink covered by a directory pathspec
    (checked: `git commit -m x .` committed `mod`), but they say which paths
    they take, so the hook does not parse commit's positional arguments.
"""
import json
import os
import subprocess
import sys
import time

# `git commit` short options that consume a value (attached or next token),
# so the rest of a cluster after one of them is that value, not more flags.
# -S and -u take OPTIONAL, attached-only arguments, so they never consume
# the next token and are deliberately absent here.
_COMMIT_VALUE_SHORT = set("mFCct")
_COMMIT_VALUE_LONG = {
    "--message", "--file", "--author", "--date", "--cleanup",
    "--reuse-message", "--reedit-message", "--fixup", "--squash",
    "--template", "--trailer", "--pathspec-from-file",
}
# global options of `git` that consume the next token (checked with git 2.x:
# `--namespace ns` and `--config-env k=ENV` take a separated value;
# `--exec-path[=<path>]` takes an optional ATTACHED one and so must not be
# here, and `--super-prefix` is not a user option at all).
# --git-dir and --work-tree are handled before this set is consulted.
_GIT_VALUE_GLOBAL = {"-C", "-c", "--namespace", "--config-env"}
# `git commit` options that make it a dry run: nothing is committed.
_COMMIT_DRY_RUN = {"--dry-run", "--short", "--porcelain", "--long"}


# The shared parser blanks heredoc bodies correctly (a command after
# `<<EOF ... EOF` stays its own command); a private copy did not.
_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from shellcmd import simple_commands_with_scope as _simple_commands
    from shellcmd import strip_env as _strip_env
except Exception as _exc:  # broken install: fail open, like every guard here
    print("flag-commit-a-sweeps-submodule: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); inert", file=sys.stderr)
    _simple_commands = None


# Environment assignments that name another repository than the cwd does.
_REDIRECT_ENV = ("GIT_DIR", "GIT_WORK_TREE")


def _redirects_git(env_tokens):
    """True if a leading `NAME=value` (or `env NAME=value`) sends git to
    another repository, as `--git-dir`/`--work-tree` would."""
    return any(t.split("=", 1)[0] in _REDIRECT_ENV for t in env_tokens)


def _git_invocation(rest):
    """(c_dirs, subcommand, args) for a `git ...` argv, or None.

    `c_dirs` is every `-C <dir>` in order (git applies them cumulatively).
    """
    if not rest or rest[0] != "git":
        return None
    c_dirs = []
    i = 1
    while i < len(rest):
        a = rest[i]
        if a == "-C" and i + 1 < len(rest):
            c_dirs.append(rest[i + 1])
            i += 2
        elif a in ("--git-dir", "--work-tree") or a.startswith(
                ("--git-dir=", "--work-tree=")):
            return None  # names another repository; go silent (docstring)
        elif a in _GIT_VALUE_GLOBAL:
            i += 2
        elif a.startswith("-"):
            i += 1  # --no-pager, -p, --exec-path[=x], ...
        else:
            return c_dirs, a, rest[i + 1:]
    return None


def commit_sweeps_all(args):
    """M3 for `git commit`: true if `-a`/`--all` is among the options and
    the commit is not a dry run (`--dry-run`, `--short`, `--porcelain` and
    `--long` all commit nothing; checked with git 2.x)."""
    sweeps = dry = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            break
        if a.startswith("--"):
            if a == "--all":
                sweeps = True
            elif a in _COMMIT_DRY_RUN:
                dry = True
            elif a in _COMMIT_VALUE_LONG:
                i += 1  # value is the next token
            i += 1
            continue
        if a.startswith("-") and a != "-":
            for pos, ch in enumerate(a[1:], start=1):
                if ch == "a":
                    sweeps = True
                elif ch in _COMMIT_VALUE_SHORT:
                    if pos == len(a) - 1:
                        i += 1  # value is the next token
                    break
                elif ch in "Su":
                    break  # optional attached value (-uall): rest of cluster
            i += 1
            continue
        i += 1
    return sweeps and not dry


def add_kind(args):
    """M3 for `git add`: (kind, pathspecs), or None when nothing is staged
    beyond named paths. kind is "add -u" (`-u`/`--update`), "add -A"
    (`-A`/`--all`) or "add" (only pathspecs, which can still cover a
    submodule: `git add .`); `-n`/`--dry-run` and `--refresh` stage nothing
    (checked with git 2.x), and `--no-ignore-removal` is an alias of `-A`."""
    flags, paths, dashdash = [], [], False
    for a in args:
        if not dashdash and a == "--":
            dashdash = True
        elif not dashdash and a.startswith("-") and a != "-":
            flags.append(a)
        else:
            paths.append(a)
    letters = "".join(f[1:] for f in flags if not f.startswith("--"))
    if "--dry-run" in flags or "--refresh" in flags or "n" in letters:
        return None
    if "--update" in flags or "u" in letters:
        return "add -u", paths
    if "--all" in flags or "--no-ignore-removal" in flags or "A" in letters:
        return "add -A", paths
    return ("add", paths) if paths else None


def _cd_operand(args):
    """The directory operand of `cd`, or None when it is not a literal path:
    a bare `cd` (goes home) and `cd -` (goes to the previous directory)."""
    i = 0
    while i < len(args) and args[i].startswith("-") and args[i] != "-":
        i += 1
        if args[i - 1] == "--":
            break  # `cd -P -- dir`; -P, -L, -e and -@ are skipped above
    if i >= len(args) or args[i] == "-":
        return None
    return args[i]


def _join(base, d):
    """`d` applied on `base`; None while `base` is unknown and `d` relative."""
    if os.path.isabs(d):
        return d
    return None if base is None else os.path.join(base, d)


def offending(command):
    """[(segment, kind, target_dir, pathspecs), ...] for every matching
    invocation in `command`, in order. `target_dir` is the directory git
    would run in, relative to the session cwd unless absolute; an invocation
    whose directory is unknown (after a bare `cd` or `cd -`) is left out."""
    if _simple_commands is None:
        return []
    cmds = _simple_commands(command)
    if cmds is None:
        return []
    # Directory per subshell scope: a subshell starts from its parent's
    # directory and a `cd` inside it never reaches the parent. A directory is
    # None once a `cd` goes somewhere the text does not name.
    cds = {(0,): ""}

    def cd_of(scope):
        while scope not in cds:
            scope = scope[:-1]
        return cds[scope]

    hits = []
    for scope, argv in cmds:
        env, rest = _strip_env(argv)
        cd = cd_of(scope)
        if rest and rest[0] == "cd":
            operand = _cd_operand(rest[1:])
            cds[scope] = None if operand is None else _join(cd, operand)
            continue
        inv = _git_invocation(rest)
        if inv is None or _redirects_git(env):
            continue
        c_dirs, sub, args = inv
        target = cd
        for d in c_dirs:
            target = _join(target, d)
        if target is None:
            continue
        segment = " ".join(argv)
        if sub == "commit" and commit_sweeps_all(args):
            hits.append((segment, "commit -a", target, None))
        elif sub == "add":
            found = add_kind(args)
            if found:
                hits.append((segment, found[0], target, found[1]))
    return hits


# hooks.json gives this hook 10 s. Every git call shares one deadline inside
# that, so a slow repository fails open here rather than being killed by the
# harness. FLAG_COMMIT_A_BUDGET_S overrides the total (the tests use 0).
_DEFAULT_BUDGET_S = 8.0
_PER_CALL_S = 5.0
_deadline = None


def _start_budget():
    global _deadline
    try:
        budget = float(os.environ.get("FLAG_COMMIT_A_BUDGET_S", ""))
    except ValueError:
        budget = _DEFAULT_BUDGET_S
    _deadline = time.monotonic() + budget


def _git(cwd, *args):
    """stdout of `git args` in cwd, or None on any failure or when the
    shared deadline is spent. Optional locks are off so a read-only status
    never rewrites the index under a concurrent git."""
    if _deadline is None:
        return None  # main() starts the budget; no budget, no git call
    remaining = _deadline - time.monotonic()
    if remaining <= 0:
        return None
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True,
            timeout=min(_PER_CALL_S, remaining),
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    # A tracked file name need not be UTF-8 (`ls-files -z` and `status -z`
    # emit it raw): surrogateescape keeps it round-trippable instead of
    # raising UnicodeDecodeError out of the hook.
    return out.stdout.decode("utf-8", "surrogateescape")


def modified_submodules(cwd):
    """(found, toplevel) where found lists (path, pinned_sha, head_sha) for
    each submodule whose gitlink would change if every modified tracked path
    were staged; None if git cannot be run here."""
    # `--ignore-submodules=dirty` skips scanning every submodule worktree for
    # edits (slow, and irrelevant: dirty content cannot change a gitlink) but
    # still reports a submodule whose checked-out commit moved.
    # `-uno` skips the untracked scan, which `-a`/`-u` never stage anyway and
    # which dominates the time in a large tree.
    status = _git(cwd, "status", "--porcelain=v1", "-z", "-uno",
                  "--ignore-submodules=dirty")
    top = _git(cwd, "rev-parse", "--show-toplevel")
    # ONE index read for every gitlink, rather than a query per modified path:
    # a large sweep would otherwise spend the whole deadline and fail open
    # exactly when the sweep is big.
    # Run from the root: from a subdirectory it would list only that subtree,
    # with paths relative to it, while status paths are root-relative.
    if status is None or top is None:
        return None
    top = top.strip()
    index = _git(top, "ls-files", "-s", "-z")
    if index is None:
        return None
    gitlinks = {}
    for entry in index.split("\0"):
        meta, _, entry_path = entry.partition("\t")
        fields = meta.split()
        if len(fields) == 3 and fields[0] == "160000":
            gitlinks[entry_path] = fields[1]
    records = status.split("\0")
    found = []
    i = 0
    while i < len(records):
        rec = records[i]
        i += 1
        if len(rec) < 4:
            continue
        xy, path = rec[:2], rec[3:]
        if xy[0] in ("R", "C"):
            i += 1
        if xy[1] != "M":
            continue
        pinned = gitlinks.get(path)  # only a gitlink (mode 160000) counts
        if pinned is None:
            continue
        head = _git(os.path.join(top, path), "rev-parse", "HEAD")
        if head is None:
            continue
        head = head.strip()
        if head != pinned:
            found.append((path, pinned, head))
    return found, top


def _under_pathspecs(sub_path, pathspecs, cwd, top, sweeping):
    """M7: does a pathspec given from `cwd` stage the submodule at `sub_path`
    (repo-root relative, `top` the repo root)?

    `sweeping` is `add -u`/`-A`: no pathspec means the whole repo, a pathspec
    naming the submodule itself counts, and a magic (`:/`) or glob pathspec,
    which is not evaluated, warns. A plain `git add <pathspec>` counts only a
    pathspec that covers the submodule from above (`.`, a parent directory):
    naming the submodule is how a pin bump is staged on purpose, and a magic
    or glob pathspec there stays silent. Both sides go through realpath, so a
    symlinked cwd cannot make the relative path miss."""
    if not pathspecs:
        return sweeping
    real_cwd, real_top = os.path.realpath(cwd), os.path.realpath(top)
    for p in pathspecs:
        if p.startswith(":") or any(ch in p for ch in "*?["):
            if sweeping:
                return True
            continue
        if os.name == "nt":
            p = p.replace("\\", "/")  # Windows separators only
        rel = os.path.relpath(os.path.normpath(os.path.join(real_cwd, p)),
                              real_top)
        if os.name == "nt":
            rel = rel.replace("\\", "/")
        covers = (rel == "." or sub_path == rel
                  or sub_path.startswith(rel + "/"))
        if covers and (sweeping or rel != sub_path):
            return True
    return False


# What each kind stages, for the message.
_STAGES = {
    "commit -a": "every modified tracked path",
    "add -u": "every modified tracked path",
    "add -A": "every change",
    "add": "every change",
}

NOTE = (
    "This `git {kind}` stages {stages}{scope}, and {count} "
    "submodule(s) here sit at a different commit than the index pins, so "
    "{which} commit would MOVE the pin(s):\n\n"
    "  command:  {segment}\n"
    "  submodule (pinned -> checked out):\n{lines}\n\n"
    "On 2026-10-15 `git commit -am` did exactly this in Morrison-Lab/lds#1026: "
    "it carried a `CLAUDE.md` edit and moved `latex-macros` from 6e227b6 to an "
    "older 85c285b, and the PR bot flagged it as blocking.\n\n"
    "If the pin bump is intended, carry on. Otherwise stage only what you "
    "mean (`git add <paths>`), commit with paths (`git commit -- <paths>`), "
    "or check the submodule out at the pinned commit first "
    "(`git submodule update <path>`, after checking that the submodule's "
    "own commits are pushed or on a branch: the update detaches HEAD and "
    "can leave unpushed commits reachable only through the reflog)."
)


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
        print(f"flag-commit-a-sweeps-submodule: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    _start_budget()
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    def quiet():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell"):
        return quiet()

    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script")
    if not isinstance(command, str) or not command.strip():
        return quiet()

    try:
        hits = offending(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-commit-a-sweeps-submodule: could not parse command ({exc})",
              file=sys.stderr)
        return 0

    # Every match is checked: one that is filtered out (a pathspec that
    # excludes the submodule, a missing directory) must not hide a later one.
    # The directory the command runs from is the payload's, not this
    # process's: tool_input.Cwd, then the payload's `cwd`, then ours.
    base = next((c for c in (inp.get("Cwd"), payload.get("cwd"))
                 if isinstance(c, str) and c), None) or os.getcwd()
    state = {}  # cwd -> modified_submodules(cwd), one status per repository
    for segment, kind, target, pathspecs in hits:
        cwd = os.path.normpath(os.path.join(base, target))
        if not os.path.isdir(cwd):
            continue
        if cwd not in state:
            state[cwd] = modified_submodules(cwd)
        if not state[cwd]:
            continue
        subs, top = state[cwd]
        if pathspecs is not None:
            subs = [s for s in subs
                    if _under_pathspecs(s[0], pathspecs, cwd, top,
                                        kind != "add")]
        if subs:
            return warn(segment, kind, pathspecs, subs)
    return quiet()


def warn(segment, kind, pathspecs, subs):
    """Print the warning for `subs` and return the exit status."""
    lines = "\n".join(f"    {p}: {a[:7]} -> {b[:7]}" for p, a, b in subs)
    # Only `commit -a` commits what it stages; the `add` forms leave the pin
    # moved for the NEXT commit.
    which = "this" if kind == "commit -a" else "the next"
    scope = f" under {', '.join(pathspecs)}" if pathspecs else ""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                kind=kind, stages=_STAGES[kind], scope=scope,
                count=len(subs), segment=segment, lines=lines,
                which=which),
        },
        "systemMessage": (
            f"`git {kind}` would stage a moved pin, so {which} commit "
            f"would move it"
            + f" ({len(subs)} submodule(s)): "
            + ", ".join(p for p, _, _ in subs) + "."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
