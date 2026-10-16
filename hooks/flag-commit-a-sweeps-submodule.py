#!/usr/bin/env python3
"""PreToolUse guard: `git commit -a`/`--all` (or `git add -u`/`--update`)
while a submodule's checked-out commit differs from the one the index pins.

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
at submodules at all.

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
      or `add` with `-u`/`--update`
  M4  the target repository is the `-C` directory, applied on top of the
      session cwd and of any earlier `cd <dir>` in the same command
  M5  `git status --porcelain=v1 -z --ignore-submodules=dirty` there lists
      an entry whose worktree column is `M` and whose path has mode 160000
      in `git ls-files -s`
  M6  the submodule's own HEAD differs from the commit the index pins -- an
      ` M` that is only dirty submodule CONTENT leaves the gitlink unchanged
      and cannot be swept in, so it stays silent (the status flag already
      drops it; this comparison is defence in depth). A pin bump already staged
      (`M ` with HEAD still equal to the staged pin) is silent too, while
      `MM` (staged, then the submodule moved again) warns
  M7  for `git add -u <pathspec>`, only a submodule at or under a pathspec
      counts, but a magic (`:/`) or glob pathspec is not evaluated and warns;
      `commit -a` takes no pathspec (git refuses the combination)

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
  - `GIT_DIR=...` or another environment prefix redirects git (not read).
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
# global options of `git` that consume the next token
_GIT_VALUE_GLOBAL = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                      "--exec-path", "--super-prefix", "--config-env"}


# The shared parser blanks heredoc bodies correctly (a command after
# `<<EOF ... EOF` stays its own command); a private copy did not.
_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from shellcmd import simple_commands as _simple_commands
    from shellcmd import strip_env as _strip_env
except Exception as _exc:  # broken install: fail open, like every guard here
    print("flag-commit-a-sweeps-submodule: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); inert", file=sys.stderr)
    _simple_commands = None


def _strip_lead(argv):
    """argv with leading env assignments, wrappers and keywords removed."""
    return _strip_env(argv)[1]


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
            i += 1  # --git-dir=x, --no-pager, -p, ...
        else:
            return c_dirs, a, rest[i + 1:]
    return None


def commit_sweeps_all(args):
    """M3 for `git commit`: true if `-a`/`--all` is among the options."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return False
        if a.startswith("--"):
            if a == "--all":
                return True
            if a in _COMMIT_VALUE_LONG:
                i += 1  # value is the next token
            i += 1
            continue
        if a.startswith("-") and a != "-":
            for pos, ch in enumerate(a[1:], start=1):
                if ch == "a":
                    return True
                if ch in _COMMIT_VALUE_SHORT:
                    if pos == len(a) - 1:
                        i += 1  # value is the next token
                    break
                if ch in "Su":
                    break  # optional attached value (-uall): rest of cluster
            i += 1
            continue
        i += 1
    return False


def add_update(args):
    """M3 for `git add`: (True, pathspecs) if `-u`/`--update` is present."""
    flags, paths, dashdash = [], [], False
    for a in args:
        if not dashdash and a == "--":
            dashdash = True
        elif not dashdash and a.startswith("-") and a != "-":
            flags.append(a)
        else:
            paths.append(a)
    for f in flags:
        if f == "--update":
            return True, paths
        if not f.startswith("--") and "u" in f[1:]:
            return True, paths
    return False, paths


def offending(command):
    """(segment, kind, target_dir, pathspecs) for the first matching
    invocation in `command`, or None. `target_dir` is the directory git
    would run in, relative to the session cwd unless absolute."""
    if _simple_commands is None:
        return None
    cmds = _simple_commands(command)
    if cmds is None:
        return None
    cd = ""
    for argv in cmds:
        rest = _strip_lead(argv)
        if len(rest) >= 2 and rest[0] == "cd":
            cd = os.path.join(cd, rest[1]) if rest[1] not in ("-",) else cd
            continue
        inv = _git_invocation(rest)
        if inv is None:
            continue
        c_dirs, sub, args = inv
        target = cd
        for d in c_dirs:
            target = os.path.join(target, d)
        if sub == "commit" and commit_sweeps_all(args):
            return " ".join(argv), "commit -a", target, None
        if sub == "add":
            hit, paths = add_update(args)
            if hit:
                return " ".join(argv), "add -u", target, paths
    return None


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
        _start_budget()
    remaining = _deadline - time.monotonic()
    if remaining <= 0:
        return None
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=min(_PER_CALL_S, remaining),
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def modified_submodules(cwd):
    """List of (path, pinned_sha, head_sha) for each submodule whose gitlink
    would change if every modified tracked path were staged; None if git
    cannot be run here."""
    # `--ignore-submodules=dirty` skips scanning every submodule worktree for
    # edits (slow, and irrelevant: dirty content cannot change a gitlink) but
    # still reports a submodule whose checked-out commit moved.
    status = _git(cwd, "status", "--porcelain=v1", "-z",
                  "--ignore-submodules=dirty")
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if status is None or top is None:
        return None
    top = top.strip()
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
        staged = _git(top, "ls-files", "-s", "--", path)
        if not staged:
            continue
        fields = staged.split(None, 3)
        if len(fields) < 3 or fields[0] != "160000":
            continue
        pinned = fields[1]
        head = _git(os.path.join(top, path), "rev-parse", "HEAD")
        if head is None:
            continue
        head = head.strip()
        if head != pinned:
            found.append((path, pinned, head))
    return found


def _under_pathspecs(sub_path, pathspecs, cwd):
    """M7: is `sub_path` (repo-root relative) covered by `git add -u`
    pathspecs given from `cwd`? No pathspec means the whole repo."""
    if not pathspecs:
        return True
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if top is None:
        return True  # cannot scope; the safe direction is to warn
    top = top.strip()
    for p in pathspecs:
        if p.startswith(":") or any(ch in p for ch in "*?["):
            # Magic (`:/`, `:(exclude)`) and glob pathspecs are not
            # evaluated; the safe direction is to warn, never to go silent.
            return True
        p = p.replace("\\", "/")  # Windows separators
        rel = os.path.relpath(os.path.normpath(os.path.join(cwd, p)), top)
        rel = rel.replace("\\", "/")
        if rel == "." or sub_path == rel or sub_path.startswith(rel + "/"):
            return True
    return False


NOTE = (
    "This `git {kind}` stages every modified tracked path, and {count} "
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
    "(`git submodule update <path>`)."
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
        hit = offending(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"flag-commit-a-sweeps-submodule: could not parse command ({exc})",
              file=sys.stderr)
        return 0
    if hit is None:
        return quiet()

    segment, kind, target, pathspecs = hit
    cwd = os.path.normpath(os.path.join(os.getcwd(), target))
    if not os.path.isdir(cwd):
        return quiet()
    subs = modified_submodules(cwd)
    if not subs:
        return quiet()
    if pathspecs is not None:
        subs = [s for s in subs if _under_pathspecs(s[0], pathspecs, cwd)]
        if not subs:
            return quiet()

    lines = "\n".join(f"    {p}: {a[:7]} -> {b[:7]}" for p, a, b in subs)
    # `add -u` only stages; the pin moves in the NEXT commit.
    which = "the next" if kind == "add -u" else "this"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                kind=kind, count=len(subs), segment=segment, lines=lines,
                which=which),
        },
        "systemMessage": (
            f"`git {kind}` would stage a moved pin"
            + (", so the next commit would move it" if which == "the next"
               else ", so this commit would move it")
            + f" ({len(subs)} submodule(s)): "
            + ", ".join(p for p, _, _ in subs) + "."
        ),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
