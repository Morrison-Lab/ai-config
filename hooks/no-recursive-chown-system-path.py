#!/usr/bin/env python3
"""PreToolUse guard: refuse a recursive chown, chmod or chgrp of a system tree.

Two reported incidents (shared/workflow/destructive-actions-catalog.md, #5317):
anthropics/claude-code#168, where `sudo chown -R $USER:$(id -gn) /usr && sudo
chmod -R u+w /usr` broke `sudo` and needed a rescue instance, and
anthropics/claude-code#39283, where an agent's `chown -R root:root /usr/` and
`/etc/` "repair" cleared the setuid bit on `sudo`, `su` and `passwd`.
No ai-config hook covered either, and CC Safety Net (the open-source guard
under evaluation in #5317) checks `chown` only for secret paths.

DENIES `chown`, `chmod` or `chgrp` run with `-R`/`--recursive` (directly, under
`sudo` or another wrapper, inside `sh -c`, or inside a command substitution)
when a target is:

  * `/`, or a standard top-level directory (`TOP_LEVEL`: `/usr`, `/etc`,
    `/home`, `/opt`, ...). A project root such as a container's `/app` is
    not one of them;
  * anything inside a system tree (`SYSTEM_TREES`), with two carve-outs for
    directories that hold one application's own files: below `/usr/local`,
    only `/usr/local` and its `USR_LOCAL_CORE` children are refused
    (`/usr/local/lib/node_modules` and `/usr/local/Cellar` pass), and below
    `/var/lib`, `/var/log` and `/var/spool` only the tree itself and the
    package and auth state in `VAR_CORE` are (`/var/lib/postgresql` passes);
  * the home directory, or a directory that contains it.

A target is read with `~`, `~user`, `$HOME`, and `~+`, `$(pwd)` and `$PWD`
(the current directory) expanded, relative paths
resolved against the hook's `cwd` and any `cd` earlier in the same shell (a
`cd` inside `( ... )` moves only that subshell, and one inside an `if`, a
loop or a `case`, outside the condition that opens it, may not run, so the
rest of the command is judged once with the `cd` and once without, `$PWD`
and names assigned from it included),
and a basename made only of glob characters read as its directory (`/usr/*`
touches `/usr`). Any other
`$VAR` keeps its value in this environment, which the Bash call inherits; one
unset here is taken as empty, because a variable set by an earlier Bash call
is empty in this one (anthropics/claude-code#75859): `chmod -R 755 "$d/"` is
`/`. A path that
exists only because something was taken as empty is refused for the root, a
system tree or home, but not for a top-level directory: `$OUT/dist` with OUT
unset is `/dist`. Only a default (`${D:-/x}`, `${D=/x}`, which also assigns
D) or an error check (`${D:?}`, which stops bash first) is read; an operand
built with any other operator (`${D:+x}`, `${D%/}`, `${!D}`, `${#D}`,
`${D:0:3}`), there or in an assignment it uses, is refused wherever it
points, since each can rebuild a protected path (`/e${HOME:+tc}` is `/etc`).
So is one that uses a parameter this cannot know: a positional parameter
(`$1`, `$@`, which `set --` or a function can set), `$0` (which
`sh -c '...' /etc` sets), `$_`, `$OLDPWD` (and `~-`), or a name set by `read`,
`mapfile`, `readarray`, `getopts` or `printf -v`. `$!` is read like an
unset variable, and `$$`, `$#`, `$?` and `$-` as some value that is not
empty. A command substitution (`$(...)`, a backtick pair, `<(...)` or `>(...)`)
outside single quotes, heredoc bodies and comments is lifted out before the
command is split, scanned as a command of its own, and taken as empty,
except a bare `pwd`, read as `$PWD`. A `sh -c` text or a substitution is
read where it appears, in the directory and with the names of each way the
command may run up to there (a `sh -c` text also with the `NAME=value`
words before its shell, `sudo D=/x sh -c`, and, unless the text is written
in single quotes, once without them, since bash expands a double-quoted text
with the outer names; `~` reads HOME the same way), to MAX_NESTED
levels, and deeper with no directory, to MAX_DEPTH. A `cd` up the tree
repeated by a loop (`cd ..`) is judged in every directory above. An
unquoted `cd $D` with D empty or unset goes home, and is judged both there
and where it is. `pushd` moves as `cd` does, and `popd` returns to the
directory the last `pushd` left. `cd "$OUT/tmp"` (or `pushd`) with OUT
unset goes to `/tmp`: the rest is
judged there, with `.`, a relative target and `$PWD` read as values taken as
empty, and once more with the directory unknown, for when OUT is set (a
value taken as empty counts only where it reaches the root, a system tree
or home).

A deny, not a warning: the remedy (fix the one path that raised the error, as
your own user) is always available, and the damage is unrecoverable without a
console. Escape hatch for a case this did not foresee: a real leading
`ALLOW_RECURSIVE_SYSTEM_CHOWN=1` assignment on the same command, with the
reason stated in the reply.

The guard is aimed at the mistakes in the incidents above (a wrong path, an
unset variable, a "repair" of a system tree), not at a command built to get
past it: no static reading of bash is complete, and an agent set on running
a command can always run it some other way. So it reads the shell forms an
honest command uses, refuses the operator and parameter forms it does not
model, and names the rest here.

Limits, deliberately unclosed: `find ... -exec chown`, `xargs chown`, a
function body (judged where it is defined, not where it is called), an
array assignment (`D=(/etc)`, read as empty), `systemd-run`, `chroot`,
`$'...'` quoting, a program named by a substitution (`"$(which chown)"`),
a command substitution's value (read as empty, both ways: it denies
`"$(npm config get prefix)/lib/node_modules"`, judged at
`/lib/node_modules`, where writing the path itself or the escape hatch is
the remedy, and it passes `"$(brew --prefix)/share"`), `flock -c TEXT`, a
named `coproc NAME { ...; }`, more than MAX_SCOPE `pushd`s in one command
(`popd` then goes somewhere unknown), a `popd` inside a command
substitution (read with an empty stack; bash's inherits the outer one), a
`cd` and a `cd ..` in one conditional body (each read as maybe run on its
own, which can refuse the directory above: `if [ -d sub ]; then cd sub;
make; cd ..; fi; chmod -R u+w .` is judged in the parent too), a quoted
`"$D"` holding spaces (also judged word by word, so `D="build /"` is refused
at `/`), a top-level directory written in a value beside an unset name
(`DIRS="$X /opt"` splits to a `/opt` read as taken as empty, which a system
tree or home is not), a `-R` held in a variable (`chown $FLAGS root /usr`
is not seen as recursive), a
`for` or `select` loop variable, `eval`, `su -c`, a heredoc piped to `sh`, an
interpreter's own `-c` (`python -c "os.system(...)"`), a substitution in an
unquoted heredoc body (`<<EOF`, which bash does run), a glob in a directory
component (`/*/lib`), a partial glob or brace expansion that names a
protected path (`/et*`, `/{etc,usr}`), a wrapper that changes directory
(`env -C /etc`, `sudo -D /etc`), more than MAX_WORLDS ways a command may
run (the directory is then unknown), the rest of a command once judging it
in every way it may run would pass MAX_WORK words of commands that may
change directory, assign or run chown, chmod or chgrp (those ways are then
merged into one, with the directory unknown), a directory deeper than
MAX_SCOPE subshells or longer than PATH_MAX (read as MAX_SCOPE deep, or
unknown), PowerShell
`icacls`/`Set-Acl`, Windows drive paths (`C:/Windows`), a `#` right after a
`$(...)` holding a `case` pattern (read as a comment), nested texts past
MAX_DEPTH, a relative target, `$PWD`, or a name assigned from `$PWD`, after
a `cd` this cannot resolve (`cd -` or `cd "$(git rev-parse
--show-toplevel)"`, where `$PWD` is taken as empty; an absolute `cd`
after it is followed), a `cd` into a
subdirectory repeated by a loop (read as run once), a command before a `cd`
in the same loop body (judged only where the loop starts), a `cd` that fails
or follows `&&` or `||` (read as run), a quoted `cd "$D"` where an unquoted
`cd $D` appears elsewhere in the same text (both read as going home), an
assignment that may not run (`false && D=./x` or `if false; then :
"${D:=./x}"; fi`, each read as run), a `${D:=x}` assignment inside `sh -c`
or a substitution, an assignment in a pipeline element (`echo x | :
"${D:=./x}"`, read as made in the shell that follows), a `${D:=x}` read
earlier in the same command than it assigns, and a bind-mounted path (the
#39283 `/volumes/mail/` case) all pass. Fails open on parse trouble and when
scripts/lib/shellcmd.py cannot be imported.
"""
from __future__ import annotations

import json
from collections import ChainMap
import os
import re
import shlex
import sys

try:
    _LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (COMMAND_WRAPPERS, SHELL_KEYWORDS, _comment_free,
                          _heredoc_free, resolve_cd_target, shell_c_expansions,
                          simple_commands_with_scope)
except Exception as _exc:  # broken install: say so, then allow
    print(f"no-recursive-chown-system-path: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    simple_commands_with_scope = None

OVERRIDE = "ALLOW_RECURSIVE_SYSTEM_CHOWN=1"
PROGRAMS = {"chown", "chmod", "chgrp"}
# A text that never names one of PROGRAMS cannot run one (the program is read
# only as a literal word, see `_program`), so it is not read further.
PROGRAM_TEXT = re.compile(r"ch(?:own|mod|grp)")
WRAPPERS = (set(COMMAND_WRAPPERS) | {"setsid", "busybox", "pkexec", "run0", "coproc", "flock"}
            if simple_commands_with_scope else set())
# Wrappers that take positional words before the program (`timeout 60 chmod`).
WRAPPER_POSITIONALS = {"timeout": 1, "flock": 1}
# Each wrapper's short options that take the next word as their value; any
# other option is a flag, so `sudo -E echo chown` runs echo, not chown.
# Sources: the getopt strings in sudo's src/parse_args.c, OpenBSD's doas.c,
# and the env.c of GNU coreutils and FreeBSD.
WRAPPER_VALUE_OPTIONS = {"sudo": set("acugpCUrtTDR"), "doas": set("auC"),
                         "env": set("auCSPLU"),
                         "timeout": set("sk"), "nice": {"n"}, "ionice": set("cnp"),
                         "stdbuf": set("ioe"), "pkexec": {"u"}, "time": {"f", "o"},
                         "exec": {"a"}, "run0": set("uDg"), "flock": set("wE")}
# Each wrapper's long options, as (those taking the next word, flags).
# getopt_long takes an exact name first, then a unique prefix (`--us` is
# `--user`), so a flag such as sudo's `--login`, a prefix of `--login-class`,
# has to be listed for its exact match to win. An option with an optional
# value (`--preserve-env[=list]`) takes it only attached, so it is a flag here.
WRAPPER_LONG = {
    "sudo": ({"--auth-type", "--chdir", "--chroot", "--close-from", "--command-timeout",
              "--group", "--host", "--login-class", "--other-user", "--prompt", "--role",
              "--type", "--user"},
             {"--askpass", "--background", "--bell", "--edit", "--help", "--list",
              "--login", "--no-update", "--non-interactive", "--preserve-env",
              "--preserve-groups",
              "--remove-timestamp", "--reset-timestamp", "--set-home", "--shell",
              "--stdin", "--validate", "--version"}),
    # `--env0-from` and `--quoting-style` take a value (required_argument in
    # coreutils master src/env.c, checked 2026-11-11).
    "env": ({"--argv0", "--chdir", "--env0-from", "--quoting-style", "--split-string",
             "--unset"},
            {"--block-signal", "--debug", "--default-signal", "--help",
             "--ignore-environment", "--ignore-signal", "--list-signal-handling",
             "--null", "--version"}),
    "timeout": ({"--kill-after", "--signal"},
                {"--foreground", "--help", "--preserve-status", "--verbose", "--version"}),
    "nice": ({"--adjustment"}, {"--help", "--version"}),
    "ionice": ({"--class", "--classdata", "--pgid", "--pid", "--uid"},
               {"--help", "--ignore", "--version"}),
    "stdbuf": ({"--error", "--input", "--output"}, {"--help", "--version"}),
    "pkexec": ({"--user"}, {"--disable-internal-agent", "--help", "--keep-cwd", "--version"}),
    "time": ({"--format", "--output"},
             {"--append", "--help", "--portability", "--quiet", "--verbose", "--version"}),
    # Sources: flock(1) of util-linux, run0(1) of systemd.
    "flock": ({"--wait", "--timeout", "--conflict-exit-code", "--command"},
              {"--shared", "--exclusive", "--unlock", "--nonblock", "--nb", "--no-fork",
               "--close", "--verbose", "--help", "--version"}),
    "run0": ({"--user", "--group", "--nice", "--chdir", "--setenv", "--unit", "--property",
              "--description", "--slice", "--background", "--machine",
              "--shell-prompt-prefix", "--lightweight", "--area"},
             {"--slice-inherit", "--no-ask-password", "--pty", "--pipe", "--help",
              "--version"}),
}
# Options with an optional value (sudo's `h::`). Attached (`-hhost`), the rest
# of the word is the value. Alone as `-h`, sudo takes the next word as the
# host when it is not an option or an assignment (src/parse_args.c). Inside a
# bundle (`-Eh`), it is help.
WRAPPER_OPTIONAL_VALUE = {"sudo": {"h"}}
# How deep `${A:-${B:-...}}` defaults are expanded before giving up.
MAX_NESTING = 32
# What `_expand` returns for an operand it will not read: a default nested past
# MAX_NESTING, or an operator other than a default (`${A:+tc}`, `${A:0:0}`,
# `${A%/}`), any of which can rebuild a protected path (`/e${HOME:+tc}` is
# `/etc`). The operand is refused, with its own reason.
UNREAD = ("/", False)
UNREAD_WHY = ("whose value this guard does not read, here or in an earlier assignment: "
              "a `${...}` operator other than a `-`/`=` default or a `?` check, defaults "
              f"nested deeper than {MAX_NESTING}, a positional parameter, `$_`, `$OLDPWD`, "
              "or a name set by `read`, `getopts` or `printf -v`; write the path out")
# Words that open and close a compound command, for `_scan`'s BLOCKS.
BLOCK_OPEN = {"if", "while", "until", "for", "select", "case"}
BLOCK_CLOSE = {"fi", "done", "esac"}
# Keywords whose own condition always runs (`if cd x; then`).
CONDITION_OPEN = {"if", "while", "until"}
LOOPS = {"while", "until", "for", "select"}
DECLARE_BUILTINS = ("export", "local", "declare", "readonly", "typeset")
# chmod's own short options (GNU and BSD); any other `-w` or `-x` is a mode.
CHMOD_OPTIONS = set("cfvRHLPh")
TOP_LEVEL = {"bin", "boot", "dev", "etc", "home", "lib", "lib32", "lib64", "libx32",
             "media", "mnt", "opt", "proc", "root", "run", "sbin", "srv", "sys",
             "tmp", "usr", "var", "Applications", "Library", "System", "Users",
             "Volumes", "cores", "private"}
SYSTEM_TREES = ("/usr", "/etc", "/bin", "/sbin", "/lib", "/lib32", "/lib64",
                "/libx32", "/boot", "/var/lib", "/var/log", "/var/spool",
                "/System", "/Library", "/var/db")
USR_LOCAL_CORE = {"bin", "sbin", "etc", "lib", "libexec", "include", "share"}
APP_TREES = ("/var/lib", "/var/log", "/var/spool")
VAR_CORE = {"dpkg", "apt", "rpm", "dnf", "yum", "pacman", "systemd", "sudo",
            "polkit-1", "PackageKit", "ucf"}
ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SUB = "__AICFG_CMDSUB__"  # a lifted command substitution (see `_lift`)
# The start of a variable: `${NAME` (closed by its matching brace, found by
# `_brace_pairs`), `$NAME`, or a lifted substitution.
# Positional and special parameters (`$1`, `${1:-/etc}`, `$@`, `$$`) count too.
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*|[0-9]+|[@*#?$!-])"
                      r"|\$([A-Za-z_][A-Za-z0-9_]*|[0-9]|[@*#?$!-])|" + SUB)
# A positional parameter can hold anything: `set -- /etc`, a function's
# arguments and `sh -c '...' /etc` (which sets `$0`) all set one. So can `$_`
# (the last word of the previous command) and `$OLDPWD`. An operand that uses
# any of these is refused, like an unread operator.
POSITIONAL = re.compile(r"[0-9]+|[@*_]|OLDPWD")
# These special parameters are never empty in bash; a stand-in that is not
# empty keeps `$HOME/$$` from reading as the home directory. `$!` is empty
# until a background job runs, so it is read like an unset variable.
SPECIAL = {"$": "1", "#": "0", "?": "0", "-": "hB"}
# Builtins that set a variable from input this guard cannot read. A name they
# set is refused when an operand uses it.
READ_BUILTINS = ("read", "mapfile", "readarray", "getopts")
NAME_SETTERS = READ_BUILTINS + DECLARE_BUILTINS + ("printf",)
# A lifted `$(pwd)`, read as `${PWD}` and shown as written.
PWD_SUB = "__AICFG_PWDSUB__"
# Kept with a scope's names under a key no `$NAME` can reach: whether its
# directory is weak (see `_here_weak`).
WEAK_PWD = "weak PWD"
# Where `pushd` left the shell, innermost last, as `(directory, weak)`; under
# a key no `$NAME` can reach. `None` once this cannot follow it.
DIR_STACK = "dir stack"
# How many ways a command may run (see `_scan`) are judged one by one.
MAX_WORLDS = 16
# How deep `sh -c` texts and substitutions inside one another are read in
# each directory; deeper ones are read with no directory, to MAX_DEPTH.
MAX_NESTED = 3
MAX_DEPTH = 32
# Past this many words read, the rest of the command is read in one way it
# may run, with the directory unknown.
MAX_WORK = 20000
# Subshells deeper than this are read as this deep, and a directory longer
# than PATH_MAX as unknown, so neither makes each command cost more.
MAX_SCOPE = 64
PATH_MAX = 4096
ALL_GLOB = re.compile(r"\A[*?.]*[*?][*?.]*\Z")
CD_OPTION = re.compile(r"-[LPe@]+")
# A `cd` operand written unquoted, after any options: `cd $D`, `(cd -P $D)`,
# `cd $D>/dev/null`. An unquoted empty one sends bash home.
BARE_CD = re.compile(r"(?:^|[\s;&|(){}])cd(?:[ \t]+-[LPe@]+)*(?:[ \t]+--)?[ \t]+"
                     r"([^\s;&|()<>'\"\\]+)(?=[\s;&|()<>]|$)")

DENY = (
    "Refused: `{segment}` runs `{program} -R` on `{target}`, {where}. "
    "A recursive ownership or mode change there broke `sudo` "
    "in anthropics/claude-code#168 and #39283, and undoing it needs a console. "
    "Fix only the path that raised the error, as your own user, or ask the "
    "user to run it. If this case is genuinely safe, put `{override}` before "
    "the command and say why (shared/workflow/destructive-actions-catalog.md)."
)


def _close(text, start):
    """Index of the `)` closing a `$(` whose body starts at START, or `None`."""
    depth, single, double, j = 1, False, False, start
    while j < len(text):
        ch = text[j]
        if ch == "\\" and not single:
            j += 2
            continue
        if ch == "'" and not double:
            single = not single
        elif ch == '"' and not single:
            double = not double
        elif not single and not double and ch in "()":
            depth += 1 if ch == "(" else -1
            if not depth:
                return j
        j += 1
    return None


def _lift(text):
    """`(text with each running $(...), `...`, <(...) and >(...) replaced by SUB,
    [inner texts])`.

    `shlex` splits an unquoted `$(id -gn)` into words of its own, so `chown -R
    $USER:$(id -gn) /usr` would otherwise lose its program. A substitution
    inside single quotes does not run and stays as text.
    """
    out, inner, single, double, i = [], [], False, False, 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and not single:
            out.append(text[i:i + 2])
            i += 2
            continue
        if ch == "'" and not double:
            single = not single
        elif ch == '"' and not single:
            double = not double
        elif not single and (text.startswith("$(", i) and not text.startswith("$((", i)
                             or not double and text.startswith(("<(", ">("), i)):
            j = _close(text, i + 2)
            if j is None:  # unclosed: bash refuses the text; nothing later closes
                out.append(text[i:])
                break
            out.append(_lifted(text[i + 2:j], inner))
            i = j + 1
            continue
        elif not single and ch == "`":
            j = text.find("`", i + 1)
            if j == -1:
                out.append(text[i:])
                break
            out.append(_lifted(text[i + 1:j], inner))
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), inner


def _lifted(body, inner):
    """What a substitution of BODY stands for: PWD_SUB for `pwd`, else SUB.

    Any other body goes in INNER, to be checked as a command of its own.
    """
    words = body.split()
    if words[:1] == ["pwd"] and all(w in ("-L", "-P", "-LP", "-PL") for w in words[1:]):
        return PWD_SUB
    inner.append(body)
    return SUB


def _takes_next_word(wrapper, tok, following):
    """Whether a wrapper's option `tok` takes the next word, FOLLOWING, as its value.

    Short options may be bundled: in `sudo -Eu root`, `-u` is the last
    letter, so `root` is its value; in `sudo -uroot`, the value is attached.
    getopt_long accepts an unambiguous prefix of a long option (`--us`).
    """
    if tok.startswith("--"):
        if "=" in tok:
            return False
        if wrapper not in WRAPPER_LONG:
            # command, exec, builtin, nohup, doas and setsid take no long
            # option with a value, so the next word is the program.
            return False
        takes, flags = WRAPPER_LONG[wrapper]
        if tok in takes or tok in flags:
            return tok in takes
        matches = [opt for opt in takes | flags if opt.startswith(tok)]
        return len(matches) == 1 and matches[0] in takes  # ambiguous: a usage error
    values = WRAPPER_VALUE_OPTIONS.get(wrapper, ())
    optional = WRAPPER_OPTIONAL_VALUE.get(wrapper, ())
    if len(tok) == 2 and tok[1] in optional:
        return (following is not None and not following.startswith("-")
                and not ASSIGNMENT.match(following))
    for j, letter in enumerate(tok[1:], 1):
        if letter in optional:
            return False  # help in a bundle, or the rest of the word is its value
        if letter in values:
            return j == len(tok) - 1
    return False


def _program(argv):
    """`(argv from the program on, override present)`, peeling wrappers.

    After a wrapper, an option may be followed by its value (`sudo -u me`);
    the first other word is the program it runs, so `sudo docker run alpine
    chown` runs docker, not chown.
    """
    override, wrapper, after_option, positionals = False, None, False, 0
    for i, tok in enumerate(argv):
        name = os.path.basename(tok)
        if after_option:
            after_option = False  # the value of the option before it
        elif name in PROGRAMS:
            return argv[i:], override
        elif ASSIGNMENT.match(tok):
            override = override or tok == OVERRIDE
        elif name in WRAPPERS:
            wrapper, positionals = name, WRAPPER_POSITIONALS.get(name, 0)
        elif tok in SHELL_KEYWORDS:
            continue
        elif wrapper and tok.startswith("-"):
            following = argv[i + 1] if i + 1 < len(argv) else None
            after_option = _takes_next_word(wrapper, tok, following)
        elif wrapper and positionals:
            positionals -= 1
        else:
            return [], override  # some other program runs here
    return [], override


def _targets(program, head):
    """The file operands of a recursive invocation, or `[]` if not recursive."""
    recursive, reference, operands, end, skip = False, False, [], False, False
    for tok in head[1:]:
        if skip:
            skip = False
        elif end or tok == "-" or not tok.startswith("-"):
            operands.append(tok)
        elif tok == "--":
            end = True
        elif _long(tok, "--recursive", 5):
            recursive = True
        elif _long(tok.split("=", 1)[0], "--reference", 5):
            reference, skip = True, "=" not in tok
        elif _long(tok, "--from", 3):
            skip = True  # `--from USER:GROUP` names owners, not files
        elif tok.startswith("--"):
            continue
        else:
            # `-R` may share a word with other flags, and for chmod with a
            # mode (`-Rw`), which is then also the mode operand.
            recursive = recursive or "R" in tok[1:]
            if program == "chmod" and not set(tok[1:]) <= CHMOD_OPTIONS:
                operands.append(tok)
    if not recursive:
        return []
    return operands if reference else operands[1:]


def _long(tok, name, shortest):
    """Whether TOK is NAME or a prefix getopt_long accepts for it.

    SHORTEST is the shortest prefix no other chown, chmod or chgrp long option
    shares (`--rec` for `--recursive`, `--ref` for `--reference`).
    """
    return len(tok) >= shortest and name.startswith(tok)


def _expand(text, home, assigned, here, depth=0, effects=None):
    """`(TEXT expanded, weak)`, or `None` when a computed value makes it undecidable.

    A default nested deeper than MAX_NESTING, or any operator but a default
    (`-`, `=`, with or without `:`) or an error check (`?`), makes the whole
    text UNREAD, which is refused. So adversarial input can neither exhaust
    the stack and crash the hook open nor rebuild a protected path out of
    pieces (`/e${A:-...tc}`, `/e${HOME:+tc}`). That refuses such an operand
    around a harmless path too (`"${DIR%/}/build"`), which the escape hatch
    or a literal path settles.

    A variable set in this environment keeps its value, since the Bash call
    inherits it too; one that is unset here is taken as empty, and the result
    is then `weak`. A `${VAR:-default}` default is expanded the same way, and
    is not a guess. ASSIGNED maps a name set earlier in the same command to
    its `(value, weak)`, or to `None` when that value was computed, as in
    `d=$(mktemp -d)`.

    With a colon, a default or a check fires when the value is empty; without
    one, only when the name is unset (`D=; ${D-/x}` is empty). A `=` default
    also assigns, and the assignment goes in EFFECTS when it is given.
    """
    text = text.replace(PWD_SUB, "${PWD}")
    text = re.sub(r"\A~([+-])(?=/|\Z)",
                  lambda m: "${PWD}" if m.group(1) == "+" else "${OLDPWD}", text)
    text = re.sub(r"\A~([A-Za-z0-9_.-]*)(?=/|\Z)",
                  lambda m: os.path.expanduser("~" + m.group(1)) if m.group(1) else "${HOME}",
                  text)
    guessed, undecidable, capped = [], [], []

    def value(name, rest):
        if name in ("!", "#") and rest:  # `${!P}`, `${!?}`, `${#P}`
            capped.append(name)
            return ""
        if name is None:  # a lifted substitution
            guessed.append(True)
            return ""
        default = re.match(r":?[-=]", rest)
        check = re.match(r":?\?", rest)
        if rest and not default and not check:
            # An operator this guard does not read: its result does not depend
            # on whether the value is known (`${d:+tc}` with d computed).
            capped.append(name)
            return ""
        if POSITIONAL.fullmatch(name):
            capped.append(name)
            return ""
        missing, is_set = False, True
        if name in SPECIAL:
            val = SPECIAL[name]
        elif name in assigned:
            if assigned[name] is None:
                undecidable.append(name)
                return ""
            if assigned[name] is UNREAD:
                capped.append(name)
                return ""
            val, weak = assigned[name]
            guessed.append(weak)
        elif name == "HOME":
            val = home
        elif name == "PWD":
            # After a `cd` this cannot resolve, `$PWD` is taken as empty, like
            # an unset variable (see Limits); after `cd "$UNSET/x"` it is weak.
            val, missing = here or "", here is None or _here_weak(assigned)
        else:
            val = os.environ.get(name, "")
            missing, is_set = not val, name in os.environ
        fires = not val if rest.startswith(":") else not is_set
        if check and fires:  # bash stops with an error before the command runs
            undecidable.append(name)
            return ""
        if default and fires:
            fallback = (UNREAD if depth >= MAX_NESTING
                        else _expand(rest[default.end():], home, assigned, here, depth + 1,
                                     effects))
            if effects is not None and "=" in default.group():
                effects[name] = fallback
            if fallback is UNREAD:
                capped.append(name)
                return ""
            if fallback is None:
                undecidable.append(name)
                return ""
            (val, weak), missing = fallback, False
            guessed.append(weak)
        guessed.append(missing)
        return val

    pieces, pos, pairs = [], 0, _brace_pairs(text)
    for match in VARIABLE.finditer(text):
        if match.start() < pos:
            continue  # inside a braced default already expanded
        pieces.append(text[pos:match.start()])
        pos = match.end()
        if match.group(1):
            close = pairs.get(match.start() + 1)
            if close is None:  # no closing brace: leave the text as written
                pieces.append(match.group(0))
                continue
            pieces.append(value(match.group(1), text[match.end():close]))
            pos = close + 1
        else:
            pieces.append(value(match.group(2), ""))
    pieces.append(text[pos:])
    expanded = "".join(pieces)
    if capped:
        return UNREAD
    return None if undecidable else (expanded, any(guessed))


def _brace_pairs(text):
    """Map the index of each `${`'s brace to the index of its closing `}`.

    Bash nests only on `${`, so a bare `{` in a default is text:
    `${A:-{x}/etc}` is `{x/etc}`. One pass, so a long command stays linear.
    """
    pairs, stack, i = {}, [], 0
    while i < len(text):
        if text.startswith("${", i):
            stack.append(i + 1)
            i += 2
            continue
        if text[i] == "}" and stack:
            pairs[stack.pop()] = i
        i += 1
    return pairs


def _assignments(argv, store, visible, home, here):
    """Record `NAME=value` from a simple command that only assigns.

    Values go in STORE as `(value, weak)`, expanded against the names VISIBLE
    so far; a command substitution makes one `None`.
    """
    # `then D=/etc`, `{ D=/etc; }`, `do D=/usr`: a keyword ends the command
    # before, so the rest still only assigns.
    while argv and argv[0] in SHELL_KEYWORDS:
        argv = argv[1:]
    lead = 0
    while lead < len(argv) and (ASSIGNMENT.match(argv[lead])
                                or argv[lead] in ("command", "builtin", "time", "-p")):
        lead += 1  # `IFS= read -r D`, `command read -r D`, `time read -r D`
    rest = argv[lead + 1:]
    if lead < len(argv) and argv[lead] in READ_BUILTINS:
        # Every bare name may be one it sets (options' values included), and
        # with none, read sets REPLY and mapfile sets MAPFILE; getopts sets
        # only the name after its option string, and OPTARG.
        names = rest[1:2] if argv[lead] == "getopts" else rest
        for word in [*names, "REPLY", "MAPFILE", "OPTARG"]:
            if NAME.fullmatch(word):
                store[word] = visible[word] = UNREAD
        return False
    if lead < len(argv) and argv[lead] == "printf":
        i = 0
        while i < len(rest) and rest[i] != "--" and rest[i].startswith("-"):
            name = rest[i][2:] if rest[i].startswith("-v") else None
            if rest[i] == "-v":
                name, i = (rest[i + 1] if i + 1 < len(rest) else None), i + 1
            if name:
                store[name] = visible[name] = UNREAD
            i += 1
        return False
    words = argv
    if argv and argv[0] in DECLARE_BUILTINS:
        # Flags, and bare names (`export d=/etc PATH`), assign nothing new.
        words = [w for w in argv[1:]
                 if not w.startswith(("-", "+")) and not NAME.fullmatch(w)]
    if not words or not all(ASSIGNMENT.match(w) for w in words):
        return False
    for word in words:
        name, _, val = word.partition("=")
        computed = "`" in val or SUB in val
        store[name] = None if computed else _expand(val, home, visible, here)
        visible[name] = store[name]
    return True


def _why(path, home, weak):
    """Why PATH is protected, or `None`.

    A WEAK path counts only as the root, a system tree or the home directory:
    `$OUT/dist` with OUT unset is `/dist`, which is no reason to refuse.
    """
    if path == "/":
        return "the filesystem root"
    # On macOS `/etc`, `/tmp` and `/var` are links into `/private`.
    path = re.sub(r"\A/private(?=/(?:etc|tmp|var)(?:/|\Z))", "", path)
    parts = path.split("/")
    if path.startswith("/usr/local/") and (len(parts) > 4 or parts[3] not in USR_LOCAL_CORE):
        return None
    for tree in APP_TREES:
        depth = tree.count("/") + 1
        if path.startswith(tree + "/") and parts[depth] not in VAR_CORE:
            return None
    for tree in SYSTEM_TREES:
        if path == tree or path.startswith(tree + "/"):
            return f"inside the system tree `{tree}`"
    if home and (path == home or home.startswith(path + "/")):
        return "the home directory or a directory that contains it"
    if len(parts) == 2 and parts[1] in TOP_LEVEL and not weak:
        return "a top-level directory"
    return None


def _split(piece):
    """`(scoped argvs, inner substitutions)`; `(None, [])` on a parse error."""
    # Drop the `<<` each blanked body leaves behind: the split blanks heredocs
    # again, and would read the next word (`2>&1`) as a new delimiter whose
    # body runs to the end, hiding every later command.
    cleaned = _comment_free(_heredoc_free(piece)).replace(" << ", " ")
    lifted, inner = _lift(cleaned)
    cmds = simple_commands_with_scope(lifted)
    if cmds is None:  # lifting broke the parse: judge the text as written
        return simple_commands_with_scope(cleaned), []
    return cmds, inner


def _defaults(argv, home, store, visible, here):
    """Record in STORE and VISIBLE what each `${D:=x}` in ARGV assigns."""
    effects = {}
    for word in argv:
        if "${" in word:
            _expand(word, home, visible, here, effects=effects)
    store.update(effects)
    visible.update(effects)


def _shown(text):
    """TEXT as the agent wrote it, with each lifted substitution put back."""
    return text.replace(SUB, "$(...)").replace(PWD_SUB, "$(pwd)")


def _above(path, here):
    """Whether PATH is a directory above HERE."""
    return path != here and (path == "/" or here.startswith(path.rstrip("/") + "/"))


def _ancestors(path):
    """Every directory above PATH, nearest first, up to `/`."""
    out = []
    while path not in ("/", ""):
        path = os.path.dirname(path)
        out.append(path)
    return out


def _may_matter(words):
    """Whether a command that is not a `cd` and holds no nested text may
    assign a name or run chown, chmod or chgrp."""
    return any("=" in w or "${" in w or w in NAME_SETTERS for w in words) or bool(
        PROGRAM_TEXT.search(" ".join(words)))


def _merged(worlds):
    """WORLDS as one, the first's names, with every directory unknown."""
    heres, assigns = worlds[0]
    return [({k: None for k in heres}, assigns)]


def _here_weak(assigned):
    """Whether the directory was reached through a value taken as empty."""
    return assigned.get(WEAK_PWD, False)


def _cd_operand(lead):
    """The index in LEAD of `cd`'s directory operand, after its options, or None."""
    i = 1
    while i < len(lead) and CD_OPTION.fullmatch(lead[i]):
        i += 1
    if i < len(lead) and lead[i] == "--":
        i += 1
    return i if i < len(lead) else None


def _bare_cd_operands(piece):
    """The operands of `cd` in PIECE written unquoted, as whole words."""
    return {m.group(1) for m in BARE_CD.finditer(piece)}


def _nested(words):
    """The `sh -c` texts WORDS starts, in order (`sudo sh -c '...'` too),
    then a copy of each with `\\$` and `\\`` unescaped."""
    try:
        texts = shell_c_expansions(shlex.join(words), max_depth=1)[1:]
    except Exception:  # a text this cannot rebuild starts nothing it can read
        return []
    # Inside double quotes bash drops the backslash of `\$` and `\``, which
    # shlex keeps; the quotes are gone by now, so both readings are scanned.
    return texts + [t.replace("\\$", "$").replace("\\`", "`") for t in texts
                    if "\\$" in t or "\\`" in t]


def _scan(piece, cwd, home, outer, level=0, ctx=None):
    """The first `(segment, program, target, path, why)` hit in PIECE, or None.

    OUTER holds the names visible where PIECE runs. A `sh -c` text or a
    substitution is read where it appears, in each way the command may run
    up to there, with that run's directory and names: it starts in the
    directory of the shell that runs it, and sees its names through the outer
    shell's expansion of a double-quoted text or through the environment.

    CTX is shared by the whole command: a nested text already read in the
    same directory with the same names it uses is not read again, and past
    MAX_WORK words read, a nested text is read with no directory, and the
    ways the command may run are merged into one, with the directory unknown
    and the first way's names.
    """
    ctx = {"seen": set(), "work": 0, "split": {}, "uses": {}} if ctx is None else ctx
    if not PROGRAM_TEXT.search(re.sub(r"[\\'\"]", "", piece)):
        return None  # no chown, chmod or chgrp anywhere in it, quotes aside
    if piece not in ctx["split"]:
        ctx["split"][piece] = (_split(piece),
                               _bare_cd_operands(_comment_free(_heredoc_free(piece))))
    (cmds, inner), bare = ctx["split"][piece]
    cmds = cmds and [(scope[:MAX_SCOPE], argv) for scope, argv in cmds]
    # A WORLD is one way the command may run: for each scope, the directory
    # the shell is in (`None` when this cannot name it) and the names
    # assigned there. A `cd` or assignment inside `( ... )` changes only that
    # subshell, so each is kept per scope and read through the scope's
    # ancestors. A `${D:=x}` default assigns D, and like a plain assignment it
    # is read as run (see Limits).
    # A `cd` that may not run forks every world in two, one where it ran and
    # one where it did not, so `$PWD`, a name assigned from it, and `.` are
    # each judged in every directory the shell may be in. Past MAX_WORLDS the
    # directory is no longer split, and becomes `None`.
    # BLOCKS holds the `if`, loop and `case` commands open here: any `cd`
    # inside one may not run, except in the condition of the one it opens
    # (`if cd x; then`, `while ! cd x`). A `{ ... }` group runs.
    # A loop runs its body and a `while`/`until` condition any number of
    # times, so a `cd ..` there may reach every directory above.
    # Each lifted substitution is matched to the command whose words hold its
    # SUB, in order; when the counts disagree, each is read with no directory.
    subs = sum(w.count(SUB) for _, argv in cmds or [] for w in argv)
    aligned = subs == len(inner)
    if not aligned:
        for text in inner:
            hit = _nested_hit(text, None, home, outer, level, ctx)
            if hit:
                return hit
    worlds, blocks, taken, loop_names = [({(0,): cwd}, {})], [], 0, set()
    for scope, argv in cmds or []:
        # `then cd /etc`, `{ cd /usr; }`: a keyword ends the command before.
        words, opened = argv, None
        while words and words[0] in SHELL_KEYWORDS:
            if words[0] in ("for", "select") and len(words) > 1:
                loop_names.add(words[1])
            if words[0] in BLOCK_OPEN:
                blocks.append(words[0])
                opened = words[0]
            elif words[0] in BLOCK_CLOSE and blocks:
                blocks.pop()
            words = words[1:]
        maybe = len(blocks) - (opened in CONDITION_OPEN) > 0
        looped = any(b in LOOPS for b in blocks)
        lead = words
        while lead and lead[0] in ("time", "-p", "command", "builtin"):
            lead = lead[1:]
        lead = _without_redirects(lead)  # `pushd d >/dev/null` has one operand
        is_cd = bool(lead) and lead[0] in ("cd", "pushd", "popd")
        count = sum(w.count(SUB) for w in argv)
        shell_texts = _nested(words)
        texts = (inner[taken:taken + count] if aligned else []) + shell_texts
        taken += count
        if not (is_cd or texts or _may_matter(words)):
            continue  # it neither moves, assigns nor runs chown, chmod or chgrp
        if len(worlds) > 1 and ctx["work"] + len(argv) * len(worlds) > MAX_WORK:
            worlds = _merged(worlds)
        forked = []
        for heres, assigns in worlds:
            here = next(heres[scope[:k]] for k in range(len(scope), 0, -1)
                        if scope[:k] in heres)
            # Innermost scope first; a write lands in this scope's own names.
            store = assigns.setdefault(scope, {})
            assigned = ChainMap(store, *(assigns.get(scope[:k], {})
                                         for k in range(len(scope) - 1, 0, -1)), outer)
            ctx["work"] += len(argv)
            first_shell = len(texts) - len(shell_texts)
            for k, text in enumerate(texts):
                # Past the budget, even within one command, with no directory.
                over = ctx["work"] > MAX_WORK
                prefix = _prefix_names(words, home, assigned, here) if k >= first_shell else {}
                # A double-quoted text was expanded with the outer names before
                # the shell ran, a single-quoted one with these: unless it is
                # written single-quoted, read it both ways.
                quoted = f"'{text}'" in piece and f'"{text}"' not in piece
                readings = [ChainMap(prefix, assigned)] + ([] if quoted else [assigned])
                for names in (readings if prefix else [assigned]):
                    hit = _nested_hit(text, None if over else here, home, names, level, ctx)
                    if hit:
                        return hit
            _defaults(argv, home, store, assigned, here)
            if is_cd:
                got = [_expand(tok, home, assigned, here) for tok in lead[1:]]
                cd_words = [lead[0]] + [g[0] if g and g is not UNREAD and not g[1] else None
                                        for g in got]
                unknown = None in cd_words or any(SUB in tok for tok in lead)
                new = None if unknown else resolve_cd_target(cd_words, here)
                # From an unknown directory only an absolute target is known.
                new = new if new and (here or os.path.isabs(new)) and len(new) <= PATH_MAX else None
                news, fork, stay = [new], maybe, here
                stay_weak = _here_weak(assigned)  # the world the `cd` leaves in place
                operand = _cd_operand(lead)
                # A relative `cd` from a weak directory stays weak.
                weak_here = stay_weak and not (
                    operand and cd_words[operand] and cd_words[operand].startswith("/"))
                stack = assigned.get(DIR_STACK, ())
                if lead[0] == "pushd":  # `pushd DIR` pushes where it was
                    plain = len(lead) == 2 and not lead[1].startswith(("-", "+"))
                    store[DIR_STACK] = (stack + ((here, stay_weak),)
                                        if plain and stack is not None
                                        and len(stack) < MAX_SCOPE else None)
                elif lead[0] == "popd":  # `popd` returns there
                    if stack and len(lead) == 1:
                        (new, weak_here), store[DIR_STACK] = stack[-1], stack[:-1]
                    elif stack is not None and len(lead) == 1:  # empty: it fails, stays
                        new, weak_here = here, stay_weak
                    else:
                        store[DIR_STACK] = None
                tok = lead[operand] if operand else None
                reading = got[operand - 1] if operand else None
                looped_name = tok and any(
                    (m.group(1) or m.group(2)) in loop_names for m in VARIABLE.finditer(tok))
                if lead[0] not in ("cd", "pushd") or not tok or SUB in tok or looped_name:
                    pass  # no operand, or one this cannot read: as resolved above
                elif lead[0] == "cd" and reading and reading is not UNREAD and reading[0] == "":
                    # An unquoted empty `cd $D` goes home; quoted, it stays put.
                    new = here
                    if tok in bare:
                        news, fork = [home], True
                    else:
                        news = [new]
                elif reading and reading is not UNREAD and reading[1] and reading[0] and (
                        here or reading[0].startswith("/")):
                    # `cd "$OUT/tmp"` with OUT unset is `cd /tmp`, and with it
                    # set goes somewhere this cannot name: the directory is weak
                    # in the first world and unknown in the second.
                    # When the `cd` may not run, the shell may also stay put.
                    # From an unknown directory only an absolute value is read.
                    path = os.path.normpath(os.path.join(here or "/", reading[0]))
                    path = path if len(path) <= PATH_MAX else None
                    fork, weak_here = True, True
                    if path == here:  # `cd "${OUT}."`: it stays, weakly, or moves
                        news, stay_weak = [None], stay_weak or not maybe
                    elif maybe:
                        news = [path, None]
                    else:
                        news, stay = [path], None
                if looped and new and here and _above(new, here):
                    # Repeated, an up-move may reach every directory above.
                    news, fork = _ancestors(here)[::-1], True
                news = [n for n in news if n != here]
                room = MAX_WORLDS - len(worlds) - len(forked)
                # Past the budget, the farthest directories above are kept.
                for n in news[:room] if fork and news and room > 0 else []:
                    moved = {k: dict(v) for k, v in assigns.items()}
                    moved.setdefault(scope, {})[WEAK_PWD] = weak_here
                    forked.append(({**heres, scope: n}, moved))
                if fork and news and room > 0:
                    heres[scope] = stay  # where this world is if the `cd` did not move it
                    store[WEAK_PWD] = stay_weak
                else:
                    heres[scope] = None if fork and news else new
                    store[WEAK_PWD] = weak_here
                continue
            if _assignments(words, store, assigned, home, here):
                continue
            hit = _judge(words, home, assigned, here)
            if hit:
                return hit
        worlds.extend(forked)
        if ctx["work"] > MAX_WORK and len(worlds) > 1:
            worlds = _merged(worlds)
    return None


def _without_redirects(argv):
    """ARGV without its redirections (`> f`, `2> f`, `<f`): split, each is an
    operator word, its target, and any file-descriptor number before it."""
    out, skip = [], False
    for i, tok in enumerate(argv):
        if skip:
            skip = False
        elif tok and set(tok) <= set("<>&"):
            if out and out[-1].isdigit() and i and argv[i - 1] is out[-1]:
                out.pop()
            skip = True
        else:
            out.append(tok)
    return out


def _prefix_names(words, home, visible, here):
    """The `NAME=value` words before a shell's `-c` option (`D=/x sh -c`,
    `sudo D=/x sh -c`, `env D=/x sh -c`), as names its text starts with."""
    names = {}
    for word in words:
        if word.startswith("-") and not word.startswith("--") and "c" in word:
            break
        if ASSIGNMENT.match(word):
            name, _, val = word.partition("=")
            computed = "`" in val or SUB in val
            # In order: `D=/etc E=$D sh -c` sets E to /etc.
            names[name] = (None if computed
                           else _expand(val, home, ChainMap(names, visible), here))
    return names


def _nested_hit(text, here, home, names, level, ctx):
    """`_scan` of a nested TEXT, unless it is past MAX_DEPTH or read already."""
    if level >= MAX_NESTED:
        here = None  # deeper texts are read once, with no directory
    if text not in ctx["uses"]:
        ctx["uses"][text] = sorted({m.group(1) or m.group(2) for m in VARIABLE.finditer(text)
                                    if m.group(1) or m.group(2)}
                                   | {WEAK_PWD} | ({"HOME"} if "~" in text else set()))
    names = {k: names[k] for k in ctx["uses"][text] if k in names}
    key = (text, here, repr(sorted(names.items())))
    if level >= MAX_DEPTH or key in ctx["seen"]:
        return None
    ctx["seen"].add(key)
    return _scan(text, here, home, names, level + 1, ctx)


def _judge(words, home, assigned, here):
    """`(segment, program, target, path, why)` when WORDS hits a protected path."""
    head, override = _program(words)
    if not head or override:
        return None
    program = os.path.basename(head[0])
    for target in _targets(program, head):
        expanded = _expand(target, home, assigned, here)
        if expanded is UNREAD:
            return _shown(" ".join(words)), program, _shown(target), None, UNREAD_WHY
        candidates = [expanded]
        if expanded and "$" in target and expanded[0].split() != [expanded[0]]:
            # Unquoted, bash splits `$DIRS` into words (`"$EXTRA /etc"` with
            # EXTRA unset is ` /etc`); quotes are gone by now, so the value is
            # judged whole and word by word.
            candidates += [(field, expanded[1]) for field in expanded[0].split()]
        for cand, weak in filter(None, candidates):
            if not cand:
                continue  # an empty operand is an error, not the cwd
            if not cand.startswith("/"):
                if here is None:
                    continue
                cand, weak = os.path.join(here, cand), weak or _here_weak(assigned)
            path = os.path.normpath(cand).replace("//", "/")
            if ALL_GLOB.match(os.path.basename(path)):
                path = os.path.dirname(path)
            why = _why(path, home, weak)
            if why:
                return _shown(" ".join(words)), program, _shown(target), path, why
    return None


def _hit(command, cwd, home):
    """`(segment, program, target, path, why)` for the first protected target."""
    return _scan(command, cwd, home, {})


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"no-recursive-chown-system-path: unreadable hook input ({exc})", file=sys.stderr)
        return 0
    if simple_commands_with_scope is None or not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command",
                                        "terminal", "shell"):
        return 0
    inp = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or ""
    if not isinstance(command, str):
        return 0
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    home = os.path.normpath(os.path.expanduser("~"))
    hit = _hit(command, cwd, home)
    if not hit:
        return 0
    segment, program, target, path, why = hit
    where = why if path is None else f"which can resolve to `{path}`, {why}"
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": DENY.format(
            segment=segment, program=program, target=target, where=where,
            override=OVERRIDE),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
