#!/usr/bin/env python3
"""PreToolUse (Bash): warn before a blanket one-side conflict resolution.

ai-config#5407, split from #4716.
Ezra, 2026-10-23: agents should resolve merge conflicts carefully,
deciding for each hunk what to keep from each side, what to drop,
and what to modify.
`skills/resolve-conflicts/SKILL.md` lists these commands as anti-patterns:

- `git checkout|restore --ours|--theirs`, which take the whole file from one
  side, so the other side's changes in it are lost, conflicting or not.
- `git merge-file --ours|--theirs`, and `-X ours|theirs` (also `-Xours`,
  `--strategy-option[=]ours`) on `merge`, `rebase`, `cherry-pick`, `revert`
  or `pull`. Each keeps one side of every conflicting hunk without a
  per-hunk decision.
- `-s ours` (also `-sours`, `--strategy[=]ours`), which drops the other
  side's changes entirely, conflicting or not. On `cherry-pick` and
  `revert`, `-s` is `--signoff`, so only `--strategy` counts there.

Git accepts a unique prefix of a long option. `--our`, `--thei` and
`--strategy-opt=ours` count, and so does `--t` on `restore` and
`merge-file`, where nothing else starts with it.
`checkout -2|-3` and `restore -2|-3` are the short forms of `--ours|--theirs`,
also inside a short-option cluster such as `-W3`.
A prefix of `--strategy` itself also starts `--strategy-option`,
so git rejects it as ambiguous (`--strat=ours`).
A command inside `bash -c '...'` (and `sh`, `zsh` and similar) is checked,
up to MAX_DEPTH nested shells; one fed through `xargs` or `eval` is not.
A merge, rebase, cherry-pick, revert or pull run with `--abort` or
`--quit` before any `--` resolves nothing and stays silent.
Short options are read in clusters (`-qs ours`, `-fXours`),
and the value of an option in SHORT_VALUE_REQUIRED, SHORT_VALUE_OPTIONAL or
LONG_WITH_VALUE (the message of `-m`, say) is never read as an option.
A value of any other option (`--onto -X ours`) is, which can only add a
warning on a command git would reject.
Not covered: `git checkout-index --stage=2|3`, `git show :2:path > path`,
and git aliases (`git co --ours`).

Warns, never blocks: one side can be right, for example a generated file the
repo's tooling regenerates afterwards. Quoted text, such as an `echo` of the
command, is not a command and does not fire. Fails open on a parse error.
"""
from __future__ import annotations

import json
import os
import sys

# The shared splitter (ai-config#3178). A broken install fails open, saying so.
try:
    _LIB = os.path.join(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__))), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import git_subcommand, nested_shell_commands, simple_commands
except Exception as _exc:  # broken install: degrade, never block
    print(f"warn-one-sided-conflict-resolution: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); no command will be checked",
          file=sys.stderr)
    git_subcommand = nested_shell_commands = simple_commands = None

SIDES = ("ours", "theirs")
PATH_SIDE_SUBCOMMANDS = ("checkout", "restore", "merge-file")
MERGING_SUBCOMMANDS = ("merge", "rebase", "cherry-pick", "revert", "pull")
STRATEGY_SHORT_SUBCOMMANDS = ("merge", "rebase", "pull")
NO_RESOLUTION = ("--abort", "--quit")
# Shortest unambiguous prefix per subcommand, from each one's `-h` option
# list: `--o` also starts --overlay (checkout, restore), --orphan (checkout)
# and --object-id (merge-file); `--t` also starts --track on checkout only.
SIDE_PREFIX_MIN = {
    "checkout": {"--ours": "--ou", "--theirs": "--th"},
    "restore": {"--ours": "--ou", "--theirs": "--t"},
    "merge-file": {"--ours": "--ou", "--theirs": "--t"},
}
# checkout and restore also spell the sides as stage numbers, and a short
# option that takes a value ends a cluster: `-b3` names a branch `3`.
SIDE_SHORT = {"2": "--ours", "3": "--theirs"}
SHORT_WITH_VALUE = {"checkout": "bB", "restore": "s"}
# `--strategy-` already excludes `--strategy`, the only other `--strategy...`.
LONG_PREFIX_MIN = {"--strategy-option": "--strategy-"}
# Short options that take a value, per `git <sub> -h`. A required value is
# the rest of the cluster or else the next word (`-m -X` is a message `-X`);
# an optional one (`-S`, `-r`, `-j`) is only the rest of the cluster.
SHORT_VALUE_REQUIRED = {
    "merge": "sXmF", "rebase": "sXx", "pull": "sXo",
    "cherry-pick": "Xm", "revert": "Xm",
}
SHORT_VALUE_OPTIONAL = {
    "merge": "S", "rebase": "Sr", "pull": "Srj", "cherry-pick": "S", "revert": "S",
}
LONG_WITH_VALUE = (
    "--message", "--file", "--exec", "--server-option", "--mainline",
    "--cleanup", "--into-name",
)
MAX_DEPTH = 3


def _side_flag(sub: str, arg: str) -> str | None:
    """`--ours` or `--theirs` when ARG is that flag, a unique prefix of it on
    SUB, or (checkout and restore) its `-2`/`-3` short form, alone or in a
    cluster."""
    if sub in SHORT_WITH_VALUE and arg[:1] == "-" and arg[:2] != "--":
        for c in arg[1:]:
            if c in SHORT_WITH_VALUE[sub]:
                return None
            if c in SIDE_SHORT:
                return SIDE_SHORT[c]
        return None
    for flag, shortest in SIDE_PREFIX_MIN[sub].items():
        if arg.startswith(shortest) and flag.startswith(arg):
            return flag
    return None


def _option_values(sub: str, rest: list[str], letter: str | None,
                   long: str) -> list[str]:
    """Values SUB's argv REST gives to `-LETTER` or to `long`.

    Walks the words the way git's option parser does: a short option may sit
    in a cluster (`-qs ours`, `-fXours`), a value is never read as an option,
    and `long` also matches a unique prefix of itself at least
    LONG_PREFIX_MIN long. LETTER is None where the short form means
    something else (`-s` is --signoff on cherry-pick and revert).
    """
    shortest = LONG_PREFIX_MIN.get(long, long)
    required = SHORT_VALUE_REQUIRED[sub]
    optional = SHORT_VALUE_OPTIONAL[sub]
    values = []
    i = 0
    while i < len(rest):
        arg = rest[i]
        i += 1
        if arg == "--":
            break
        if arg.startswith("--"):
            name, eq, value = arg.partition("=")
            if name.startswith(shortest) and long.startswith(name):
                if not eq:
                    value = rest[i] if i < len(rest) else ""
                    i += 1
                values.append(value)
            elif name in LONG_WITH_VALUE and not eq:
                i += 1
            continue
        if not arg.startswith("-"):
            continue
        for j, c in enumerate(arg[1:], start=1):
            if c not in required and c not in optional:
                continue
            value = arg[j + 1:]
            if c in required and not value:
                value = rest[i] if i < len(rest) else ""
                i += 1
            if c == letter:
                values.append(value)
            break
    return values


def one_sided(argv: list[str]) -> tuple[str, str] | None:
    """(command text, what it drops) for a one-side resolution, else None."""
    parsed = git_subcommand(argv)
    if parsed is None:
        return None
    sub, rest, _env = parsed
    hunks = "keeps one side of every conflicting hunk without a per-hunk decision"
    if sub in PATH_SIDE_SUBCOMMANDS:
        # merge-file still merges the clean hunks; checkout and restore take
        # the whole stage-2 or stage-3 file.
        effect = hunks if sub == "merge-file" else (
            "takes the whole file from one side, dropping the other side's "
            "changes in it, conflicting or not")
        for arg in rest:
            if arg == "--":
                break
            flag = _side_flag(sub, arg)
            if flag:
                return f"git {sub} {flag}", effect
        return None
    if sub in MERGING_SUBCOMMANDS:
        options = rest[:rest.index("--")] if "--" in rest else rest
        if any(arg in NO_RESOLUTION for arg in options):
            return None
        for value in _option_values(sub, rest, "X", "--strategy-option"):
            if value in SIDES:
                return f"git {sub} -X {value}", hunks
        # On cherry-pick and revert, `-s` is --signoff, so only the long form
        # names a strategy there.
        letter = "s" if sub in STRATEGY_SHORT_SUBCOMMANDS else None
        for value in _option_values(sub, rest, letter, "--strategy"):
            if value == "ours":
                label = "-s ours" if letter else "--strategy ours"
                return (f"git {sub} {label}",
                        "drops the other side's changes entirely, "
                        "conflicting or not")
    return None


def warning(found: str, effect: str) -> str:
    return (
        f"[hook: warn-one-sided-conflict-resolution] `{found}` {effect}, so "
        "the other side's work can be lost silently. Resolve each hunk instead: "
        "decide what to keep from each side, what to drop and what to modify, "
        "and record it in the merge commit message or PR comment "
        "(skills/resolve-conflicts/SKILL.md). Keep this command only when you "
        "have confirmed the dropped side holds nothing worth keeping, for example "
        "a generated file the repo's tooling regenerates. ai-config#5407."
    )


def evaluate(command: str, depth: int = 0) -> str | None:
    if simple_commands is None or depth > MAX_DEPTH:
        return None
    cmds = simple_commands(command)
    if not cmds:
        return None
    for argv in cmds:
        found = one_sided(argv)
        if found:
            return warning(*found)
        for inner in nested_shell_commands(argv):
            text = evaluate(inner, depth + 1)
            if text:
                return text
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    try:
        text = evaluate(command)
    except Exception as exc:  # a hook bug must never block a command
        print(f"warn-one-sided-conflict-resolution: {exc}", file=sys.stderr)
        return 0
    if text:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": text,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
