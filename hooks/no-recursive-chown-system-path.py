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

A target is read with `~`, `~user` and `$HOME` expanded, relative paths
resolved against the hook's `cwd` and any `cd` earlier in the same shell (a
`cd` inside `( ... )` moves only that subshell), and a basename made only of
glob characters read as its directory (`/usr/*` touches `/usr`). Any other
`$VAR` keeps its value in this environment, which the Bash call inherits; one
unset here is taken as empty, because a variable set by an earlier Bash call
is empty in this one (anthropics/claude-code#75859): `chmod -R 755 "$d/"` is
`/`. A path that
exists only because something was taken as empty is refused for the root, a
system tree or home, but not for a top-level directory: `$OUT/dist` with OUT
unset is `/dist`. A command substitution outside single quotes, heredoc
bodies and comments is lifted out before the command
is split, scanned as a command of its own, and taken as empty. Inside `sh -c`
or a substitution the working directory is unknown, so only absolute targets
are judged there.

A deny, not a warning: the remedy (fix the one path that raised the error, as
your own user) is always available, and the damage is unrecoverable without a
console. Escape hatch for a case this did not foresee: a real leading
`ALLOW_RECURSIVE_SYSTEM_CHOWN=1` assignment on the same command, with the
reason stated in the reply.

Limits, deliberately unclosed: `find ... -exec chown`, `xargs chown`, a
`for` loop variable, `eval`, `su -c`, a heredoc piped to `sh`, an
interpreter's own `-c` (`python -c "os.system(...)"`), a substitution in an
unquoted heredoc body (`<<EOF`, which bash does run), a glob in a directory
component (`/*/lib`), a partial glob or brace expansion that names a
protected path (`/et*`, `/{etc,usr}`), a wrapper that changes directory
(`env -C /etc`, `sudo -D /etc`), PowerShell `icacls`/`Set-Acl`, Windows drive
paths (`C:/Windows`), and a bind-mounted path (the #39283 `/volumes/mail/`
case) all pass. Fails open on parse trouble and when scripts/lib/shellcmd.py cannot
be imported.
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
WRAPPER_VALUE_OPTIONS = {"sudo": set("ughpCUrtTDR"), "doas": set("uC"), "env": set("uCS"),
                         "timeout": set("sk"), "nice": {"n"}, "ionice": set("cnp"),
                         "stdbuf": set("ioe")}
WRAPPER_VALUE_LONG = {"--user", "--group", "--host", "--prompt", "--chdir", "--chroot",
                      "--close-from", "--other-user", "--role", "--type",
                      "--command-timeout", "--unset", "--split-string", "--signal",
                      "--kill-after", "--adjustment", "--class", "--classdata", "--pid",
                      "--input", "--output", "--error"}
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
SUB = "__AICFG_CMDSUB__"  # a lifted command substitution (see `_lift`)
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)((?:[^{}]|\{[^{}]*\})*)\}|\$([A-Za-z_][A-Za-z0-9_]*)|"
                      + SUB)
ALL_GLOB = re.compile(r"\A[*?.]*[*?][*?.]*\Z")

DENY = (
    "Refused: `{segment}` runs `{program} -R` on `{target}`, which resolves to "
    "`{path}`, {why}. A recursive ownership or mode change there broke `sudo` "
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
                inner.append(text[i + 2:j])
                out.append(SUB)
                i = j + 1
                continue
        elif not single and ch == "`" and "`" in text[i + 1:]:
            j = text.index("`", i + 1)
            inner.append(text[i + 1:j])
            out.append(SUB)
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), inner


def _takes_next_word(wrapper, tok):
    """Whether a wrapper's option `tok` takes the next word as its value.

    Short options may be bundled: in `sudo -Eu root`, `-u` is the last
    letter, so `root` is its value; in `sudo -uroot`, the value is attached.
    """
    if tok.startswith("--"):
        return tok in WRAPPER_VALUE_LONG
    values = WRAPPER_VALUE_OPTIONS.get(wrapper, ())
    for j, letter in enumerate(tok[1:], 1):
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
            after_option = _takes_next_word(wrapper, tok)
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
        elif tok == "--recursive":
            recursive = True
        elif tok.startswith("--reference"):
            reference, skip = True, tok == "--reference"
        elif tok.startswith("--"):
            continue
        elif program == "chmod" and not set(tok[1:]) <= CHMOD_OPTIONS:
            operands.append(tok)  # a mode such as `-w` or `-x`
        elif "R" in tok[1:]:
            recursive = True
    if not recursive:
        return []
    return operands if reference else operands[1:]


def _expand(text, home, assigned, here):
    """`(TEXT expanded, weak)`, or `None` when a computed value makes it undecidable.

    A variable set in this environment keeps its value, since the Bash call
    inherits it too; one that is unset here is taken as empty, and the result
    is then `weak`. A `${VAR:-default}` default is expanded the same way, and
    is not a guess. ASSIGNED maps a name set earlier in the same command to
    its `(value, weak)`, or to `None` when that value was computed, as in
    `d=$(mktemp -d)`.
    """
    text = re.sub(r"\A~([A-Za-z0-9_.-]*)(?=/|\Z)",
                  lambda m: os.path.expanduser("~" + m.group(1)) if m.group(1) else home,
                  text)
    guessed, undecidable = [], []

    def value(match):
        if match.group(0) == SUB:
            guessed.append(True)
            return ""
        name, rest = match.group(1) or match.group(3), match.group(2) or ""
        missing = False
        if name in assigned:
            if assigned[name] is None:
                undecidable.append(name)
                return ""
            val, weak = assigned[name]
            guessed.append(weak)
        elif name == "HOME":
            val = home
        elif name == "PWD":
            val, missing = here or "", here is None
        else:
            val = os.environ.get(name, "")
            missing = not val
        default = re.match(r":?[-=]", rest)
        if default and not val:
            fallback = _expand(rest[default.end():], home, assigned, here)
            if fallback is None:
                undecidable.append(name)
                return ""
            (val, weak), missing = fallback, False
            guessed.append(weak)
        guessed.append(missing)
        return val

    expanded = VARIABLE.sub(value, text)
    return None if undecidable else (expanded, any(guessed))


def _assignments(argv, store, visible, home, here):
    """Record `NAME=value` from a simple command that only assigns.

    Values go in STORE as `(value, weak)`, expanded against the names VISIBLE
    so far; a command substitution makes one `None`.
    """
    words = argv
    if argv and argv[0] in DECLARE_BUILTINS:
        words = [w for w in argv[1:] if not w.startswith(("-", "+"))]
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


def _scan(piece, cwd, home):
    """`(hit or None, [inner command substitutions])` for one shell text."""
    cmds, inner = _split(piece)
    # A `cd` or assignment inside `( ... )` changes only that subshell, so each
    # is kept per scope and read through the scope's ancestors.
    heres, assigns = {(0,): cwd}, {}
    for scope, argv in cmds or []:
        here = next(heres[scope[:k]] for k in range(len(scope), 0, -1) if scope[:k] in heres)
        if argv and argv[0] in ("cd", "pushd", "popd"):
            moved = any(SUB in tok for tok in argv)
            heres[scope] = None if moved else resolve_cd_target(argv, here)
            continue
        assigned = {}
        for k in range(1, len(scope) + 1):
            assigned.update(assigns.get(scope[:k], {}))
        if _assignments(argv, assigns.setdefault(scope, {}), assigned, home, here):
            continue
        head, override = _program(argv)
        if not head or override:
            continue
        program = os.path.basename(head[0])
        for target in _targets(program, head):
            for cand, weak in filter(None, [_expand(target, home, assigned, here)]):
                if not cand:
                    continue  # an empty operand is an error, not the cwd
                if not cand.startswith("/"):
                    if here is None:
                        continue
                    cand = os.path.join(here, cand)
                path = os.path.normpath(cand).replace("//", "/")
                if ALL_GLOB.match(os.path.basename(path)):
                    path = os.path.dirname(path)
                why = _why(path, home, weak)
                if why:
                    shown = " ".join(argv).replace(SUB, "$(...)")
                    return (shown, program, target.replace(SUB, "$(...)"), path, why), inner
    return None, inner


def _hit(command, cwd, home):
    """`(segment, program, target, path, why)` for the first protected target.

    Only the command itself runs in CWD; a `sh -c` text or a substitution
    gets `None`, so its relative targets are left alone.
    """
    pending = [(piece, cwd if n == 0 else None)
               for n, piece in enumerate(shell_c_expansions(command))]
    while pending:
        piece, here = pending.pop(0)
        hit, inner = _scan(piece, here, home)
        if hit:
            return hit
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
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": DENY.format(
            segment=segment, program=program, target=target, path=path, why=why,
            override=OVERRIDE),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
