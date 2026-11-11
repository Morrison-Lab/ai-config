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
  * anything inside a system tree (`SYSTEM_TREES`);
  * the home directory, or a directory that contains it.

A target is read with `~` and `$HOME` expanded, relative paths resolved
against the hook's `cwd` and any `cd` earlier in the same command, and a
trailing glob read as its directory (`/usr/*` touches `/usr`). Any other
`$VAR` or command substitution is tried both with its value in this
environment and as empty, because a variable set by an earlier Bash call is
empty in this one (anthropics/claude-code#75859): `chmod -R 755 "$d/"` is `/`.

A deny, not a warning: the remedy (fix the one path that raised the error, as
your own user) is always available, and the damage is unrecoverable without a
console. Escape hatch for a case this did not foresee: a real leading
`ALLOW_RECURSIVE_SYSTEM_CHOWN=1` assignment on the same command, with the
reason stated in the reply.

Limits, deliberately unclosed: `find ... -exec chown`, `xargs chown`,
PowerShell `icacls`/`Set-Acl`, Windows drive paths (`C:/Windows`), and a
bind-mounted path (the #39283 `/volumes/mail/` case) all pass. Fails open on
parse trouble and when scripts/lib/shellcmd.py cannot be imported.
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
SYSTEM_TREES = ("/usr", "/etc", "/bin", "/sbin", "/lib", "/lib32", "/lib64",
                "/libx32", "/boot", "/var/lib", "/System", "/Library",
                "/private/etc", "/private/var")
ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
VARIABLE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)[^}/]*\}?|\$\([^)]*\)|`[^`]*`")
GLOB = re.compile(r"[*?\[]")

DENY = (
    "Refused: `{segment}` runs `{program} -R` on `{target}`, which resolves to "
    "`{path}`, {why}. A recursive ownership or mode change there broke `sudo` "
    "in anthropics/claude-code#168 and #39283, and undoing it needs a console. "
    "Fix only the path that raised the error, as your own user, or ask the "
    "user to run it. If this case is genuinely safe, put `{override}` before "
    "the command and say why (shared/workflow/destructive-actions-catalog.md)."
)


def _program(argv):
    """`(argv from the program on, override present)`, peeling wrappers."""
    override, since_wrapper = False, None
    for i, tok in enumerate(argv):
        if os.path.basename(tok) in PROGRAMS:
            return argv[i:], override
        if ASSIGNMENT.match(tok):
            override = override or tok == OVERRIDE
        elif tok in COMMAND_WRAPPERS:
            since_wrapper = 0
        elif tok in SHELL_KEYWORDS:
            continue
        elif since_wrapper is None or since_wrapper >= WRAPPER_ARG_WINDOW:
            return [], override  # some other program runs here
        else:
            since_wrapper += 1  # a wrapper's own option or value (`sudo -u me`)
    return [], override


def _targets(head):
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
        elif not tok.startswith("--") and "R" in tok[1:]:
            recursive = True
    if not recursive:
        return []
    return operands if reference else operands[1:]


def _candidates(target, home, assigned):
    """Every path TARGET can expand to: variables set, and variables empty.

    A variable ASSIGNED earlier in the same command keeps its literal value,
    or makes the target undecidable (`set()`) when that value is computed,
    as in `d=$(mktemp -d)`.
    """
    target = re.sub(r"\A~(?=/|\Z)", home, target)
    target = re.sub(r"\$\{?HOME\}?(?![A-Za-z0-9_])", home, target)
    names = {m.group(1) for m in VARIABLE.finditer(target)}
    if any(assigned.get(n) is None and n in assigned for n in names):
        return set()

    def value(match, empty):
        name = match.group(1)
        if name in assigned:
            return assigned[name]
        return "" if empty or not name else os.environ.get(name, "")

    return {VARIABLE.sub(lambda m: value(m, False), target),
            VARIABLE.sub(lambda m: value(m, True), target)}


def _assignments(argv, assigned):
    """Record `NAME=value` from a simple command that only assigns."""
    words = argv[1:] if argv and argv[0] in ("export", "local", "declare", "readonly") else argv
    if not words or not all(ASSIGNMENT.match(w) for w in words):
        return False
    for word in words:
        name, _, val = word.partition("=")
        assigned[name] = None if "$" in val or "`" in val else val
    return True


def _why(path, home):
    """Why PATH is protected, or `None`."""
    if path == "/":
        return "the filesystem root"
    if path.count("/") == 1:
        return "a top-level directory"
    for tree in SYSTEM_TREES:
        if path == tree or path.startswith(tree + "/"):
            return f"inside the system tree `{tree}`"
    if home and (path == home or home.startswith(path + "/")):
        return "the home directory or a directory that contains it"
    return None


def _hit(command, cwd, home):
    """`(segment, program, target, path, why)` for the first protected target."""
    for piece in shell_c_expansions(command):
        argvs = simple_commands(piece)
        here, assigned = cwd, {}
        for argv in argvs or []:
            if argv and argv[0] in ("cd", "pushd", "popd"):
                here = resolve_cd_target(argv, here)
                continue
            if _assignments(argv, assigned):
                continue
            head, override = _program(argv)
            if not head or override:
                continue
            for target in _targets(head):
                for cand in _candidates(target, home, assigned):
                    if not cand:
                        continue  # an empty operand is an error, not the cwd
                    if not cand.startswith("/"):
                        if here is None:
                            continue
                        cand = os.path.join(here, cand)
                    path = os.path.normpath(cand).replace("//", "/")
                    if GLOB.search(os.path.basename(path)):
                        path = os.path.dirname(path)
                    why = _why(path, home)
                    if why:
                        return " ".join(argv), os.path.basename(head[0]), target, path, why
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
