#!/usr/bin/env python3
r"""PreToolUse guard: refuse a recursive delete through a variable this shell never set.

## The incident

anthropics/claude-code#75859: an agent set a temporary `$HOME` in one Bash
call and ran `rm -rf "$HOME"` in a later one. Each Bash call starts a fresh
shell, so the assignment had not persisted and the command ran against the
real home directory. The same mistake with any other name is worse:
`D=/tmp/build` in one call and `rm -rf "$D/"` in the next deletes `/`.

CC Safety Net, the pinned base guard (`hooks/run-cc-safety-net.py`,
ai-config#5474), denies `rm -rf "$HOME"` at its standard level, but passes
`rm -rf "$D/"` and `rm -rf "$BUILD_DIR"/*` when the name is unset. Its strict
level denies both, but strict refused 112 of 797 distinct Bash commands from
one ordinary session, so the base guard stays at standard and this hook
covers the gap (ai-config#5476, part of #5317).

## What it denies

A recursive `rm` (`-r`, `-R`, `--recursive`, or a short cluster holding one
of them, such as `-rf`), and a `find` whose expression has `-delete` or runs
`rm` through `-exec`, `-execdir`, `-ok` or `-okdir`, when a target (for
`find`, a starting point) uses a variable that

  * is empty or unset in this hook's environment, which the Bash call
    inherits, and
  * is not assigned earlier in the same command.

Each `sh -c` text the command runs (`shellcmd.shell_c_expansions`) is read
the same way, with the names the outer command assigns counted as assigned.
`sudo`, `env`, `timeout` and the other `COMMAND_WRAPPERS` are looked through.

A reference reads as follows:

  * `$D`, `${D}`, and `${D<op>}` for an operator that yields empty when D is
    unset (`${D:+x}`, `${D%/}`, `${D#x}`, `${D/x/y}`, `${D:0:3}`, ...) are
    judged;
  * `${D:-x}`, `${D-x}`, `${D:=x}` and `${D=x}` carry a value and pass
    (`${D:=x}` and `${D=x}` also assign D for the rest of the command);
  * `${D:?}` and `${D?}` stop bash before the delete runs, and pass. This is
    the remedy the deny message suggests.

"Assigned earlier" means any of: a command that only assigns (`D=/x;`),
`export`, `local`, `declare`, `typeset` or `readonly` with `D=...`, `read`,
`mapfile`, `readarray` or `getopts` naming D, `printf -v D`, `for D in`,
`select D in`, or a `${D:=x}` default. A `NAME=value` word in front of the
delete itself does not count, because bash expands the delete's arguments
before it applies that assignment: `D=/x rm -rf "$D/"` runs on `/`.

After `source`, `.` or `eval`, any name may have been set, so the rest of
that command is not judged.

## What it does not read

A guard that reads bash statically is aimed at honest mistakes, not at a
command built to get past it. Not judged: positional and special parameters
(`$1`, `$@`, `$_`), indirect expansion (`${!D}`), names inside a command
substitution in a target (`"$(dirname "$D")"`, which is stripped before the
target is read), `xargs rm`, a function body (judged where it is defined),
an assignment that may not run (`false && D=/x; rm -rf "$D/"` passes), and
an assignment inside a subshell, which does not reach the parent but is
counted. `$'...'` quoting is read as single quoting, and an escaped `\$`
inside a double-quoted `sh -c` text is read as escaped in the inner text
too, because `shell_c_expansions` keeps the backslash.

## Escape hatch

A real leading `ALLOW_RM_UNSET_VARIABLE=1` assignment on the delete's own
simple command, with the reason stated in the reply. Fails open (passes) when
the hook input is unreadable, `scripts/lib/shellcmd.py` cannot be imported,
or the command cannot be split.
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
    from shellcmd import (COMMAND_WRAPPERS, SHELL_KEYWORDS, WRAPPER_ARG_WINDOW,
                          _comment_free, _heredoc_free, shell_c_expansions,
                          simple_commands)
except Exception as _exc:  # broken install: say so and pass
    print(f"no-recursive-rm-unset-variable: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not evaluating", file=sys.stderr)
    shell_c_expansions = simple_commands = None
    COMMAND_WRAPPERS = SHELL_KEYWORDS = frozenset()
    WRAPPER_ARG_WINDOW = 6

OVERRIDE = "ALLOW_RM_UNSET_VARIABLE=1"
ASSIGNMENT = re.compile(r"\A([A-Za-z_][A-Za-z0-9_]*)\+?=")
NAME = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*\Z")
# `$NAME`, or `${NAME<op>}` with the operator text captured.
REFERENCE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)([^}]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
# Operators whose result is not empty when the name is unset.
DEFAULTING = (":-", "-", ":=", "=")
ASSIGNING = (":=", "=")
STOPPING = (":?", "?")
# Stands in for a `$` that bash does not expand (single-quoted or escaped),
# so the dequoted tokens `shlex` returns still tell the two apart.
MASK = ""
PROGRAMS = {"rm", "find"}
DECLARE_BUILTINS = {"export", "local", "declare", "readonly", "typeset"}
READ_BUILTINS = {"read", "mapfile", "readarray", "getopts"}
SOURCING = {"source", ".", "eval"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
FIND_LEADING_OPTIONS = {"-H", "-L", "-P"}

DENY = (
    "Blocked: `{segment}` deletes recursively through `{ref}`, and `{name}` is "
    "unset in this shell. Each Bash call starts a fresh shell, so a variable "
    "set in an earlier call is empty here, and the target `{target}` becomes "
    "`{empty}` (anthropics/claude-code#75859, ai-config#5476). Assign `{name}` "
    "in this same command, write `${{{name}:?}}` so bash stops if it is unset, "
    "or write the literal path. If `{name}` really is meant to be empty here, "
    "put `{override}` in front of the delete on the same command and say why "
    "in your reply."
)


def _mask(text):
    """TEXT with every `$` bash would not expand replaced by MASK."""
    out, single, double, i = [], False, False, 0
    while i < len(text):
        ch = text[i]
        if single:
            single = ch != "'"
            out.append(MASK if ch == "$" else ch)
        elif ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append(ch)
            out.append(MASK if nxt == "$" else nxt)
            i += 2
            continue
        elif ch == "'" and not double:
            single = True
            out.append(ch)
        else:
            if ch == '"':
                double = not double
            out.append(ch)
        i += 1
    return "".join(out)


def _without_substitutions(token):
    """TOKEN with each `$(...)`, `$((...))` and backtick span removed."""
    out, i = [], 0
    while i < len(token):
        if token.startswith("$(", i):
            depth, j = 0, i + 1
            while j < len(token):
                if token[j] == "(":
                    depth += 1
                elif token[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            i = j + 1
            continue
        if token[i] == "`":
            end = token.find("`", i + 1)
            i = len(token) if end < 0 else end + 1
            continue
        out.append(token[i])
        i += 1
    return "".join(out)


def _defaults_assigned(token, assigned):
    """Add each name a `${D:=x}` or `${D=x}` in TOKEN assigns."""
    for match in REFERENCE.finditer(token):
        name, op = match.group(1), match.group(2) or ""
        if name and op.startswith(ASSIGNING):
            assigned.add(name)


def _unset_reference(token, assigned):
    """`(reference text, name)` for the first reference in TOKEN that is empty
    here and not assigned earlier, or None."""
    for match in REFERENCE.finditer(_without_substitutions(token)):
        name = match.group(1) or match.group(3)
        op = match.group(2) or ""
        if op.startswith(DEFAULTING) or op.startswith(STOPPING):
            continue
        if name in assigned or os.environ.get(name):
            continue
        return match.group(0), name
    return None


def _emptied(token, assigned):
    """TOKEN as bash would expand its unset references (to nothing)."""
    def sub(match):
        name = match.group(1) or match.group(3)
        op = match.group(2) or ""
        if op.startswith(DEFAULTING) or op.startswith(STOPPING):
            return match.group(0)
        if name in assigned or os.environ.get(name):
            return match.group(0)
        return ""
    return REFERENCE.sub(sub, token).replace(MASK, "$") or "''"


def _program(argv):
    """`(index of the program, override present)`, past leading assignments,
    keywords and wrappers."""
    i, override, after_wrapper = 0, False, False
    while i < len(argv):
        tok = argv[i]
        if ASSIGNMENT.match(tok):
            override = override or tok == OVERRIDE
            i += 1
            after_wrapper = False
            continue
        if tok in SHELL_KEYWORDS:
            i += 1
            after_wrapper = False
            continue
        if os.path.basename(tok) in COMMAND_WRAPPERS:
            i += 1
            after_wrapper = True
            continue
        if after_wrapper:
            window = argv[i:i + WRAPPER_ARG_WINDOW]
            hit = next((off for off, cand in enumerate(window)
                        if os.path.basename(cand) in PROGRAMS), None)
            i = i + hit if hit is not None else len(argv)
        break
    return i, override


def _record_assignments(argv, assigned):
    """Add the names ARGV assigns to ASSIGNED. True when ARGV sources or
    evaluates text, after which any name may be set."""
    for tok in argv:
        _defaults_assigned(tok, assigned)
    words = list(argv)
    while words and words[0] in SHELL_KEYWORDS - {"for"}:
        words = words[1:]
    if not words:
        return False
    if words[0] in ("for", "select"):
        if len(words) > 1 and NAME.match(words[1]):
            assigned.add(words[1])
        return False
    if all(ASSIGNMENT.match(tok) for tok in words):
        assigned.update(ASSIGNMENT.match(tok).group(1) for tok in words)
        return False
    lead = 0
    while lead < len(words) and ASSIGNMENT.match(words[lead]):
        lead += 1
    if lead >= len(words):
        return False
    program, rest = os.path.basename(words[lead]), words[lead + 1:]
    if program in SOURCING:
        return True
    if program in DECLARE_BUILTINS:
        assigned.update(m.group(1) for m in map(ASSIGNMENT.match, rest) if m)
    elif program in READ_BUILTINS:
        assigned.update(tok for tok in rest if NAME.match(tok))
    elif program == "printf":
        for k, tok in enumerate(rest[:-1]):
            if tok == "-v" and NAME.match(rest[k + 1]):
                assigned.add(rest[k + 1])
    return False


def _rm_targets(head):
    """The operands of a recursive `rm`, or [] when it is not recursive."""
    recursive, targets, end = False, [], False
    for tok in head[1:]:
        if end or tok == "-" or not tok.startswith("-"):
            targets.append(tok)
        elif tok == "--":
            end = True
        elif tok == "--recursive":
            recursive = True
        elif not tok.startswith("--") and ("r" in tok or "R" in tok):
            recursive = True
    return targets if recursive else []


def _find_targets(head):
    """The starting points of a deleting `find`, or [] when it deletes nothing."""
    rest = head[1:]
    deletes = "-delete" in rest or any(
        tok in FIND_EXEC and k + 1 < len(rest) and os.path.basename(rest[k + 1]) == "rm"
        for k, tok in enumerate(rest))
    if not deletes:
        return []
    starts, k = [], 0
    while k < len(rest) and rest[k] in FIND_LEADING_OPTIONS:
        k += 1
    for tok in rest[k:]:
        if tok.startswith(("-", "(", "!", ",")):
            break
        starts.append(tok)
    return starts


def _prepared(piece):
    """PIECE ready for `simple_commands`, with unexpanded `$` masked."""
    text = _heredoc_free(piece)
    text = re.sub(r"\\\r?\n", " ", text)
    return _mask(_comment_free(text))


def _hit(command):
    """`(segment, reference, name, target)` for the first refused delete."""
    assigned = set()
    for piece in shell_c_expansions(command):
        argvs = simple_commands(_prepared(piece))
        if argvs is None:
            continue
        for argv in argvs:
            lead, override = _program(argv)
            head = argv[lead:]
            if head and not override:
                program = os.path.basename(head[0])
                targets = (_rm_targets(head) if program == "rm"
                           else _find_targets(head) if program == "find" else [])
                for target in targets:
                    found = _unset_reference(target, assigned)
                    if found:
                        return " ".join(argv).replace(MASK, "$"), found[0], found[1], target
            if _record_assignments(argv, assigned):
                break
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"no-recursive-rm-unset-variable: unreadable hook input ({exc})",
              file=sys.stderr)
        return 0
    if shell_c_expansions is None or not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") not in ("Bash", "bash", "run_command",
                                        "execute_command", "terminal", "shell"):
        return 0
    inp = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or ""
    if not isinstance(command, str) or not command:
        return 0
    try:
        hit = _hit(command)
    except Exception as exc:  # a guard bug must not block every command
        print(f"no-recursive-rm-unset-variable: not evaluated ({exc})", file=sys.stderr)
        return 0
    if not hit:
        return 0
    segment, ref, name, target = hit
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": DENY.format(
            segment=segment, ref=ref, name=name, target=target.replace(MASK, "$"),
            empty=_emptied(target, set()), override=OVERRIDE),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
