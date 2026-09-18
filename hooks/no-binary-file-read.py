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

The NUL sniff is the decider for a file whose extension is not on the
BINARY_EXTENSIONS list -- that file is always sniffed, and only the sniff's
result decides. A file whose extension IS on the list is flagged on that
match alone, with no sniff at all: `BINARY_EXTENSIONS` is only a fast-path
shortcut in the sense that it exists to skip a read for an unambiguous case
(`.exe`, `.png`, ...), not in the sense that its match is provisional.

A path argument is resolved the way the SHELL would resolve it, not the way
this hook's own host OS would: a leading `/` is absolute regardless of
platform, a Git-Bash/MSYS (`/c/Users/...`) or WSL-mount (`/mnt/c/Users/...`)
drive spelling is translated to native form when this hook runs as a native
Windows Python process (the incident this hook exists to catch used exactly
that path shape), and a glob (`*.exe`) is expanded against the resolved
directory -- the shell that would normally do that expansion never actually
runs the command this hook only reads the text of. A redirection target
(`cat file > out.bin`) is excluded from the candidate paths; it is being
written, not read.

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
permission error, a directory, an unmatched glob, a device/pseudo-filesystem
path, or a compound command this hook cannot parse.
"""

from __future__ import annotations

import glob
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
# real command name is whatever follows them. `env`/`sudo` are included here
# rather than given their own flag-skipping logic: `_command_name` below has
# no notion of an `env`-only flag (`-i`, `-u NAME`) or a `sudo`-only flag
# (`-u user`) at all -- it just stops at the first token that is neither an
# assignment nor a LEAD_WORD, so `env -u NAME cat x` or `sudo -u user cat x`
# misreads the flag token itself (`-u`) as the command name. That name is
# then not in TARGET_CMDS, so the call is silently ignored -- a false
# negative, the safe direction for a warn-only guard, but a real gap rather
# than a handled case.
LEAD_WORDS = {"sudo", "command", "exec", "nohup", "time", "doas", "env"}

# Shell redirection operators, as `shlex` (in punctuation-aware mode) tokenizes
# them. A bare fd number immediately before one of these (`2>`, tokenized as
# separate `2` and `>` tokens with no way to tell it apart from `cat 2 > out`,
# an actual argument "2" followed by a redirect) is dropped along with the
# operator -- treating a lone digit before `>`/`>>`/`&>` as part of the
# redirect rather than a path is the conservative call for a warn-only guard:
# it costs a rare false negative (a file genuinely named "2") to avoid a
# common false positive (every `2>` fd redirect otherwise reading "2" as a
# path argument).
REDIR_OPS = {"<", ">", ">>", "<<", "<>", "&>", ">&", "&>>", "<&", "<<<", ">|"}

TARGET_CMDS = {"cat", "head", "tail", "less", "more"}

# Paths that are never a "binary file mistakenly read" -- a device or
# pseudo-filesystem node either isn't a regular file (so the NUL sniff on it
# is meaningless) or can block/hang on open (`/dev/tty`, a FIFO).
DEVICE_PREFIXES = ("/dev/", "/proc/", "/sys/")
DEVICE_EXACT = {"/dev", "/proc", "/sys"}

# See the module docstring: a match here flags on its own, no sniff. This
# list exists so an unambiguous case (a real .exe, a .png) does not pay for
# an open() + read() it does not need -- the NUL sniff only runs, and only
# decides, for an extension NOT on this list.
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


def _strip_redirections(args):
    """Drop shell redirection operators and their targets from an argv-like
    token list, along with a bare fd-number token immediately preceding one
    (see the REDIR_OPS comment above). Applied BEFORE both `has_bounded_read`
    and `extract_paths` so neither one has to know about redirection --
    `has_bounded_read` would otherwise miscount an unrelated `-c` written
    after a redirect, and `extract_paths` would otherwise read a redirection
    TARGET (something being written, not read) as a candidate path -- e.g.
    `cat note.txt > out.bin` misreading `out.bin` as a file `cat` reads.
    """
    out = []
    i = 0
    n = len(args)
    while i < n:
        a = args[i]
        if a in REDIR_OPS:
            if out and out[-1].isdigit():
                out.pop()
            i += 1
            if i < n:
                i += 1  # also drop the redirection target
            continue
        out.append(a)
        i += 1
    return out


# `head`/`tail` flags that consume a separate token as their value, so that
# value is never mistaken for a path argument.
_VALUE_FLAGS = {"-c", "-n", "--bytes", "--lines"}


def has_bounded_read(cmd_name, args):
    """True when `head`/`tail` was given an explicit byte limit (`-c`).

    `-n` (a LINE count) does NOT exempt: a binary file with few newlines can
    still dump its entire contents under `-n 5`. Only a BYTE bound is a real
    guarantee about how much gets read. Stops at a literal `--`, matching
    `extract_paths` below -- the two must agree on where the flag region
    ends, or a file literally named `-c` read via `head -- -c` would be
    wrongly exempted as if `-c` were still a flag there.
    """
    if cmd_name not in ("head", "tail"):
        return False
    for a in _strip_redirections(args):
        if a == "--":
            break
        if a in ("-c", "--bytes"):
            return True
        if a.startswith("--bytes="):
            return True
        # `-c10`, `-c+10`, `-c-10` -- short option with an attached value.
        if a.startswith("-c") and len(a) > 2 and (a[2].isdigit() or a[2] in "+-"):
            return True
    return False


def extract_paths(cmd_name, args):
    """Non-flag, non-redirection arguments, treated as candidate file paths."""
    paths = []
    skip_next = False
    seen_dashdash = False
    for a in _strip_redirections(args):
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


# A Bash command's paths are always POSIX, even when THIS hook itself runs
# as a native Windows Python process. `os.path.isabs('/c/Users/x')` is False
# under `ntpath` (no drive letter), so joining it onto `cwd` produces a
# garbage path that silently never matches a real file -- which is exactly
# the incident this hook exists to catch: `cat /c/Users/dougm/bin/godot`,
# verbatim, would have gone undetected on the platform it happened on.
def _posix_absolute(raw_path):
    return raw_path.startswith("/") or os.path.isabs(raw_path)


# Git-Bash/MSYS (`/c/Users/...`) and WSL-mount (`/mnt/c/Users/...`) spellings
# of a Windows drive path. A program actually EXEC'd by Git Bash gets this
# translation for free from the MSYS runtime; this hook only reads the
# command's TEXT and never runs it, so nothing translates it on its behalf.
_MSYS_DRIVE_RE = re.compile(r"^/([A-Za-z])(/.*)?$")
_WSL_DRIVE_RE = re.compile(r"^/mnt/([A-Za-z])(/.*)?$")


def _to_native(path):
    """Translate an MSYS/WSL drive path to native Windows form. A no-op
    everywhere else -- on a POSIX host a leading slash is already native."""
    if os.name != "nt":
        return path
    m = _WSL_DRIVE_RE.match(path) or _MSYS_DRIVE_RE.match(path)
    if not m:
        return path
    return f"{m.group(1).upper()}:{m.group(2) or '/'}"


def _resolve(raw_path, cwd):
    candidate = raw_path if _posix_absolute(raw_path) else os.path.join(cwd, raw_path)
    return os.path.normpath(_to_native(candidate))


GLOB_CHARS = frozenset("*?[")
# A pathological pattern (`**` over a huge tree) should cost this hook a
# bounded amount of work, not an unbounded glob walk -- capped rather than
# exhaustively matched.
MAX_GLOB_MATCHES = 200


def _candidates(raw_path, cwd):
    """Resolved filesystem path(s) `raw_path` could refer to.

    The shell that would normally expand a glob (`*.exe`) never actually
    runs this command -- this hook only reads its text -- so an unexpanded
    pattern must be expanded here, or a MATCHED glob is missed exactly like
    an unmatched one: the guard would stay silent on `cat *.exe` even when
    the directory holds exactly one binary file, which is a second shape of
    this hook's own founding incident. An UNMATCHED pattern still yields
    nothing, which is correct -- it was never a real path.
    """
    resolved = _resolve(raw_path, cwd)
    if not any(ch in raw_path for ch in GLOB_CHARS):
        return [resolved]
    try:
        return glob.glob(resolved)[:MAX_GLOB_MATCHES]
    except OSError:
        return []


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
                candidates = _candidates(raw_path, cwd)
            except (TypeError, ValueError):
                continue
            for resolved in candidates:
                if is_binary_file(resolved):
                    found.append((name, raw_path, resolved))
                    break  # one hit is enough to warn on this argument
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
