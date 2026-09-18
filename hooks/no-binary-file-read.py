#!/usr/bin/env python3
"""PreToolUse guard: a whole-file reader applied to a binary file.

## The incident

A session ran `cat` on a Windows executable
(`/c/Users/dougm/bin/godot`, a real PE binary) to find out what it was.
Roughly 10KB of binary garbage landed in the conversation context, wasting
context in an already-long session and yielding nothing usable. The intent
was reasonable -- identify an unfamiliar file -- the tool was wrong for it.

## Why this is hook-shaped rather than a prose rule

The condition is fully decidable at `PreToolUse` from the command text plus
the filesystem: the command is a whole-file reader, a path argument exists on
disk, and the file's first bytes contain a NUL. Nothing about it is a
judgment call. A prose rule is consulted at read time and broken at
composition time, which is the failure mode
[`no-mistake-without-a-hook.py`](no-mistake-without-a-hook.py) names.

## What fires and what does not

`cat`, `head`, `tail`, `less`, `more` applied to a path argument that
exists on disk and whose first ~8KB contain a NUL byte. `strings` is
deliberately NOT included -- it is the correct tool for exactly this case,
and flagging it would tell the reader to stop doing the right thing.
`head -c N` / `tail -c N` (and `--bytes[= ]N`) are exempt: a byte-bounded
read is already the remedy this guard would otherwise suggest, so warning on
it would be noise pointed at its own fix. `-n` (a LINE count) is not a byte
bound and does not exempt -- a binary file with few newlines can still dump
its entire contents under `-n 5`.

The NUL sniff is the decider. An extension match (`.exe`, `.png`, ...) is
only a fast-path shortcut that skips the read for an unambiguous case; it is
never treated as sufficient on its own, and a file whose extension is not on
the list is still sniffed.

## Why this warns rather than blocks

A hard block on a read tool would be more annoying than the mistake it
prevents -- there are legitimate reasons to inspect a binary's raw bytes
(a magic-number check, a corruption diagnosis), and a guard that refuses
those gets switched off, taking the real cases with it, per
[`deterministic-tools.md`](../shared/principles/deterministic-tools.md).

## How the warning is delivered

Through `hookSpecificOutput.additionalContext` on stdout, paired with a
one-line `systemMessage` outside Antigravity (whose adapter's `PreToolUse`
branch surfaces `additionalContext` and `systemMessage` separately, so
emitting both there prints the warning twice; see
[`flag-cd-into-main-checkout.py`](flag-cd-into-main-checkout.py), which this
hook's delivery shape is modelled on).

## Failure mode

Degrades silently -- no warning, no crash -- on a missing file, a
permission error, a directory, an unmatched glob (which never resolves to a
real path in the first place), a device/pseudo-filesystem path, or a
compound command this hook cannot parse.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

# ---------------------------------------------------------------------------
# Splitting a compound Bash command into simple-command argv lists.
#
# Same construction as `flag-add-a-outside-pathspec.py`'s `_simple_commands`:
# join `\`-continued lines, blank heredoc bodies, turn unquoted newlines into
# `;`, then let `shlex` (in punctuation-aware mode) do the real splitting and
# dequoting.
RX_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?\n[ \t]*\2\b", re.S)
_SHELL_OPS = set("();|&")

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Leading words that do not change WHICH file-reading command runs, so the
# real command name is whatever follows them. `env` is included here rather
# than given its own flag-skipping logic -- any `env`-only flags (`-i`, `-u
# NAME`) are simply skipped like any other flag by `_command_name` below,
# which is a heuristic simplification: it can misread a value-taking `env`
# flag's value as the command name on an unusual invocation, and the result
# is then not in TARGET_CMDS and the call is silently ignored -- a false
# negative, the safe direction for a warn-only guard.
LEAD_WORDS = {"sudo", "command", "exec", "nohup", "time", "doas", "env"}

TARGET_CMDS = {"cat", "head", "tail", "less", "more"}

# Paths that are never a "binary file mistakenly read" -- a device or
# pseudo-filesystem node either isn't a regular file (so the NUL sniff on it
# is meaningless) or can block/hang on open (`/dev/tty`, a FIFO).
DEVICE_PREFIXES = ("/dev/", "/proc/", "/sys/")
DEVICE_EXACT = {"/dev", "/proc", "/sys"}

# Fast-path only -- see the module docstring. The NUL sniff below is what
# actually decides; this list exists so an unambiguous case (a real .exe, a
# .png) does not pay for an open() + read() it does not need.
BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".obj", ".lib",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff",
    ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".tar", ".jar",
    ".pdf", ".class", ".pyc", ".pyd", ".wasm",
    ".mp3", ".mp4", ".mov", ".avi", ".wav", ".flac", ".ogg", ".webm",
    ".sqlite", ".sqlite3", ".db",
    ".ttf", ".otf", ".woff", ".woff2",
}

SNIFF_BYTES = 8192


def _simple_commands(cmd):
    """Split a shell command into simple-command argv lists; None on error."""
    cmd = re.sub(r"\\\r?\n", " ", cmd)
    cmd = RX_HEREDOC.sub("<<", cmd)
    cmd = cmd.replace("\n", ";")
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return None
    cmds, cur = [], []
    for t in toks:
        if t and set(t) <= _SHELL_OPS:
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


def _command_name(argv):
    """(name, remaining_args) -- name is None when argv is empty or all
    leading words/assignments."""
    i = 0
    while i < len(argv):
        tok = argv[i]
        if ASSIGNMENT.match(tok) or tok in LEAD_WORDS:
            i += 1
            continue
        break
    if i >= len(argv):
        return None, []
    name = argv[i].rsplit("/", 1)[-1]
    return name, argv[i + 1:]


# `head`/`tail` flags that consume a separate token as their value, so that
# value is never mistaken for a path argument.
_VALUE_FLAGS = {"-c", "-n", "--bytes", "--lines"}


def has_bounded_read(cmd_name, args):
    """True when `head`/`tail` was given an explicit byte limit (`-c`).

    `-n` (a LINE count) does NOT exempt: a binary file with few newlines can
    still dump its entire contents under `-n 5`. Only a BYTE bound is a real
    guarantee about how much gets read.
    """
    if cmd_name not in ("head", "tail"):
        return False
    for a in args:
        if a in ("-c", "--bytes"):
            return True
        if a.startswith("--bytes="):
            return True
        # `-c10`, `-c+10`, `-c-10` -- short option with an attached value.
        if a.startswith("-c") and len(a) > 2 and (a[2].isdigit() or a[2] in "+-"):
            return True
    return False


def extract_paths(cmd_name, args):
    """Non-flag arguments, treated as candidate file paths."""
    paths = []
    skip_next = False
    seen_dashdash = False
    for a in args:
        if skip_next:
            skip_next = False
            continue
        if not seen_dashdash and a == "--":
            seen_dashdash = True
            continue
        if not seen_dashdash and a.startswith("-") and a != "-":
            if cmd_name in ("head", "tail") and a in _VALUE_FLAGS:
                skip_next = True
            continue
        paths.append(a)
    return paths


def _is_device_path(path):
    norm = path.replace("\\", "/")
    if norm in DEVICE_EXACT:
        return True
    return any(norm.startswith(p) for p in DEVICE_PREFIXES)


def is_binary_file(path):
    """True when `path` exists, is a regular file, and its first bytes
    contain a NUL. False on anything else -- missing, a directory, a
    permission error, a device node -- rather than raising."""
    try:
        if _is_device_path(path):
            return False
        if not os.path.isfile(path):
            return False
        _, ext = os.path.splitext(path)
        if ext.lower() in BINARY_EXTENSIONS:
            return True
        with open(path, "rb") as fh:
            chunk = fh.read(SNIFF_BYTES)
        return b"\x00" in chunk
    except OSError:
        return False


def offending_reads(command, cwd):
    """[(cmd_name, raw_path, resolved_path)] for each whole-file read of a
    binary file found in `command`. Empty on anything unparseable."""
    found = []
    cmds = _simple_commands(command)
    if not cmds:
        return found
    for argv in cmds:
        name, args = _command_name(argv)
        if name not in TARGET_CMDS:
            continue
        if has_bounded_read(name, args):
            continue
        for raw_path in extract_paths(name, args):
            if not raw_path or raw_path == "-":
                continue
            try:
                resolved = os.path.normpath(
                    raw_path if os.path.isabs(raw_path)
                    else os.path.join(cwd, raw_path)
                )
            except (TypeError, ValueError):
                continue
            if is_binary_file(resolved):
                found.append((name, raw_path, resolved))
    return found


def evaluate(command, cwd):
    """Warning text, or None, for `command` run in directory `cwd`."""
    try:
        hits = offending_reads(command, cwd)
    except Exception:
        return None
    if not hits:
        return None
    name, raw_path, resolved = hits[0]
    extra = "" if len(hits) == 1 else f" ({len(hits) - 1} more such read(s) in this command.)"
    return (
        f"`{name} {raw_path}` reads a file whose contents look BINARY "
        f"(a NUL byte in the first {SNIFF_BYTES} bytes):{extra}\n\n"
        f"    {resolved}\n\n"
        "Dumping raw binary bytes into the conversation wastes context and "
        "returns nothing usable. Use the right tool instead:\n"
        f"  file {raw_path}                to identify the file type\n"
        f"  head -c 200 {raw_path} | xxd    to peek at the first bytes\n"
        f"  strings {raw_path} | head       to pull any embedded text"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    if payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
    ):
        return 0
    inp = payload.get("tool_input") or {}
    command = (inp.get("command") or inp.get("CommandLine")
               or inp.get("cmd") or inp.get("script") or "")
    if not command:
        return 0

    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        warning = evaluate(command, str(cwd))
    except Exception:
        return 0
    if not warning:
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": warning,
        },
    }
    # See flag-cd-into-main-checkout.py's main() for why this is gated on
    # ANTIGRAVITY_AGENT: that adapter's PreToolUse branch prints
    # additionalContext AND every collected systemMessage separately, so a
    # payload carrying both would warn twice there.
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"`{command.strip().splitlines()[0][:80]}` looks like a "
            "whole-file read of a binary file. See additionalContext for "
            "the path and the remedy."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
