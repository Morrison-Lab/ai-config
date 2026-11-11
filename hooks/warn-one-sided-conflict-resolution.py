#!/usr/bin/env python3
"""PreToolUse (Bash): warn before a blanket one-side conflict resolution.

ai-config#5407, split from #4716. Ezra, 2026-10-23: agents should resolve
merge conflicts carefully, deciding for each hunk what to keep from each
side, what to drop, and what to modify. `skills/resolve-conflicts/SKILL.md`
lists these commands as anti-patterns:

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
`--strategy-opt=ours` count. A prefix of `--strategy` itself also starts
`--strategy-option`, so git rejects it as ambiguous (`--strat=ours`).
A command inside `bash -c '...'` (and `sh`, `zsh` and similar) is checked,
up to MAX_DEPTH nested shells; one fed through `xargs` or `eval` is not.
A run with `--abort` or `--quit` resolves nothing and stays silent.

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
# Shortest unambiguous prefixes: `--o` also starts --orphan and --overlay,
# and `--t` also starts --track.
SIDE_PREFIX_MIN = {"--ours": "--ou", "--theirs": "--th"}
# `--strategy-` already excludes `--strategy`, the only other `--strategy...`.
LONG_PREFIX_MIN = {"--strategy-option": "--strategy-"}
MAX_DEPTH = 3


def _side_flag(arg: str) -> str | None:
    """`--ours` or `--theirs` when ARG is that flag or a unique prefix of it."""
    for flag, shortest in SIDE_PREFIX_MIN.items():
        if arg.startswith(shortest) and flag.startswith(arg):
            return flag
    return None


def _option_values(rest: list[str], short: str, long: str) -> list[str]:
    """Values given to `short` (`-X v` or `-Xv`) or `long` (`--long v` or `--long=v`).

    `long` also matches a unique prefix of itself at least LONG_PREFIX_MIN long.
    """
    shortest = LONG_PREFIX_MIN.get(long, long)
    values = []
    for i, arg in enumerate(rest):
        if arg == "--":
            break
        nxt = rest[i + 1] if i + 1 < len(rest) else ""
        name, eq, value = arg.partition("=")
        is_long = name.startswith(shortest) and long.startswith(name)
        if arg == short or (is_long and not eq):
            values.append(nxt)
        elif is_long:
            values.append(value)
        elif arg.startswith(short) and len(arg) > len(short):
            values.append(arg[len(short):])
    return values


def one_sided(argv: list[str]) -> tuple[str, str] | None:
    """(command text, what it drops) for a one-side resolution, else None."""
    parsed = git_subcommand(argv)
    if parsed is None:
        return None
    sub, rest, _env = parsed
    if any(arg in NO_RESOLUTION for arg in rest):
        return None
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
            flag = _side_flag(arg)
            if flag:
                return f"git {sub} {flag}", effect
        return None
    if sub in MERGING_SUBCOMMANDS:
        for value in _option_values(rest, "-X", "--strategy-option"):
            if value in SIDES:
                return f"git {sub} -X {value}", hunks
        # On cherry-pick and revert, `-s` is --signoff, so only the long form
        # names a strategy there.
        short = "-s" if sub in STRATEGY_SHORT_SUBCOMMANDS else "--strategy"
        for value in _option_values(rest, short, "--strategy"):
            if value == "ours":
                label = "-s ours" if short == "-s" else "--strategy ours"
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
