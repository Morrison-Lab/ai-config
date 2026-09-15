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
import subprocess
from pathlib import Path
from typing import Iterator

SCRIPT_SUFFIXES = (".py", ".sh")
# The one variable the plugin loader sets and a shell does not.
PLUGIN_ROOT_VAR = "CLAUDE_PLUGIN_ROOT"
# A BARE Windows drive-letter path, at the start, after whitespace or after
# a flag's `=`, with either separator after the colon: the one shape whose
# backslashes are separators that a POSIX shlex would eat. Inside double
# quotes shlex keeps
# a backslash unless it precedes a quote, a backslash, a dollar sign or a
# backtick, so a quoted Windows path needs no help.
RX_BARE_DRIVE_PATH = re.compile(r"(?:^|(?<=[\s=]))[A-Za-z]:[/\\]\S*")
# A leading `NAME=value` environment assignment, which precedes the command
# rather than being it. Anchored whole, so a path containing `=` is untouched.
RX_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*=")


def script_token(command: str) -> str | None:
    """The argument of `command` that names the hook script, or None.

    None means this command's shape is not one this module can read -- a
    wrapper, a shell one-liner, an interpreter invoked with no script. That
    is a `skipped`, not a finding.
    """
    # A POSIX shlex eats a bare backslash as an escape, which turns an
    # unquoted Windows path into one word with no separators. Double the
    # backslashes inside each bare drive-letter path only, so shlex hands
    # them back as themselves while an escaped space elsewhere in the same
    # command keeps its escape.
    protected = RX_BARE_DRIVE_PATH.sub(
        lambda m: m.group(0).replace('\\', '\\' + '\\'), command)
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


def interpreter_token(command: str) -> str | None:
    """The interpreter `command` invokes, or None when it runs a script directly.

    `"<path>/foo.sh"` runs itself and has no interpreter; `python3 "<path>"`
    has one. Returns the token as written, because the *spelling* is the whole
    question: a bare name is resolved through PATH at fire time by whatever
    process the harness spawns, which is not this one.
    """
    protected = RX_BARE_DRIVE_PATH.sub(
        lambda m: m.group(0).replace('\\', '\\' + '\\'), command)
    try:
        tokens = shlex.split(protected, posix=True)
    except ValueError:
        tokens = command.split()
    # `VAR=value python3 script.py` is one command with a leading assignment,
    # not a command named `VAR=value`. Dropping the prefix keeps the row
    # probeable; keeping it would make the row silently contribute nothing,
    # which is the failure mode this whole check exists to remove.
    while tokens and RX_ENV_ASSIGNMENT.match(tokens[0]):
        tokens = tokens[1:]
    if not tokens or tokens[0].endswith(SCRIPT_SUFFIXES):
        return None
    return tokens[0]


# Asks the interpreter itself whether it can see a path, which is the question
# `Path.is_file()` in THIS process cannot answer for it -- see probe_interpreter.
_PROBE = "import os, sys; sys.exit(0 if os.path.exists(sys.argv[1]) else 1)"


def probe_interpreter(interpreter: str, script: str, timeout: float = 15) -> str:
    """Can `interpreter` actually read `script`? One of ok/blind/unlaunchable/unknown.

    `classify_command` above answers "does this path exist", asked by this
    process. That is a different question from "can the interpreter the hook
    command names open this file", and on Windows the two disagree: bare
    `python3` commonly resolves to the Microsoft Store App Execution Alias,
    which runs a real interpreter inside a packaged-app filesystem view with no
    access to `%APPDATA%\\Claude`. Every hook then dies on a file `Path.is_file`
    reports as plainly there, `--check` reports `ok` for all of them, and the
    session is fully blocked with nothing pointing at the interpreter
    ([#3624](https://github.com/Morrison-Lab/ai-config/issues/3624)).

    So the probe is executed, not reasoned about. Only Python interpreters are
    probed: `-c` is a Python flag, and handing it to `sh` or `node` would test
    the prober rather than the hook.

    Five verdicts, and only two of them are observations. `ok` and `blind` mean
    the interpreter ran and answered; `blind` is the finding this exists for --
    it reported a file that is right there as absent. `unlaunchable`,
    `timeout` and `unknown` each mean the probe reached no answer, and they are
    kept apart rather than folded together because each licenses a different
    next step. None of them is evidence of the Store-alias condition: claiming
    a cause nobody observed is what sent #3624 looking at the plugin cache for
    hours.
    """
    if not Path(interpreter).name.lower().startswith("python"):
        return "skipped"
    try:
        done = subprocess.run([interpreter, "-c", _PROBE, script],
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Caught ahead of the clause below because TimeoutExpired IS a
        # SubprocessError, so folding the two would report an interpreter that
        # launched fine and then hung as one that never launched -- a false
        # statement about the more alarming of the two observations.
        return "timeout"
    except (OSError, subprocess.SubprocessError):
        return "unlaunchable"
    return {0: "ok", 1: "blind"}.get(done.returncode, "unknown")


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
