#!/usr/bin/env python3
"""PreToolUse guard: a process listing that prints other processes' argv.

THE MEASUREMENT (2026-09-13, ai-config#3626)
--------------------------------------------
A session diagnosing Databricks endpoint limits checked whether a background
probe was still alive:

    ps -eo pid,etime,command | grep -E "itpm2|curl" | grep -v grep

The `command` column is the process's full argv, and the probe was a `curl`
carrying `-H "Authorization: Bearer <token>"` from a shell variable --- the
recommended form. The harness printed what the command returned, so a live
OAuth bearer token landed in the session transcript.

The secret was handled correctly at every point in the code. The leak happened
at the INSPECTION step, which is why careful secret handling does not prevent
it: argv is readable by every process on the host, and any listing that prints
it copies whatever credentials it holds into the tool output, including those
of processes this session did not start.

WHAT IT CHECKS
--------------
Every simple command in the Bash command line, including those inside a
shell's `-c` argument, for a program that prints OTHER processes' command
lines or environments:

    ps       with a UNIX `-f`/`-F`, any BSD-style option cluster (`aux`, `ax`,
             `x`), or an explicit format naming `args`/`command`/`cmd`
    pgrep    with `-a` / `--list-full`
    pstree   with `-a` / `--arguments`
    top      with `-c`
    a read of `/proc/<pid>/cmdline` or `/proc/<pid>/environ`

The `ps` grammar modelled is Linux procps. macOS's BSD `ps` prints argv
for more forms than this (plain `ps -e` among them), so silence there is
weaker evidence than it is on Linux.

It stays silent on the forms that print only a name: `pgrep -f <pattern>`
(PIDs only), `ps -eo pid,etime,comm`, `ps -e`, and BSD `c` (`ps axc`), which
replaces argv with the executable name.

WHY THIS WARNS RATHER THAN BLOCKS
---------------------------------
`ps aux` is common and usually harmless: whether a listing leaks depends on
what else is running on the host, which the command text cannot show. The
issue that asked for this guard names that false-positive rate as the reason
to warn. The warning costs one line; the miss puts a credential in a
transcript that is stored, summarized, and sometimes posted.

Fails OPEN on any parse trouble, same as every guard here.
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (COMMAND_WRAPPERS, ENV_ASSIGNMENT, SHELL_KEYWORDS,
                          WRAPPER_ARG_WINDOW, shell_c_expansions,
                          simple_commands)
except Exception as _exc:  # broken install; fail open and say so
    print(f"flag-argv-printing-process-listing: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); not evaluating",
          file=sys.stderr)
    simple_commands = None

LISTERS = {"ps", "pgrep", "pstree", "top"}

# Format keys whose column is the full argv rather than the executable name.
ARGV_KEYS = {"args", "command", "cmd"}

# `ps` options that take a separate value, so the value is not misread as a
# BSD option cluster (`ps -C curl` names a process, it is not BSD `curl`).
PS_UNIX_VALUE_OPTS = set("CGgNpqstUuoO")
PS_LONG_VALUE_OPTS = {"--cols", "--columns", "--rows", "--lines", "--width",
                      "--format", "--group", "--Group", "--pid", "--ppid",
                      "--quick-pid", "--sid", "--tty", "--user", "--User",
                      "--sort"}
PS_BSD_VALUE_OPTS = set("oOptUk")

RX_PROC_LEAK = re.compile(r"/proc/[^/\s]+/(?:cmdline|environ)")


def _program(argv):
    """Index of ARGV's program token if it is a lister, else None.

    Leading assignments, shell keywords, and wrappers (`sudo`, `timeout 5`,
    `watch`) are skipped; past a wrapper, look ahead a bounded distance for a
    lister rather than modelling each wrapper's option grammar.
    """
    index, after_wrapper = 0, False
    while index < len(argv):
        token = argv[index]
        name = os.path.basename(token)
        if ENV_ASSIGNMENT.match(token) or token in SHELL_KEYWORDS:
            index += 1
            after_wrapper = False
            continue
        if name in COMMAND_WRAPPERS or name == "watch":
            index += 1
            after_wrapper = True
            continue
        if name in LISTERS:
            return index
        if after_wrapper:
            window = argv[index:index + WRAPPER_ARG_WINDOW]
            hit = next((offset for offset, candidate in enumerate(window)
                        if os.path.basename(candidate) in LISTERS), None)
            if hit is not None:
                return index + hit
        return None
    return None


def _format_keys(spec):
    """The column keys named in a `ps -o` format spec."""
    keys = set()
    for part in re.split(r"[,\s]+", spec):
        key = part.split("=", 1)[0].split(":", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def _ps_prints_argv(args):
    # `replaced`: an `-o`/`o`/`--format` replaced the default columns, so only
    # the named keys count. `-O` ADDS to the default, so it does not.
    formats, full, bsd, replaced = [], False, [], False
    i = 0
    while i < len(args):
        tok = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else ""
        if tok.startswith("--"):
            name, eq, value = tok.partition("=")
            if name == "--format":
                formats.append(value if eq else nxt)
                replaced = True
            if name in PS_LONG_VALUE_OPTS and not eq:
                i += 1
            i += 1
            continue
        if tok.startswith("-") and len(tok) > 1:
            cluster = tok[1:]
            # procps reads `ps -aux` as BSD `aux` (UNIX ps has no `-x`), so a
            # dashed cluster carrying `x` prints argv like the BSD form.
            if "x" in cluster:
                full = True
            for pos, ch in enumerate(cluster):
                if ch in "fF":
                    full = True
                if ch in PS_UNIX_VALUE_OPTS:
                    value = cluster[pos + 1:]
                    if not value:
                        value = nxt
                        i += 1
                    if ch in "oO":
                        formats.append(value)
                        replaced = replaced or ch == "o"
                    break
            i += 1
            continue
        if re.fullmatch(r"[A-Za-z]+", tok):
            bsd.append(tok)
            for pos, ch in enumerate(tok):
                if ch in PS_BSD_VALUE_OPTS:
                    value = tok[pos + 1:]
                    if not value:
                        value = nxt
                        i += 1
                    if ch in "oO":
                        formats.append(value)
                        replaced = replaced or ch == "o"
                    break
        i += 1
    keys = set().union(*(_format_keys(spec) for spec in formats)) if formats else set()
    if keys & ARGV_KEYS:
        return True
    if replaced:
        return False
    if full:
        return True
    # BSD mode prints argv unless `c` swaps it for the executable name; `e`
    # appends the environment, which is worse, so it fires even with `c`.
    return any("c" not in tok or "e" in tok for tok in bsd)


def _cluster_has(args, short, longs):
    for tok in args:
        if tok in longs:
            return True
        if tok.startswith("-") and not tok.startswith("--") and short in tok[1:]:
            return True
    return False


def _leak(argv):
    """A description of how ARGV prints other processes' argv, or None."""
    for tok in argv:
        if RX_PROC_LEAK.fullmatch(tok):
            return f"reads `{tok}`"
    index = _program(argv)
    if index is None:
        return None
    name = os.path.basename(argv[index])
    args = argv[index + 1:]
    shown = " ".join(argv[index:])
    if name == "ps" and _ps_prints_argv(args):
        return f"`{shown}` lists full command lines"
    if name == "pgrep" and _cluster_has(args, "a", {"--list-full"}):
        return f"`{shown}` lists full command lines"
    if name == "pstree" and _cluster_has(args, "a", {"--arguments"}):
        return f"`{shown}` lists full command lines"
    if name == "top" and _cluster_has(args, "c", set()):
        return f"`{shown}` lists full command lines"
    return None


def find_leak(command):
    for line in shell_c_expansions(command):
        argvs = simple_commands(line)
        if not argvs:
            continue
        for argv in argvs:
            found = _leak(argv)
            if found:
                return found
    return None


NOTE = (
    "{found}. Process argv is readable by every process on the host, so this "
    "prints any credential another process carries on its command line --- a "
    "`curl -H \"Authorization: Bearer ...\"` header, a `--token` flag --- into "
    "the transcript, including processes this session did not start "
    "(measured 2026-09-13: `ps -eo pid,etime,command` printed a live bearer "
    "token, ai-config#3626).\n\n"
    "To test liveness, `pgrep -f <pattern>` prints PIDs only. For detail, name "
    "the executable rather than argv: `ps -o pid,etime,comm -p <pid>`. "
    "And keep your own secrets out of argv in the first place: pass them on "
    "stdin, in a file (`curl -H @file`), or in an unechoed environment "
    "variable. See memories/shell.md, \"Process listings print argv\".\n\n"
    "If nothing on this host carries a credential in argv, carry on --- this "
    "is a reminder, not a refusal."
)


def main() -> int:
    if simple_commands is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail open
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return 0
    try:
        found = find_leak(command)
    except Exception:
        return 0  # fail open
    if not found:
        return 0
    # No `permissionDecision` key: an absent decision defers to the normal
    # permission flow rather than suppressing a prompt.
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(found=found),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"{found}: argv can carry other processes' credentials into the "
            "transcript. `pgrep -f` or `ps -o pid,comm` print no argv."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
