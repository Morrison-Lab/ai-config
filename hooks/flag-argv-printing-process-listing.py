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
shell's `-c` argument, a `$(...)`, backtick or `<(...)` process
substitution (quoted or not, and masked out of the enclosing command so
`ps -p $(pgrep x) -o args` keeps its `-o args`;
heredoc bodies and `#` comments are blanked first, so a commit message or PR
body that merely mentions `ps aux` stays silent), and a quoted remote command
(`ssh host 'ps aux'`) --- for a program that prints OTHER processes' command
lines or environments:

    ps       with a UNIX `-f`/`-F`, any BSD-style option cluster (`aux`, `ax`,
             `x`), a dashless PID operand (`ps 1234`, `ps $pid`, which
             switches procps to BSD output), `-O`/BSD `O` (which preload the default `command` column),
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
             `task/<tid>/`), unless the command only names the file as an
             operand of a tester (`test`, `[`, `[[`, `ls`, `stat`,
             `readlink`, `realpath`, `echo`, `printf`, `grep -l/-L/-c/-q`)

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

- a command assembled at run time: `eval "$cmd"`, a script file, another
  language's `os.system('ps aux')`, a variable as the program name, or a
  variable holding the /proc prefix (`for p in /proc/[0-9]*; do cat
  "$p/cmdline"; done`; `/proc/$pid/cmdline` itself is caught);
- `ps -r`, which procps answers in BSD format with a COMMAND column;
- a heredoc fed to a shell, and a substitution inside an unquoted heredoc
  (all heredoc bodies are blanked, which trades this miss for silence on
  commit messages);
- `docker top` and `docker run --pid=host ... ps aux`;
- `top -b` under a toprc that saved the command-line toggle on;
- other tools that print argv: `htop`, `atop`, `lsof +c0`,
  `systemctl status`, `w` (its WHAT column), `pidstat -l`;
- a format set in the environment: `PS_FORMAT=args ps -e` prints argv;
- the session's OWN environment (`env`, `printenv`, `export -p`,
  `/proc/self/environ`), which is out of scope: this guard is about other
  processes' data, and those dumps are a separate habit to break.

Commands over 10000 characters are not examined, so a pathological input
cannot push the scan past the hook's timeout.

It stays silent on the forms that print only a name: `pgrep -f <pattern>`
(PIDs only), `ps -p <pid>`, `ps -eo pid,etime,comm`, `ps -e`, BSD `c`
(`ps axc`), which replaces argv with the executable name, and
`/proc/self/cmdline`, which is the shell's own argv. It also stays silent
when the listing's output never reaches the transcript: its own pipeline
ends in `wc` or `grep -c`/`-q`/`-l` (through any `grep`, `sort`,
`head`-style filters), or sends stdout to
`/dev/null`. Only the listing's own top-level pipeline counts: a
`>/dev/null` on a command before a top-level `;` or `&` does not silence it.
Inside parentheses the whole group is read as one pipeline, so
`(ps -ef; true >/dev/null)` is silenced, a miss.

It deliberately over-warns where the output feeds a consumer that prints
nothing (`ps -ef | grep x | awk '{print $2}' | xargs kill`,
`[ -n "$(ps aux | grep x)" ]`) and on `ps -o args -p $$`: the remedy it
names, `pgrep`/`pkill`, is the better habit there anyway.

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

# Short flags that TAKE A VALUE, per wrapper; every other flag takes none, so
# `sudo -E ps`, `xargs -0 ps` and `watch -d ps` reach the lister.
WRAPPER_VALUE_FLAGS = {
    "sudo": set("ugpCDhrtTU"), "doas": set("uC"), "env": set("uCS"),
    "timeout": set("sk"), "nice": set("n"), "ionice": set("cnpt"),
    "stdbuf": set("ioe"), "watch": set("nq"), "xargs": set("adEeIiLlnPs"),
    "flock": set("wEn"), "ssh": set("BbcDEeFIiJLlmOoPpQRSWw"),
    "docker": set("euw"), "podman": set("euw"), "nerdctl": set("euw"),
    "kubectl": set("cn"),
}
# Long flags that take a separate value; any other `--flag` takes none.
WRAPPER_VALUE_LONG = {"--user", "--group", "--signal", "--kill-after",
                      "--namespace", "--container", "--env", "--workdir",
                      "--interval", "--chdir", "--unset"}

# Container CLIs run a command only under `exec <container>`; `docker ps`
# lists containers and must not be read as procps `ps`.
CONTAINER_CLIS = {"docker", "podman", "kubectl", "nerdctl"}

# Format keys whose column is the full argv rather than the executable name.
ARGV_KEYS = {"args", "command", "cmd", "%a"}

# `ps` options that take a value, so the value is not misread as a BSD option
# cluster (`ps -C curl` names a process, it is not BSD `curl`) and so a letter
# inside an attached value (`ps -Cxterm`) is not read as an option.
PS_UNIX_VALUE_OPTS = set("CGgpqstUuoO")
PS_LONG_VALUE_OPTS = {"--cols", "--columns", "--rows", "--lines", "--width",
                      "--format", "--group", "--Group", "--pid", "--ppid",
                      "--quick-pid", "--sid", "--tty", "--user", "--User",
                      "--sort"}
PS_BSD_VALUE_OPTS = set("oOptUk")

RX_REDIRECT = re.compile(r"\A\d*(?:[<>]|&>)")

# Stdout (or both streams) sent to /dev/null; `2>/dev/null` is not this.
RX_STDOUT_DISCARD = re.compile(r"(?:^|[\s;|&])(?:1?>|&>)\s*/dev/null\b")

# Another process's `cmdline` or `environ`. `self`, `thread-self` and `$$`
# are the shell's own; dumping the session's own environment (`env`,
# `printenv`, `/proc/self/environ`) is out of scope, as KNOWN HOLES says.
RX_PROC_LEAK = re.compile(
    r"/proc/(?!(?:self|thread-self|\$\$)/)[^/\s]+/"
    r"(?:task/[^/\s]+/)?(?:cmdline|environ)")

# Programs that only test for a /proc file rather than print it.
PROC_TESTERS = {"test", "[", "[[", "ls", "stat", "readlink", "realpath",
                "echo", "printf"}
GREP_PROGS = {"grep", "egrep", "fgrep", "rg"}
GREP_QUIET_LONG = {"--files-with-matches", "--files-without-match", "--count",
                   "--quiet", "--silent"}

SHELLS = {"sh", "bash", "zsh", "dash", "ash", "ksh"}

MAX_DEPTH = 3
MAX_COMMAND = 10000
MAX_BODIES = 64


def _resolve(argv):
    """`(index, via_busybox)` of the program ARGV actually runs, or None.

    Leading assignments and shell keywords are skipped, then wrappers. Past a
    wrapper only options, their values, and the wrapper's own positional
    operands are skipped; the first other token is the program. Which flags
    take a value is listed per wrapper (`WRAPPER_VALUE_FLAGS`); a flag that
    list gets wrong shifts the walk by one token, which costs a miss, never a
    false warning about some other program's flags.
    """
    index, busybox = 0, False
    while index < len(argv) and (ENV_ASSIGNMENT.match(argv[index])
                                 or argv[index] in SHELL_KEYWORDS):
        index += 1
    while index < len(argv):
        name = os.path.basename(argv[index])
        if name in CONTAINER_CLIS:
            # `exec` may follow global options and `compose`:
            # `kubectl -n ns exec pod -- ps`, `docker compose exec web ps`.
            j, cli_flags = index + 1, WRAPPER_VALUE_FLAGS.get(name, set())
            while j < len(argv) and (argv[j].startswith("-")
                                     or argv[j] == "compose"):
                takes = (len(argv[j]) == 2 and argv[j][1] in cli_flags
                         or argv[j] in WRAPPER_VALUE_LONG)
                j += 2 if takes else 1
            if j >= len(argv) or argv[j] != "exec":
                return index, busybox
            operands, index = 1, j + 1  # the container (or pod)
        elif name in WRAPPER_OPERANDS:
            busybox = busybox or name == "busybox"
            operands, index = WRAPPER_OPERANDS[name], index + 1
        else:
            return index, busybox
        value_flags = WRAPPER_VALUE_FLAGS.get(name, set())
        after_option = False
        while index < len(argv):
            token = argv[index]
            if token == "--":
                index += 1
                after_option = False
                continue
            if token.startswith("-") and len(token) > 1:
                # Only a value-taking flag whose value is not attached
                # (`-n 1`, `--user me`) consumes the next token: `-n1`,
                # `--user=me`, `-E` and `-0` do not.
                if token.startswith("--"):
                    after_option = token in WRAPPER_VALUE_LONG
                else:
                    cluster = token[1:]
                    taker = next((pos for pos, ch in enumerate(cluster)
                                  if ch in value_flags), None)
                    after_option = taker == len(cluster) - 1
                index += 1
                continue
            if after_option:
                # Before the assignment test: `ssh -o Key=Value host` and
                # `docker exec -e FOO=bar c` carry a value shaped like one.
                after_option = False
                index += 1
                continue
            if ENV_ASSIGNMENT.match(token):
                index += 1  # `env FOO=1 ps`, `sudo FOO=1 ps`
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
        if tok in ("--help", "--version", "-V"):
            return False  # prints usage, not processes
        if RX_REDIRECT.match(tok) or (
                tok.isdigit() and RX_REDIRECT.match(nxt)):
            # `ps aux > out`: `out` is a file, not an option cluster; and in
            # `2>/dev/null` the tokenizer splits off a `2` that is no PID.
            break
        if tok != "$$" and re.fullmatch(r"\d+(?:,\d+)*|\$.*", tok):
            # A dashless PID list (`ps 1234`, `ps $pid`) switches procps to
            # BSD output, which carries the COMMAND column (measured). `$$`
            # is the shell itself, whose own argv is exempt.
            bsd = True
            i += 1
            continue
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
        if (dashed and "x" in cluster and cluster.isalpha()
                and cluster[0] not in PS_UNIX_VALUE_OPTS - {"u"}):
            # procps reads `ps -aux` (and `-auxf`, `-aufx`) as BSD: UNIX ps
            # has no `-x`. A cluster opening with a value option (`-Ux`,
            # `-Cxterm`, `-pxx`) names a user, command or PID instead.
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
    # A tester exempts only a /proc path it receives as an OPERAND; a stdin
    # redirect (`xargs -0 -n1 echo < /proc/1/environ`) feeds the contents on.
    redirected = [i for i in hits if i and RX_REDIRECT.match(argv[i - 1])]
    if name in PROC_TESTERS and not redirected:
        return None
    if name == "git" and argv[program + 1:program + 2] == ["grep"]:
        name, program = "grep", program + 1  # `git grep` patterns too
    if name in GREP_PROGS:
        args = argv[program + 1:]
        # A pattern given with `-e`/`--regexp` is a search string, not a read.
        hits = [i for i in hits
                if argv[i - 1] not in ("-e", "--regexp")]
        if not hits:
            return None
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
    shown_args = argv[index:]
    for pos, tok in enumerate(shown_args):
        if RX_REDIRECT.match(tok) or (
                tok.isdigit() and pos + 1 < len(shown_args)
                and RX_REDIRECT.match(shown_args[pos + 1])):
            shown_args = shown_args[:pos]  # quote the command, not redirects
            break
    shown = " ".join(shown_args)
    if ((name == "ps" and _ps_prints_argv(args, busybox))
            or (name == "pgrep" and _cluster_has(args, "a", {"--list-full"}))
            or (name == "pstree" and _cluster_has(args, "a", {"--arguments"}))
            or (name == "top" and _cluster_has(args, "c", {"--cmdline-toggle"}))):
        return f"`{shown}` lists full command lines"
    return None


def _substitution_spans(text):
    """`(start, end, body)` of each top-level substitution outside single quotes.

    Covers `$(...)`, backticks, and process substitution `<(...)`/`>(...)`.
    One linear pass; an unclosed `$(` takes the rest of the text as its body.
    """
    spans, i, n, in_double = [], 0, len(text), False
    while i < n and len(spans) < MAX_BODIES:
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
            spans.append((i, close + 1, text[i + 1:close]))
            i = close + 1
            continue
        elif text[i:i + 2] in ("$(", "<(", ">("):
            depth, j = 1, i + 2
            while j < n and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            spans.append((i, j, text[i + 2:j - 1] if not depth else text[i + 2:]))
            i = j
            continue
        i += 1
    return spans


def _masked(text, spans):
    """TEXT with each substitution span replaced by one placeholder word.

    The shared tokenizer splits on a substitution's parenthesis, so
    `ps -p $(pgrep x) -o args` would lose its `-o args`; the bodies are
    scanned separately.
    """
    out, last = [], 0
    for start, end, _body in spans:
        out.append(text[last:start])
        out.append("SUBST")
        last = end
    out.append(text[last:])
    return "".join(out)


def _discarded(argv, following, line):
    """Whether the listing's output never reaches the transcript.

    LINE is the listing's own PIPELINE (see `_pipelines`), so FOLLOWING holds
    only the commands its output is piped into. True for stdout sent to
    /dev/null, or a pipe that ends in a counter (`wc`, `grep -c/-q/-l`) or a
    through only filtering commands. An awk projection is not exempt:
    `awk '{print $12}'` prints one argv word per process.
    """
    # Read on the raw line: the tokenizer splits `2>/dev/null` into `2`, `>`,
    # which loses whether the redirect is stdout or stderr.
    if RX_STDOUT_DISCARD.search(line):
        return True
    if "|" not in line:
        return False
    for nxt in following:
        name = os.path.basename(nxt[0]) if nxt else ""
        if name == "wc":
            return True
        if name in GREP_PROGS:
            if any(tok in GREP_QUIET_LONG or (
                    tok.startswith("-") and not tok.startswith("--")
                    and set(tok[1:]) & set("cql"))
                   for tok in nxt[1:]):
                return True
            continue
        if name in ("sort", "uniq", "head", "tail", "cut", "tr"):
            continue
        return False
    return False


def _pipelines(text):
    """TEXT split into top-level pipelines, on `;`, `&`, `&&`, `||`, newline.

    Quotes and parentheses are respected, and the `&` of a redirection
    (`2>&1`, `&>`) is not a separator.
    """
    parts, start, depth, i, n, quote = [], 0, 0, 0, len(text), None
    while i < n:
        ch = text[i]
        if quote:
            if ch == "\\" and quote == '"':
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch == "\\":
            i += 2
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and (ch in ";\n" or text.startswith("||", i)
                             or (ch == "&" and text[i - 1:i] != ">"
                                 and text[i + 1:i + 2] != ">")):
            parts.append(text[start:i])
            i += 2 if text[i:i + 2] in ("&&", "||") else 1
            start = i
            continue
        i += 1
    parts.append(text[start:])
    return [part for part in parts if part.strip()]


def find_leak(command, depth=0):
    if depth > MAX_DEPTH:
        return None
    for line in shell_c_expansions(command):
        live = _comment_free(_heredoc_free(line))
        spans = _substitution_spans(live)
        for _start, _end, body in spans:
            found = find_leak(body, depth + 1)
            if found:
                return found
        for pipeline in _pipelines(_masked(live, spans)):
            argvs = simple_commands(pipeline) or []
            for k, argv in enumerate(argvs):
                found = _leak(argv)
                if found and not _discarded(argv, argvs[k + 1:], pipeline):
                    return found
        argvs = simple_commands(line)
        if not argvs:
            continue
        for argv in argvs:
            # A quoted remote command (`ssh host 'ps aux'`) is one token at
            # the program position, and a container's shell (`docker exec c
            # sh -c "ps aux"`) carries one after `-c`. Only those are read as
            # a line; a commit message behind `timeout` is not a command.
            first = argv[0] if argv else ""
            if not (os.path.basename(first) in WRAPPER_OPERANDS
                    or os.path.basename(first) in CONTAINER_CLIS):
                continue
            located = _resolve(argv)
            if located is None:
                continue
            index = located[0]
            program = argv[index]
            candidates = [program] if " " in program else []
            if os.path.basename(program) in SHELLS:
                candidates += [tok for prev, tok in zip(argv[index:], argv[index + 1:])
                               if prev == "-c" and " " in tok]
            for token in candidates:
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
