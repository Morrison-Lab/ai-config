#!/usr/bin/env python3
"""Read, check, and render the Antigravity plugin's hook manifest.

`plugins/ai-config/hooks.json` is the canonical manifest. `bootstrap.sh` used
to copy it verbatim into the Antigravity staging directory
(`~/.gemini/config/plugins/ai-config/hooks.json`), which is correct only where
`python3` is on PATH and the launcher expands `~`. Neither holds under
`cmd.exe`, so the staged copy on Windows was repaired by hand with quoted
absolute paths. Every `run_command` PreToolUse hook then failed to launch, with
`cmd.exe` reporting a backslash-prefixed quoted path as not recognized
(https://github.com/Morrison-Lab/ai-config/issues/3091).

The quoting is what fails, and it fails whether or not the repair wrote the
quotes correctly. Measured 2026-09-09: a launcher that hands the whole command
to `cmd.exe` as one argument re-escapes every embedded quote on the way, so a
correctly quoted path arrives carrying a leading backslash. The same two paths
unquoted launch and return `{"decision": "allow"}`. A Windows hook command
therefore has to carry no quotes at all.

That failure is invisible from both ends: Antigravity skips a hook whose
subprocess dies, and a headless `agy` run reports success and prints a work
summary listing files it never wrote.

This module is the shared half of the fix. `scripts/render-agy-hooks.py`
renders the staged manifest per platform instead of copying it, and
`scripts/check-agy-hook-commands.py` refuses both the escaped-quote form and,
on Windows, any quote at all.
"""
from __future__ import annotations

import copy
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Iterator, Tuple

# Built rather than typed: a doubled backslash does not always survive the
# transport that writes this file (see CLAUDE.md, "Tool transport collapses
# doubled backslashes").
BACKSLASH = chr(92)
ESCAPED_QUOTE = BACKSLASH + '"'

# cmd.exe parses each of these as command syntax. A Windows hook command is
# emitted unquoted (see `windows_problems`), so none of them can be carried.
CMD_METACHARACTERS = "&|<>^%()"

CANONICAL_INTERPRETER = "python3"
CANONICAL_PLUGIN_DIR = "~/.gemini/config/plugins/ai-config"
PLUGIN_SUBPATH = "plugins/ai-config"
MANIFEST_NAME = "hooks.json"


def gemini_config_dir() -> str:
    """Return the Antigravity config directory bootstrap.sh installs into.

    bootstrap.sh honours GEMINI_CONFIG_HOME and GEMINI_HOME, so a checker
    that hard-codes ~/.gemini reads the wrong file on a machine that sets
    either one, and reports a missing manifest instead of the real install.
    """
    config_home = os.environ.get("GEMINI_CONFIG_HOME")
    if config_home:
        return config_home
    gemini_home = os.environ.get("GEMINI_HOME")
    if gemini_home:
        return gemini_home + "/config"
    return "~/.gemini/config"


def install_plugin_dir() -> str:
    """Return the plugin directory this machine installs into."""
    return gemini_config_dir() + "/" + PLUGIN_SUBPATH


def staged_manifest_path() -> str:
    """Return the staged manifest path bootstrap.sh writes on this machine."""
    return os.path.expanduser(install_plugin_dir() + "/" + MANIFEST_NAME)

CommandVisitor = Callable[[str], str]


def iter_hooks(manifest: dict) -> Iterator[Tuple[str, dict]]:
    """Yield `(location, hook)` for every hook object carrying a command.

    Antigravity uses two shapes in one file: `PreToolUse` entries are groups
    carrying a `matcher` and a `hooks` list, while `Stop` and `PreInvocation`
    entries are flat hook objects. Both are walked here so a caller never has
    to know which event uses which. The hook dict itself is yielded rather
    than its command string, so a caller that rewrites commands and a caller
    that only reads them share one traversal.
    """
    for plugin, events in manifest.items():
        if not isinstance(events, dict):
            continue
        for event, entries in events.items():
            if not isinstance(entries, list):
                continue
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                where = f"{plugin}.{event}[{index}]"
                if isinstance(entry.get("hooks"), list):
                    for sub, hook in enumerate(entry["hooks"]):
                        if isinstance(hook, dict) and "command" in hook:
                            yield f"{where}.hooks[{sub}]", hook
                elif "command" in entry:
                    yield where, entry


def iter_commands(manifest: dict) -> Iterator[Tuple[str, str]]:
    """Yield `(location, command)` for every hook command in a manifest."""
    for where, hook in iter_hooks(manifest):
        yield where, hook["command"]


def map_commands(manifest: dict, visit: CommandVisitor) -> dict:
    """Return a deep copy of `manifest` with each command replaced by `visit(cmd)`."""
    out = copy.deepcopy(manifest)
    for _, hook in iter_hooks(out):
        hook["command"] = visit(hook["command"])
    return out


def command_problems(command: str) -> list[str]:
    """Return every launch-blocking defect in one hook command string.

    These are the defects that hold in any shell, so they are checked in the
    canonical manifest and the staged copy alike.
    """
    problems: list[str] = []
    if not isinstance(command, str) or not command.strip():
        problems.append("command is empty")
        return problems
    if ESCAPED_QUOTE in command:
        problems.append(
            "contains a backslash-escaped quote; the backslash is part of the "
            "value, so cmd.exe reads it as the first character of the program "
            "name and reports the path as not recognized (https://github.com/Morrison-Lab/ai-config/issues/3091). "
            "Write a plain quote and let the JSON encoder escape it."
        )
    if command.count('"') % 2:
        problems.append("has an odd number of double quotes, so a quoted path is unterminated")
    return problems


def canonical_problems(command: str) -> list[str]:
    """Return defects specific to the repo's own `plugins/ai-config/hooks.json`.

    The canonical manifest stays in the portable POSIX form and is rendered per
    platform at install time, so a platform-specific path written into it would
    be copied onto machines it does not fit.
    """
    problems = command_problems(command)
    if not isinstance(command, str):
        return problems
    if not command.startswith(CANONICAL_INTERPRETER + " "):
        problems.append(
            f"does not start with '{CANONICAL_INTERPRETER} '; the canonical "
            "manifest stays portable and scripts/render-agy-hooks.py resolves "
            "the interpreter per platform"
        )
    if CANONICAL_PLUGIN_DIR not in command:
        problems.append(f"does not reference {CANONICAL_PLUGIN_DIR}")
    return problems


def program_token(command: str) -> str:
    """Return the program name a shell would launch for `command`.

    Handles the one quoting form these manifests use: an optionally quoted
    first token. An empty return means the command carries no program at all.
    """
    text = command.strip()
    if not text:
        return ""
    if text.startswith('"'):
        end = text.find('"', 1)
        return text[1:end] if end > 0 else text[1:]
    return text.split()[0]


def program_resolves(command: str) -> bool:
    """Report whether the program `command` names exists on this machine.

    A bare name is looked up on PATH; anything with a separator is treated as
    a path, with `~` expanded, since a launcher that does not expand `~` is
    exactly what this module exists to work around.
    """
    program = program_token(command)
    if not program:
        return False
    if "/" in program or os.sep in program:
        return Path(os.path.expanduser(program)).exists()
    return shutil.which(program) is not None


def is_native_windows_path(path: str) -> bool:
    """Report whether `path` is a drive-letter path `cmd.exe` can resolve.

    An MSYS or Cygwin path such as `/c/Users/dougm` or `/mingw64/bin/python3`
    is a real path to the shell that produced it and nothing at all to
    `cmd.exe`, so writing one into a hook command reproduces the failure this
    module fixes.
    """
    text = path.replace(BACKSLASH, "/")
    return len(text) > 2 and text[1] == ":" and text[0].isalpha()


def is_windows() -> bool:
    """Report whether hook commands here will be launched by `cmd.exe`.

    `os.name` answers this for a native interpreter. An MSYS2 or Cygwin Python
    reports `posix` while the machine's launcher is still `cmd.exe`, so the
    environment is consulted too rather than rendering the POSIX form onto a
    Windows install.
    """
    if os.name == "nt":
        return True
    return sys.platform.startswith("cygwin") or bool(os.environ.get("MSYSTEM"))


def resolve_python_exe(windows: bool | None = None) -> str:
    """Return the interpreter to name in a rendered hook command.

    `AGY_HOOK_PYTHON` overrides everything, so a machine whose interpreter this
    cannot infer stays configurable. On Windows only a native drive-letter path
    is usable: an MSYS or Cygwin `sys.executable` such as
    `/mingw64/bin/python3.exe` means nothing to a `cmd.exe` launcher, and
    emitting it would reproduce the failure this module fixes. When neither the
    running interpreter nor anything on PATH is native, this raises rather than
    guessing a name that may not resolve.
    """
    override = os.environ.get("AGY_HOOK_PYTHON", "").strip()
    if override:
        return override
    if windows is None:
        windows = is_windows()
    if not windows:
        return CANONICAL_INTERPRETER
    candidates = [sys.executable or ""]
    candidates += [shutil.which(name) or "" for name in ("python", "python3", "py")]
    for candidate in candidates:
        native = candidate.replace(BACKSLASH, "/")
        if is_native_windows_path(native):
            return native
    raise ValueError(
        "cannot name a Windows interpreter for the hook commands: the running "
        f"interpreter is {sys.executable!r}, which cmd.exe cannot resolve, and "
        "no native python.exe was found on PATH. Set AGY_HOOK_PYTHON to an "
        "absolute drive-letter path such as C:/Python313/python.exe."
    )


def resolve_plugin_dir(windows: bool | None = None) -> str:
    """Return the plugin directory to name in a rendered hook command.

    Antigravity expands `~` on macOS and Linux, so the portable form is kept
    there. `cmd.exe` does not, so Windows gets the expanded absolute path.
    """
    if windows is None:
        windows = is_windows()
    plugin_dir = install_plugin_dir()
    if not windows:
        return plugin_dir
    expanded = os.path.expanduser(plugin_dir).replace(BACKSLASH, "/")
    if not is_native_windows_path(expanded):
        raise ValueError(
            f"expanded the plugin directory to {expanded!r}, which cmd.exe "
            "cannot resolve. Run scripts/render-agy-hooks.py under a native "
            "Windows Python rather than an MSYS or Cygwin one."
        )
    return expanded


def windows_problems(command: str) -> list[str]:
    """Return defects that hold only where `cmd.exe` launches the command.

    Measured 2026-09-09 on Windows 11: a launcher that hands the whole command
    to `cmd.exe` as ONE argument re-escapes every embedded quote on the way
    (this is what `subprocess.list2cmdline` does, and it reproduces the
    reported error exactly), so a correctly quoted path arrives with a
    backslash in front of it and `cmd.exe` reports it as not recognized. The
    quoting is therefore not repairable from inside the manifest: the command
    has to carry no quotes at all.
    """
    problems = command_problems(command)
    if not isinstance(command, str):
        return problems
    if '"' in command:
        problems.append(
            "contains a double quote; the launcher hands the command to "
            "cmd.exe as a single argument and re-escapes embedded quotes, so "
            "a quoted path arrives with a leading backslash and does not "
            "resolve (https://github.com/Morrison-Lab/ai-config/issues/3091). Use unquoted paths."
        )
    problems.extend(unrendered_posix_problems(command))
    problems.extend(cmd_metacharacter_problems(command))
    return problems


def unrendered_posix_problems(command: str) -> list[str]:
    """Return defects that mark a command as never having been rendered.

    A staged manifest still carrying the canonical POSIX form is the exact
    stale state https://github.com/Morrison-Lab/ai-config/issues/3091 reports, and `program_resolves` alone does not
    catch it: `python3` can sit on PATH as a Windows Store alias while
    `cmd.exe` still cannot expand the `~` that follows it.
    """
    problems = []
    if command.startswith(CANONICAL_INTERPRETER + " "):
        problems.append(
            f"still starts with '{CANONICAL_INTERPRETER} '; cmd.exe resolves "
            "no such program reliably, so this manifest was copied rather "
            "than rendered by scripts/render-agy-hooks.py"
        )
    if "~" in command:
        problems.append(
            "contains '~', which cmd.exe does not expand; a rendered Windows "
            "command carries an absolute path"
        )
    return problems


def cmd_metacharacter_problems(command: str) -> list[str]:
    """Return defects from characters `cmd.exe` parses as command syntax.

    A Windows command is emitted unquoted (see `windows_problems`), so every
    character quoting would otherwise neutralize is live. Checking only quotes
    and spaces leaves a path carrying `&` or `%` to be split or expanded.
    """
    found = sorted({c for c in CMD_METACHARACTERS if c in command})
    if not found:
        return []
    return [
        "contains " + ", ".join(repr(c) for c in found) + "; cmd.exe parses "
        "these as command syntax and the command is emitted unquoted, so the "
        "hook would be split or expanded rather than launched"
    ]


def describe_char(char: str) -> str:
    """Name a character the way an error message should read it.

    A bare repr reports a space as `' '`, which a reader scans straight past on
    the one path where the space is the whole problem.
    """
    names = {" ": "a space", '"': "a double quote"}
    return names.get(char, repr(char))


def assert_cmd_safe(path: str, role: str) -> None:
    """Fail fast on a path `cmd.exe` cannot be handed unquoted.

    Quoting is unavailable here (see `windows_problems`), so a path carrying a
    space has no correct rendering and stopping is the only honest answer.
    """
    unsafe = sorted({c for c in CMD_METACHARACTERS + ' "' if c in path})
    if unsafe:
        raise ValueError(
            f"the {role} path {path!r} contains "
            + ", ".join(describe_char(c) for c in unsafe)
            + ", and a Windows hook command cannot be quoted "
            "(https://github.com/Morrison-Lab/ai-config/issues/3091), so cmd.exe would parse it as command syntax. "
            "Point AGY_HOOK_PYTHON at an interpreter on a plain path, or "
            "install the plugin under one."
        )


def render_command(command: str, python_exe: str, plugin_dir: str, windows: bool) -> str:
    """Render one canonical command for the target platform.

    Fails fast on a command that is not in the canonical form, rather than
    emitting something a launcher would silently mishandle.
    """
    problems = canonical_problems(command)
    if problems:
        raise ValueError(f"cannot render {command!r}: {'; '.join(problems)}")
    script = command[len(CANONICAL_INTERPRETER) + 1:].strip()
    script = script.replace(CANONICAL_PLUGIN_DIR, plugin_dir, 1)
    if windows:
        assert_cmd_safe(python_exe, "interpreter")
        assert_cmd_safe(script, "hook script")
    return f"{python_exe} {script}"


def render_manifest(manifest: dict, windows: bool, python_exe: str = "", plugin_dir: str = "") -> dict:
    """Return `manifest` with every command rendered for the target platform."""
    python_exe = python_exe or resolve_python_exe(windows)
    plugin_dir = plugin_dir or resolve_plugin_dir(windows)
    return map_commands(
        manifest,
        lambda cmd: render_command(cmd, python_exe, plugin_dir, windows),
    )
