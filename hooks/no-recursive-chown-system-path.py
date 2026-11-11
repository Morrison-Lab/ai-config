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
directory before it is judged too, `$PWD` included; a name assigned from
`$PWD` there keeps the worst of its values),
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
empty. A command substitution outside single quotes, heredoc bodies and
comments is lifted out before the command is split, scanned as a command of
its own, and taken as empty, except a bare `pwd`, read as `$PWD`. Inside `sh -c`
or a substitution the working directory is unknown, so only absolute targets
are judged there.

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
`for` or `select` loop variable, `eval`, `su -c`, a heredoc piped to `sh`, an
interpreter's own `-c` (`python -c "os.system(...)"`), a substitution in an
unquoted heredoc body (`<<EOF`, which bash does run), a glob in a directory
component (`/*/lib`), a partial glob or brace expansion that names a
protected path (`/et*`, `/{etc,usr}`), a wrapper that changes directory
(`env -C /etc`, `sudo -D /etc`), PowerShell `icacls`/`Set-Acl`, Windows drive
paths (`C:/Windows`), a relative target after a `cd` this cannot
resolve (`cd -` or `cd "$UNSET"`), a `cd` that fails or follows `&&` or
`||` (read as run), an assignment that may not run
(`false && D=./x` or `if false; then : "${D:=./x}"; fi`, each read as run), a
`${D:=x}` assignment inside `sh -c` or a substitution, an assignment in a
pipeline element (`echo x | : "${D:=./x}"`, read as made in the shell that
follows), a `${D:=x}` read earlier in the same command than it assigns, and
a bind-mounted path (the #39283 `/volumes/mail/` case) all pass. Fails open
on parse trouble and when scripts/lib/shellcmd.py cannot be imported.
"""
from __future__ import annotations

import json
import os
import re
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
WRAPPERS = (set(COMMAND_WRAPPERS) | {"setsid", "busybox", "pkexec"}
            if simple_commands_with_scope else set())
# Wrappers that take positional words before the program (`timeout 60 chmod`).
WRAPPER_POSITIONALS = {"timeout": 1}
# Each wrapper's short options that take the next word as their value; any
# other option is a flag, so `sudo -E echo chown` runs echo, not chown.
# Sources: the getopt strings in sudo's src/parse_args.c, OpenBSD's doas.c,
# and the env.c of GNU coreutils and FreeBSD.
WRAPPER_VALUE_OPTIONS = {"sudo": set("acugpCUrtTDR"), "doas": set("auC"),
                         "env": set("auCSPLU"),
                         "timeout": set("sk"), "nice": {"n"}, "ionice": set("cnp"),
                         "stdbuf": set("ioe"), "pkexec": {"u"}, "time": {"f", "o"},
                         "exec": {"a"}}
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
UNREAD_WHY = ("which uses a `${...}` operator this guard does not read, here or "
              "in an earlier assignment (anything but a `-`/`=` default or a `?` "
              f"check, or defaults nested deeper than {MAX_NESTING}); write the path out")
# Words that open and close a compound command, for `_scan`'s DEPTH.
BLOCK_OPEN = {"if", "while", "until", "for", "select", "case"}
BLOCK_CLOSE = {"fi", "done", "esac"}
# Keywords whose own condition always runs (`if cd x; then`).
CONDITION_OPEN = {"if", "while", "until"}
DECLARE_BUILTINS = ("export", "local", "declare", "readonly", "typeset")
# chmod's own short options (GNU and BSD); any other `-w` or `-x` is a mode.
CHMOD_OPTIONS = set("cfvRHLPh")
TOP_LEVEL = {"bin", "boot", "dev", "etc", "home", "lib", "lib32", "lib64", "libx32",
             "media", "mnt", "opt", "proc", "root", "run", "sbin", "srv", "sys",
             "tmp", "usr", "var", "Applications", "Library", "System", "Users",
             "Volumes", "cores", "private"}
SYSTEM_TREES = ("/usr", "/etc", "/bin", "/sbin", "/lib", "/lib32", "/lib64",
                "/libx32", "/boot", "/var/lib", "/var/log", "/var/spool",
                "/System", "/Library", "/private/etc", "/private/var/db")
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
PWD_COMMAND = re.compile(r"pwd(\s+-[LP]+)*")
PWD_USE = re.compile(r"\$\{?PWD(?![A-Za-z0-9_])")
ALL_GLOB = re.compile(r"\A[*?.]*[*?][*?.]*\Z")

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
    """`(text with each running $(...) and `...` replaced by SUB, [inner texts])`.

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
        elif not single and text.startswith("$(", i) and not text.startswith("$((", i):
            j = _close(text, i + 2)
            if j is not None:
                out.append(_lifted(text[i + 2:j], inner))
                i = j + 1
                continue
        elif not single and ch == "`" and "`" in text[i + 1:]:
            j = text.index("`", i + 1)
            out.append(_lifted(text[i + 1:j], inner))
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), inner


def _lifted(body, inner):
    """What a substitution of BODY stands for: `${PWD}` for `pwd`, else SUB.

    Any other body goes in INNER, to be checked as a command of its own.
    """
    if PWD_COMMAND.fullmatch(body.strip()):
        return "${PWD}"
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
    text = re.sub(r"\A~([+-])(?=/|\Z)",
                  lambda m: "${PWD}" if m.group(1) == "+" else "${OLDPWD}", text)
    text = re.sub(r"\A~([A-Za-z0-9_.-]*)(?=/|\Z)",
                  lambda m: os.path.expanduser("~" + m.group(1)) if m.group(1) else home,
                  text)
    guessed, undecidable, capped = [], [], []

    def value(name, rest):
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
            val, missing = here or "", here is None
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
        # with none, read sets REPLY and mapfile sets MAPFILE; getopts also
        # sets OPTARG.
        for word in [*rest, "REPLY", "MAPFILE", "OPTARG"]:
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
        _expand(word, home, visible, here, effects=effects)
    store.update(effects)
    visible.update(effects)


def _per_dir(dirs, home, store, visible, step):
    """Run STEP(store, visible, directory) once for each of DIRS; its result.

    With one directory this is a plain call. With several, `$PWD` differs
    between them (`if [ -d x ]; then cd x; fi; X=$PWD`), so each name STEP
    assigns keeps, of its readings, one that is protected or refused, else
    the last; a later use of it is then judged as the worst case.
    """
    if len(dirs) == 1:
        return step(store, visible, dirs[0])
    runs = []
    for d in dirs:
        st, vis = {}, dict(visible)
        runs.append((step(st, vis, d), st))
    for name in dict.fromkeys(n for _, st in runs for n in st):
        readings = [st[name] for _, st in runs if name in st]
        store[name] = visible[name] = next(
            (r for r in readings if r is UNREAD or r and r[0].startswith("/")
             and _why(os.path.normpath(r[0]), home, r[1])), readings[-1])
    return runs[-1][0]


def _scan(piece, cwd, home, outer):
    """`(hit or None, [inner command substitutions], names assigned)` for one text.

    OUTER holds names an enclosing text assigned: a `sh -c` body or a
    substitution sees them, through the outer shell's own expansion of a
    double-quoted body or through the environment.
    """
    cmds, inner = _split(piece)
    # A `cd` or assignment inside `( ... )` changes only that subshell, so each
    # is kept per scope and read through the scope's ancestors.
    # A `${D:=x}` default assigns D, and like a plain assignment it is read as
    # run (see Limits).
    # Each scope keeps every directory the shell may be in: a `cd` after a
    # keyword (`if [ -d x ]; then cd x; fi`) may not run, so the directory
    # before it stays possible. `None` is a directory this cannot name.
    # DEPTH counts the `if`, loop and `case` commands open here: any `cd`
    # inside one may not run, except in the condition of the one it opens
    # (`if cd x; then`, `while ! cd x`). A `{ ... }` group runs.
    heres, assigns, depth = {(0,): (cwd,)}, {}, 0
    for scope, argv in cmds or []:
        dirs = next(heres[scope[:k]] for k in range(len(scope), 0, -1) if scope[:k] in heres)
        # With more than one possible directory, `$PWD` has no one value.
        here = dirs[0] if len(dirs) == 1 else None
        assigned = dict(outer)
        for k in range(1, len(scope) + 1):
            assigned.update(assigns.get(scope[:k], {}))
        store = assigns.setdefault(scope, {})
        _per_dir(dirs, home, store, assigned,
                 lambda st, vis, d: _defaults(argv, home, st, vis, d))
        # `then cd /etc`, `{ cd /usr; }`: a keyword ends the command before.
        opened = None
        while argv and argv[0] in SHELL_KEYWORDS:
            depth += (argv[0] in BLOCK_OPEN) - (argv[0] in BLOCK_CLOSE)
            opened = argv[0] if argv[0] in BLOCK_OPEN else opened
            argv = argv[1:]
        maybe = depth - (opened in CONDITION_OPEN) > 0
        lead = argv
        while lead and lead[0] in ("time", "-p", "command", "builtin"):
            lead = lead[1:]
        if lead and lead[0] in ("cd", "pushd", "popd"):
            words = [lead[0]]
            for tok in lead[1:]:
                got = _expand(tok, home, assigned, here)
                known = got and got is not UNREAD and not got[1]
                words.append(got[0] if known else None)
            moved = None in words or any(SUB in tok for tok in lead)
            new = tuple(None if moved else resolve_cd_target(words, d) for d in dirs)
            heres[scope] = tuple(dict.fromkeys((*dirs, *new) if maybe else new))
            continue
        if _per_dir(dirs, home, store, assigned, lambda st, vis, d: _assignments(
                argv, st, vis, home, d)):
            continue
        head, override = _program(argv)
        if not head or override:
            continue
        program = os.path.basename(head[0])
        for target, base in ((t, d) for t in _targets(program, head) for d in dirs):
            # Judged once per possible directory, for `.` and `$PWD` alike.
            expanded = _expand(target, home, assigned, base)
            if expanded is UNREAD:
                shown = " ".join(argv).replace(SUB, "$(...)")
                target = target.replace(SUB, "$(...)")
                return (shown, program, target, None, UNREAD_WHY), inner, {}
            for cand, weak in filter(None, [expanded]):
                if not cand:
                    continue  # an empty operand is an error, not the cwd
                if not cand.startswith("/"):
                    if base is None:
                        continue
                    cand = os.path.join(base, cand)
                path = os.path.normpath(cand).replace("//", "/")
                if ALL_GLOB.match(os.path.basename(path)):
                    path = os.path.dirname(path)
                why = _why(path, home, weak)
                if why:
                    shown = " ".join(argv).replace(SUB, "$(...)")
                    target = target.replace(SUB, "$(...)")
                    return (shown, program, target, path, why), inner, {}
    seen = dict(outer)
    for names in assigns.values():
        seen.update(names)
    return None, inner, seen


def _hit(command, cwd, home):
    """`(segment, program, target, path, why)` for the first protected target.

    Only the command itself runs in CWD; a `sh -c` text or a substitution
    gets `None`, so its relative targets are left alone.
    """
    pending = [(piece, cwd if n == 0 else None)
               for n, piece in enumerate(shell_c_expansions(command))]
    known = {}  # every name assigned so far, over-approximating its scope
    while pending:
        piece, here = pending.pop(0)
        hit, inner, seen = _scan(piece, here, home, known)
        if hit:
            return hit
        known.update(seen)
        for text in inner:
            pending.extend((nested, None) for nested in shell_c_expansions(text))
    return None


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
    where = why if path is None else f"which resolves to `{path}`, {why}"
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
