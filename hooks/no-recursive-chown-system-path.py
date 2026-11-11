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
`sudo` or another wrapper, or inside `sh -c`) when a target is:

  * `/`, or any top-level directory (`/usr`, `/etc`, `/home`, `/mnt`, ...);
  * anything inside a system tree (`SYSTEM_TREES`), except below `/usr/local`,
    where only `/usr/local` and its `USR_LOCAL_CORE` children are refused
    (`/usr/local/lib/node_modules` and `/usr/local/Cellar` are user-managed);
  * the home directory, or a directory that contains it.

A target is read with `~`, `~user` and `$HOME` expanded, relative paths
resolved against the hook's `cwd` and any `cd` earlier in the same command,
and a trailing glob read as its directory (`/usr/*` touches `/usr`). Any
other `$VAR` is tried both with its value in this environment and as empty,
because a variable set by an earlier Bash call is empty in this one
(anthropics/claude-code#75859): `chmod -R 755 "$d/"` is `/`. A path that
exists only because a variable was taken as empty is refused for the root,
a system tree or home, but not for a top-level directory: `$OUT/dist` with
OUT unset is `/dist`. A command substitution is lifted out before the
command is split, scanned as a command of its own, and taken as empty.

A deny, not a warning: the remedy (fix the one path that raised the error, as
your own user) is always available, and the damage is unrecoverable without a
console. Escape hatch for a case this did not foresee: a real leading
`ALLOW_RECURSIVE_SYSTEM_CHOWN=1` assignment on the same command, with the
reason stated in the reply.

Limits, deliberately unclosed: `find ... -exec chown`, `xargs chown`, a
`for` loop variable, `eval`, `su -c`, a heredoc piped to `sh`, an
interpreter's own `-c` (`python -c "os.system(...)"`), PowerShell
`icacls`/`Set-Acl`, Windows drive paths (`C:/Windows`), and a bind-mounted
path (the #39283 `/volumes/mail/` case) all pass. Fails open on parse
trouble and when scripts/lib/shellcmd.py cannot be imported.
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
    from shellcmd import (COMMAND_WRAPPERS, SHELL_KEYWORDS, WRAPPER_ARG_WINDOW,
                          resolve_cd_target, shell_c_expansions, simple_commands)
except Exception as _exc:  # broken install: say so, then allow
    print(f"no-recursive-chown-system-path: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    simple_commands = None

OVERRIDE = "ALLOW_RECURSIVE_SYSTEM_CHOWN=1"
PROGRAMS = {"chown", "chmod", "chgrp"}
WRAPPERS = set(COMMAND_WRAPPERS) | {"setsid", "busybox"} if simple_commands else set()
WINDOW = 12  # `sudo -u a -g b -H -n -E -S chmod` needs more than shellcmd's 6
CHMOD_OPTIONS = set("cfvR")  # chmod's own short options; `-w` or `-x` is a mode
SYSTEM_TREES = ("/usr", "/etc", "/bin", "/sbin", "/lib", "/lib32", "/lib64",
                "/libx32", "/boot", "/var/lib", "/var/log", "/var/spool",
                "/System", "/Library", "/private/etc", "/private/var/db")
# Below /usr/local, only these directories hold system-wide binaries and config;
# `/usr/local/lib/node_modules` and `/usr/local/Cellar` are user-managed.
USR_LOCAL_CORE = {"bin", "sbin", "etc", "lib", "libexec", "include", "share"}
ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
# A command substitution, lifted out before splitting (see `_lift`).
SUB = "__AICFG_CMDSUB__"
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)([^}]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)|"
                      + SUB)
GLOB = re.compile(r"[*?\[]")

DENY = (
    "Refused: `{segment}` runs `{program} -R` on `{target}`, which resolves to "
    "`{path}`, {why}. A recursive ownership or mode change there broke `sudo` "
    "in anthropics/claude-code#168 and #39283, and undoing it needs a console. "
    "Fix only the path that raised the error, as your own user, or ask the "
    "user to run it. If this case is genuinely safe, put `{override}` before "
    "the command and say why (shared/workflow/destructive-actions-catalog.md)."
)


def _lift(text):
    """`(text with each $(...) and `...` replaced by SUB, [their inner texts])`.

    `simple_commands` splits an unquoted `$(id -gn)` into words of its own, so
    `chown -R $USER:$(id -gn) /usr` would otherwise lose its program.
    """
    out, inner, i = [], [], 0
    while i < len(text):
        if text.startswith("$(", i) and not text.startswith("$((", i):
            depth, j = 1, i + 2
            while j < len(text) and depth:
                depth += {"(": 1, ")": -1}.get(text[j], 0)
                j += 1
            inner.append(text[i + 2:j - 1])
            out.append(SUB)
            i = j
        elif text[i] == "`" and "`" in text[i + 1:]:
            j = text.index("`", i + 1)
            inner.append(text[i + 1:j])
            out.append(SUB)
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out), inner


def _program(argv):
    """`(argv from the program on, override present)`, peeling wrappers."""
    override, since_wrapper = False, None
    for i, tok in enumerate(argv):
        if os.path.basename(tok) in PROGRAMS:
            return argv[i:], override
        if ASSIGNMENT.match(tok):
            override = override or tok == OVERRIDE
        elif tok in WRAPPERS:
            since_wrapper = 0
        elif tok in SHELL_KEYWORDS:
            continue
        elif since_wrapper is None or since_wrapper >= WINDOW:
            return [], override  # some other program runs here
        else:
            since_wrapper += 1  # a wrapper's own option or value (`sudo -u me`)
    return [], override


def _targets(program, head):
    """The file operands of a recursive invocation, or `[]` if not recursive."""
    recursive, reference, operands, end = False, False, [], False
    for tok in head[1:]:
        if end or tok == "-" or not tok.startswith("-"):
            operands.append(tok)
        elif tok == "--":
            end = True
        elif tok == "--recursive":
            recursive = True
        elif tok.startswith("--reference"):
            reference = True
        elif tok.startswith("--"):
            continue
        elif program == "chmod" and not set(tok[1:]) <= CHMOD_OPTIONS:
            operands.append(tok)  # a mode such as `-w` or `-x`
        elif "R" in tok[1:]:
            recursive = True
    if not recursive:
        return []
    return operands if reference else operands[1:]


def _candidates(target, home, assigned, here):
    """`[(path, weak)]` for every path TARGET can expand to.

    Each variable is tried with its value here and as empty; a `weak`
    candidate exists only because some variable was taken as empty. A
    variable ASSIGNED earlier in the same command keeps its literal value, or
    makes the target undecidable (`[]`) when that value is computed, as in
    `d=$(mktemp -d)`. A command substitution is always unknown, so it is
    taken as empty.
    """
    target = re.sub(r"\A~([A-Za-z0-9_.-]*)(?=/|\Z)",
                    lambda m: os.path.expanduser("~" + m.group(1)) if m.group(1) else home,
                    target)
    for match in VARIABLE.finditer(target):
        name = match.group(1) or match.group(3)
        if name in assigned and assigned[name] is None:
            return []

    def value(match, empty, guessed):
        if match.group(0) == SUB:
            guessed.append(True)
            return ""
        name, rest = match.group(1) or match.group(3), match.group(2) or ""
        if name in assigned:
            val = assigned[name]
        elif name == "HOME":
            val = home
        elif name == "PWD":
            val = here or ""
        else:
            val = "" if empty else os.environ.get(name, "")
            guessed.append(not val)
        if rest.startswith((":-", "-")) and not val:
            val = rest.split("-", 1)[1]
        return val

    results = []
    for empty in (False, True):
        guessed = []
        path = VARIABLE.sub(lambda m: value(m, empty, guessed), target)
        if all(path != seen for seen, _ in results):
            results.append((path, any(guessed)))
    return results


def _assignments(argv, assigned):
    """Record `NAME=value` from a simple command that only assigns."""
    words = argv[1:] if argv and argv[0] in ("export", "local", "declare", "readonly") else argv
    if not words or not all(ASSIGNMENT.match(w) for w in words):
        return False
    for word in words:
        name, _, val = word.partition("=")
        computed = "$" in val or "`" in val or SUB in val
        assigned[name] = None if computed else val
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
    for tree in SYSTEM_TREES:
        if path == tree or path.startswith(tree + "/"):
            return f"inside the system tree `{tree}`"
    if home and (path == home or home.startswith(path + "/")):
        return "the home directory or a directory that contains it"
    if path.count("/") == 1 and not weak:
        return "a top-level directory"
    return None


def _scan(piece, cwd, home):
    """`(hit or None, [inner command substitutions])` for one shell text."""
    lifted, inner = _lift(piece)
    here, assigned = cwd, {}
    for argv in simple_commands(lifted) or []:
        if argv and argv[0] in ("cd", "pushd", "popd"):
            here = resolve_cd_target(argv, here)
            continue
        if _assignments(argv, assigned):
            continue
        head, override = _program(argv)
        if not head or override:
            continue
        program = os.path.basename(head[0])
        for target in _targets(program, head):
            for cand, weak in _candidates(target, home, assigned, here):
                if not cand:
                    continue  # an empty operand is an error, not the cwd
                if not cand.startswith("/"):
                    if here is None:
                        continue
                    cand = os.path.join(here, cand)
                path = os.path.normpath(cand).replace("//", "/")
                if GLOB.search(os.path.basename(path)):
                    path = os.path.dirname(path)
                why = _why(path, home, weak)
                if why:
                    shown = " ".join(argv).replace(SUB, "$(...)")
                    return (shown, program, target.replace(SUB, "$(...)"), path, why), inner
    return None, inner


def _hit(command, cwd, home):
    """`(segment, program, target, path, why)` for the first protected target."""
    pending = list(shell_c_expansions(command))
    while pending:
        hit, inner = _scan(pending.pop(0), cwd, home)
        if hit:
            return hit
        for text in inner:
            pending.extend(shell_c_expansions(text))
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"no-recursive-chown-system-path: unreadable hook input ({exc})", file=sys.stderr)
        return 0
    if simple_commands is None or not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") not in ("Bash", "bash", "run_command", "execute_command",
                                        "terminal", "shell"):
        return 0
    inp = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or ""
    if not isinstance(command, str):
        return 0
    home = os.path.normpath(os.path.expanduser("~"))
    hit = _hit(command, payload.get("cwd") or os.getcwd(), home)
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
