#!/usr/bin/env python3
"""Decide whether the script a settings.json hook command names resolves.

`install-hooks.py` answers whether the hooks this repo *ships* are bound, and
keys every status on `hooks/hooks.json`. This module answers the wider
question its `--check` mode asks: for every hook a settings file actually
registers, does the path inside its command point at a file that exists?

The distinction is not cosmetic. `python3 <missing file>` exits 2, and exit 2
is the `PreToolUse` deny signal, so one unresolvable absolute path denies
every tool call its matcher names -- and from inside the session that is
indistinguishable from the guard legitimately firing
([#2392](https://github.com/Morrison-Lab/ai-config/issues/2392)).

Three verdicts, and the third is the load-bearing one. A path this process
cannot expand (`${CLAUDE_PLUGIN_ROOT}` is set by the plugin loader, not by the
shell) is reported as `skipped`, never as `missing`: not checkable here is a
different finding from not present, and conflating them would report every
plugin-path install as broken.
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Iterator

SCRIPT_SUFFIXES = (".py", ".sh")


def script_token(command: str) -> str | None:
    """The argument of `command` that names the hook script, or None.

    None means this command's shape is not one this module can read -- a
    wrapper, a shell one-liner, an interpreter invoked with no script. That
    is a `skipped`, not a finding.
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        if token.endswith(SCRIPT_SUFFIXES):
            return token
    return None


def expand(token: str) -> str:
    """Expand the variables a settings.json hook path is written with.

    `$HOME` is substituted from `Path.home()` rather than from the
    environment, because a process whose `HOME` is unset would otherwise leave
    the commonest path form unexpanded and report it as `skipped`.
    """
    home = str(Path.home())
    text = token.replace("${HOME}", home).replace("$HOME", home)
    return os.path.expandvars(text)


def classify_command(command: str) -> tuple[str, str | None]:
    """Return (`ok` | `missing` | `skipped`, expanded path or None)."""
    token = script_token(command)
    if token is None:
        return "skipped", None
    path = expand(token)
    if "$" in path or "%" in path:
        return "skipped", path
    return ("ok" if Path(path).expanduser().is_file() else "missing"), path


def registered_hooks(settings: dict) -> Iterator[tuple[str, str, str]]:
    """Yield (event, matcher, command) for every hook a settings dict binds."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher") or ""
            for hook in group.get("hooks", []):
                command = hook.get("command")
                if command:
                    yield event, matcher, command


def check_settings(settings: dict) -> list[dict]:
    """One row per registered hook, carrying its path verdict."""
    rows = []
    for event, matcher, command in registered_hooks(settings):
        status, path = classify_command(command)
        rows.append({"event": event, "matcher": matcher, "command": command,
                     "status": status, "path": path})
    return rows
