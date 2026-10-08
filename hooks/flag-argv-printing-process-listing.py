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
it: argv is readable by any process that can see it in /proc, which on a
default Linux mount (no `hidepid`, one PID namespace) is every process on the
host. Any listing that prints it copies whatever credentials it holds into the
tool output, including those of processes this session did not start.

WHAT IT CHECKS
--------------
Every simple command in the Bash command line --- including those inside a
shell's `-c` argument, a `$(...)` or backtick substitution (quoted or not;
heredoc bodies and `#` comments are blanked first, so a commit message or PR
body that merely mentions `ps aux` stays silent), and a quoted remote command
(`ssh host 'ps aux'`) --- for a program that prints OTHER processes' command
lines or environments:

    ps       with a UNIX `-f`/`-F`, any BSD-style option cluster (`aux`, `ax`,
             `x`), `-O`/BSD `O` (which preload the default `command` column),
             `--context`, BSD `e` (environments, even with `c` or an `-o`
             format), or an explicit format naming `args`/`command`/`cmd`/`%a`
             --- unless BSD `c` is present, which swaps argv for the name in
             every column (measured: `ps -ef c`, `ps -e -o pid,args c`)
    pgrep    with `-a` / `--list-full`
    pstree   with `-a` / `--arguments`
    top      with `-c`/`--cmdline-toggle`. `-c` REVERSES the toprc's
             remembered state rather than setting it, so with a toprc that
             saved `c` on, plain `top -b` prints argv and is not caught
             (listed under KNOWN HOLES)
    a read of `/proc/<pid>/cmdline` or `/proc/<pid>/environ` (also under
             `task/<tid>/`), unless the command only tests for the file
             (`test`, `[`, `ls`, `grep -l/-L/-c/-q`)

A lister is found past wrappers (`sudo`, `timeout 5`, `watch`, `xargs`,
`setsid`, `flock <file>`, `ssh <host>`, `busybox`) and past
`docker`/`podman`/`kubectl`/`nerdctl exec <container>`, since a remote or
container listing prints into the same transcript. The walk past a wrapper
accepts only options, their values, and the wrapper's own positional
operands (`timeout`'s duration, `ssh`'s host), and stops at any other
program, so `sudo docker ps -f name=web` is docker's filter flag, not procps.

The `ps` grammar modelled is Linux procps. macOS's BSD `ps` prints argv for
more forms than this (plain `ps -e` among them), so silence there is weaker
evidence than it is on Linux. Busybox `ps` prints argv by default, so
`busybox ps` fires unless an `-o` format names no argv column.

KNOWN HOLES, so silence is not read as coverage:

- a command assembled at run time: `eval "$cmd"`, a script file, a variable
  as the program name, or a variable inside a /proc path
  (`for p in /proc/[0-9]*; do cat "$p/cmdline"; done`);
- a heredoc fed to a shell, and a substitution inside an unquoted heredoc
  (all heredoc bodies are blanked, which trades this miss for silence on
  commit messages);
- `docker top` and `docker run --pid=host ... ps aux`;
- `top -b` under a toprc that saved the command-line toggle on;
- other tools that print argv: `htop`, `atop`, `lsof +c0`,
  `systemctl status`.

Commands over 20000 characters are not examined, so a pathological input
cannot push the scan past the hook's timeout.

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
                          _comment_free, _heredoc_free, shell_c_expansions,
                          simple_commands)
except Exception as _exc:  # broken install; fail open and say so
    print(f"flag-argv-printing-process-listing: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); not evaluating",
          file=sys.stderr)
    simple_commands = None

LISTERS = {"ps", "pgrep", "pstree", "top"}

# Wrappers that run the command after them, with how many positional
# operands each takes before that command (`timeout 5`, `flock FILE`,
# `ssh HOST`). Options and their values are skipped separately.
WRAPPER_OPERANDS = {name: 0 for name in COMMAND_WRAPPERS}
WRAPPER_OPERANDS.update({"timeout": 1, "watch": 0, "xargs": 0, "setsid": 0,
                         "flock": 1, "ssh": 1, "busybox": 0})

# Container CLIs run a command only under `exec <container>`; `docker ps`
# lists containers and must not be read as procps `ps`.
CONTAINER_CLIS = {"docker", "podman", "kubectl", "nerdctl"}

# Format keys whose column is the full argv rather than the executable name.
ARGV_KEYS = {"args", "command", "cmd", "%a"}

# `ps` options that take a value, so the value is not misread as a BSD option
# cluster (`ps -C curl` names a process, it is not BSD `curl`) and so a letter
# inside an attached value (`ps -Cxterm`) is not read as an option.
PS_UNIX_VALUE_OPTS = set("CGgNpqstUuoO")
PS_LONG_VALUE_OPTS = {"--cols", "--columns", "--rows", "--lines", "--width",
                      "--format", "--group", "--Group", "--pid", "--ppid",
                      "--quick-pid", "--sid", "--tty", "--user", "--User",
                      "--sort"}
PS_BSD_VALUE_OPTS = set("oOptUk")

RX_REDIRECT = re.compile(r"\A\d*(?:[<>]|&>)")

RX_PROC_LEAK = re.compile(
    r"/proc/[^/\s]+/(?:task/[^/\s]+/)?(?:cmdline|environ)")

# Programs that only test for a /proc file rather than print it.
PROC_TESTERS = {"test", "[", "[[", "ls", "stat", "readlink", "realpath"}
GREP_PROGS = {"grep", "egrep", "fgrep", "rg"}
GREP_QUIET_LONG = {"--files-with-matches", "--files-without-match", "--count",
                   "--quiet", "--silent"}

MAX_DEPTH = 3
MAX_COMMAND = 20000
MAX_BODIES = 64


def _resolve(argv):
    """`(index, via_busybox)` of the program ARGV actually runs, or None.

    Leading assignments and shell keywords are skipped, then wrappers. Past a
    wrapper only options, their values, and the wrapper's own positional
    operands are skipped; the first other token is the program. A token after
    an option is read as that option's value, which can hide a program behind
    a flag that takes none (`ssh -v host`): the cost is a miss, never a
    false warning about some other program's flags.
    """
    index, busybox = 0, False
    while index < len(argv) and (ENV_ASSIGNMENT.match(argv[index])
                                 or argv[index] in SHELL_KEYWORDS):
        index += 1
    while index < len(argv):
        name = os.path.basename(argv[index])
        if name in CONTAINER_CLIS:
            if "exec" not in argv[index + 1:index + 2]:
                return index, busybox
            operands, index = 1, index + 2  # the container (or pod)
        elif name in WRAPPER_OPERANDS:
            busybox = busybox or name == "busybox"
            operands, index = WRAPPER_OPERANDS[name], index + 1
        else:
            return index, busybox
        after_option = False
        while index < len(argv):
            token = argv[index]
            if token == "--":
                index += 1
                after_option = False
                continue
            if token.startswith("-") and len(token) > 1:
                # Only a bare `-n` or `--name` can take the next token as its
                # value; `-n1` and `--name=v` carry theirs.
                after_option = (len(token) == 2
                                or (token.startswith("--") and "=" not in token))
                index += 1
                continue
            if after_option:
                after_option = False
                index += 1
                continue
            if operands:
                operands -= 1
                index += 1
                continue
            break
    return None


def _format_keys(spec):
    """The column keys named in a `ps -o` format spec."""
    keys = set()
    for part in re.split(r"[,\s]+", spec):
        key = part.split("=", 1)[0].split(":", 1)[0].strip()
        if key:
            keys.add(key)
    if "%a" in spec:
        keys.add("%a")  # AIX descriptors need no separator: `-o%p%a`
    return keys


def _ps_prints_argv(args, busybox=False):
    # `replaced`: an `-o`/`o`/`--format` replaced the default columns, so only
    # the named keys count. `-O`/`O` ADD to the default columns, which include
    # `command`, so they set `full` instead.
    formats, full, replaced = [], False, False
    bsd, bsd_c, env = False, False, False
    i = 0
    while i < len(args):
        tok = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else ""
        if RX_REDIRECT.match(tok):
            break  # `ps aux > out`: `out` is a file, not an option cluster
        if tok.startswith("--"):
            name, eq, value = tok.partition("=")
            if name == "--format":
                formats.append(value if eq else nxt)
                replaced = True
            if name == "--context":
                full = True
            if name in PS_LONG_VALUE_OPTS and not eq:
                i += 1
            i += 1
            continue
        dashed = tok.startswith("-") and len(tok) > 1
        if not dashed and not re.fullmatch(r"[A-Za-z]+", tok):
            i += 1
            continue
        cluster = tok[1:] if dashed else tok
        value_opts = PS_UNIX_VALUE_OPTS if dashed else PS_BSD_VALUE_OPTS
        if dashed and "x" in cluster and re.fullmatch(r"[auxwe]+", cluster):
            # procps reads `ps -aux` as BSD `aux` (UNIX ps has no `-x`); a
            # cluster carrying a value option (`-Ux`, `-Cxterm`) is not this.
            dashed, value_opts = False, PS_BSD_VALUE_OPTS
        bsd = bsd or not dashed
        for pos, ch in enumerate(cluster):
            if dashed and ch in "fF":
                full = True
            if not dashed and ch == "e":
                env = True
            if not dashed and ch == "c":
                bsd_c = True
            if ch in value_opts:
                value = cluster[pos + 1:]
                if not value:
                    value = nxt
                    i += 1
                if ch == "o":
                    formats.append(value)
                    replaced = True
                elif ch == "O":
                    formats.append(value)
                    full = True
                break
        i += 1
    if env:
        return True  # BSD `e` prints every process's environment
    if bsd_c:
        return False  # BSD `c` swaps argv for the name in every column
    keys = set().union(*(_format_keys(spec) for spec in formats)) if formats else set()
    if keys & ARGV_KEYS:
        return True
    if replaced:
        return False
    return full or busybox or bsd


def _cluster_has(args, shorts, longs):
    for tok in args:
        if tok in longs:
            return True
        if (tok.startswith("-") and not tok.startswith("--")
                and set(tok[1:]) & set(shorts)):
            return True
    return False


def _proc_leak(argv, program):
    hits = [i for i, tok in enumerate(argv) if RX_PROC_LEAK.fullmatch(tok)]
    if not hits:
        return None
    name = os.path.basename(argv[program]) if program is not None else ""
    if name in PROC_TESTERS:
        return None
    if name in GREP_PROGS:
        args = argv[program + 1:]
        if any(tok in GREP_QUIET_LONG
               or (tok.startswith("-") and not tok.startswith("--")
                   and set(tok[1:]) & set("lLcq"))
               for tok in args):
            return None
        # Without `-e`/`-f`, the first operand is the PATTERN, not a file:
        # `rg -n /proc/1/cmdline hooks` searches for the string.
        if not any(tok in ("-e", "-f", "--regexp", "--file") for tok in args):
            operands = [program + 1 + j for j, tok in enumerate(args)
                        if not tok.startswith("-")]
            if operands:
                hits = [i for i in hits if i != operands[0]]
        if not hits:
            return None
    return f"reads `{argv[hits[0]]}`"


def _leak(argv):
    """A description of how ARGV prints other processes' argv, or None."""
    located = _resolve(argv)
    program = located[0] if located else None
    found = _proc_leak(argv, program)
    if found or located is None:
        return found
    index, busybox = located
    name = os.path.basename(argv[index])
    args = argv[index + 1:]
    shown = " ".join(argv[index:])
    if ((name == "ps" and _ps_prints_argv(args, busybox))
            or (name == "pgrep" and _cluster_has(args, "a", {"--list-full"}))
            or (name == "pstree" and _cluster_has(args, "a", {"--arguments"}))
            or (name == "top" and _cluster_has(args, "c", {"--cmdline-toggle"}))):
        return f"`{shown}` lists full command lines"
    return None


def _substitutions(text):
    """Bodies of `$(...)` and backtick substitutions outside single quotes.

    One linear pass; an unclosed `$(` takes the rest of the text as its body.
    """
    bodies, i, n, in_double = [], 0, len(text), False
    while i < n and len(bodies) < MAX_BODIES:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "'" and not in_double:
            close = text.find("'", i + 1)
            i = n if close == -1 else close + 1
            continue
        if ch == '"':
            in_double = not in_double
        elif ch == "`":
            close = text.find("`", i + 1)
            if close == -1:
                break
            bodies.append(text[i + 1:close])
            i = close + 1
            continue
        elif text.startswith("$(", i):
            depth, j = 1, i + 2
            while j < n and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            bodies.append(text[i + 2:j - 1] if not depth else text[i + 2:])
            i = j
            continue
        i += 1
    return bodies


def find_leak(command, depth=0):
    if depth > MAX_DEPTH:
        return None
    for line in shell_c_expansions(command):
        live = _comment_free(_heredoc_free(line))
        for body in _substitutions(live):
            found = find_leak(body, depth + 1)
            if found:
                return found
        argvs = simple_commands(line)
        if not argvs:
            continue
        for argv in argvs:
            found = _leak(argv)
            if found:
                return found
            # A quoted remote or container command (`ssh host 'ps aux'`,
            # `docker exec c sh -c "ps aux"`) is one token; read it as a line.
            first = argv[0] if argv else ""
            if (os.path.basename(first) in WRAPPER_OPERANDS
                    or os.path.basename(first) in CONTAINER_CLIS):
                for token in argv[1:]:
                    if " " in token:
                        found = find_leak(token, depth + 1)
                        if found:
                            return found
    return None


NOTE = (
    "{found}. Process argv is readable by any process that can see it in "
    "/proc (on a default Linux mount, every process on the host), so this "
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
    if len(command) > MAX_COMMAND:
        return 0  # bounded scan; see the docstring
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
