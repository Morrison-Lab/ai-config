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
import re
import shlex
from pathlib import Path
from typing import Iterator

SCRIPT_SUFFIXES = (".py", ".sh")
# The one variable the plugin loader sets and a shell does not.
PLUGIN_ROOT_VAR = "CLAUDE_PLUGIN_ROOT"
# A Windows drive-letter path, quoted or bare: the shape whose backslashes
# are separators rather than escapes.
RX_DRIVE_PATH = re.compile(r"(?:^|[\s\\\x22\x27])[A-Za-z]:\\")


def script_token(command: str) -> str | None:
    """The argument of `command` that names the hook script, or None.

    None means this command's shape is not one this module can read -- a
    wrapper, a shell one-liner, an interpreter invoked with no script. That
    is a `skipped`, not a finding.
    """
    # A POSIX shlex eats a bare backslash as an escape, which turns an
    # unquoted Windows path into one word with no separators. When the
    # command carries a drive-letter path, double every backslash first so
    # shlex hands each one back as itself; a POSIX command keeps its escapes
    # (an escaped space stays inside one word), so the two shapes cannot
    # share one rule.
    protected = command
    if RX_DRIVE_PATH.search(command):
        protected = command.replace('\\', '\\' + '\\')
    try:
        tokens = shlex.split(protected, posix=True)
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
    if PLUGIN_ROOT_VAR in path:
        return "skipped", path
    if "$" in path or "%" in path:
        # Any other variable this process cannot expand is one the harness
        # will not expand either, so the registration is broken, not merely
        # uncheckable.
        return "missing", path
    return ("ok" if Path(path).expanduser().is_file() else "missing"), path


def _iter_hooks(settings: dict) -> Iterator[tuple[str, str, dict]]:
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
                if isinstance(hook, dict):
                    yield event, matcher, hook


def registered_hooks(settings: dict) -> Iterator[tuple[str, str, str]]:
    """Yield (event, matcher, command) for every hook a settings dict binds."""
    for event, matcher, hook in _iter_hooks(settings):
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
