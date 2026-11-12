#!/usr/bin/env python3
r"""PreToolUse guard: refuse a recursive delete through a variable this shell never set.

Each Bash call starts a fresh shell, so `rm -rf "$D/"` after a `D=` in an
earlier call runs on `/` (anthropics/claude-code#75859). CC Safety Net passes
that at its standard level (ai-config#5476, part of #5317).

DENIES a recursive `rm`, or a `find` with `-delete` or `-exec rm`, when a
target uses `$D` and D is empty here (the Bash call inherits this environment)
and not assigned earlier in the command. `D=/x rm ...` does not assign: bash
expands the arguments first. `${D:-x}` and `${D:?}` pass. Not read: positional
parameters, `${!D}`, `xargs rm`, function bodies, whether an assignment runs,
and anything after `source`, `.` or `eval`. Escape hatch: a leading
`ALLOW_RM_UNSET_VARIABLE=1`, with the reason in the reply. Fails open.
"""
import json
import os
import re
import sys

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__))), "scripts", "lib"))
    from shellcmd import (COMMAND_WRAPPERS, SHELL_KEYWORDS, WRAPPER_ARG_WINDOW,
                          _comment_free, _heredoc_free, shell_c_expansions,
                          simple_commands)
except Exception as _exc:  # broken install: say so and pass
    print(f"no-recursive-rm-unset-variable: not evaluating ({_exc})", file=sys.stderr)
    shell_c_expansions = None

OVERRIDE = "ALLOW_RM_UNSET_VARIABLE=1"
ASSIGNMENT = re.compile(r"\A([A-Za-z_][A-Za-z0-9_]*)\+?=")
RECURSIVE = re.compile(r"\A(--recursive|-[^-]*[rR].*)\Z")
REFERENCE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)([^}]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
SUBSTITUTION = re.compile(r"\$\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)|`[^`]*`")
KEEPS_VALUE = (":-", "-", ":=", "=", ":?", "?")  # a default, or bash stops first
ASSIGNING = (":=", "=")
MASK = chr(0xE000)  # a `$` bash does not expand (single-quoted or escaped)
DECLARE = {"export", "local", "declare", "readonly", "typeset"}
READERS = {"read", "mapfile", "readarray", "getopts"}
SOURCING = {"source", ".", "eval"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}

DENY = ("Blocked: `{segment}` deletes through `{ref}`, unset in this shell: a variable set "
        "in an earlier Bash call is empty here, so `{target}` loses it (anthropics/claude-code"
        "#75859, ai-config#5476). Assign `{name}` in this command, write `${{{name}:?}}`, or "
        "write the literal path. If it is meant to be empty, prefix the delete with "
        "`{override}` and say why in your reply.")


def _mask(text):
    """TEXT with each `$` bash would not expand replaced by MASK."""
    out, single, double, i = [], False, False, 0
    while i < len(text):
        ch = text[i]
        if single:
            single = ch != "'"
        elif ch == "\\" and i + 1 < len(text):
            out.append(ch + (MASK if text[i + 1] == "$" else text[i + 1]))
            i += 2
            continue
        elif ch == "'" and not double:
            single = True
        elif ch == '"':
            double = not double
        out.append(MASK if single and ch == "$" else ch)
        i += 1
    return "".join(out)


def _unset_reference(token, assigned):
    """`(reference, name)` for the first reference in TOKEN, outside a command
    substitution, that is empty here."""
    for match in REFERENCE.finditer(SUBSTITUTION.sub("", token)):
        name, op = match.group(1) or match.group(3), match.group(2) or ""
        if not op.startswith(KEEPS_VALUE) and name not in assigned and not os.environ.get(name):
            return match.group(0), name
    return None


def _program(argv):
    """`(index of the program, override present)`, past assignments and wrappers."""
    i, override, after_wrapper = 0, False, False
    while i < len(argv):
        tok = argv[i]
        if ASSIGNMENT.match(tok) or tok in SHELL_KEYWORDS:
            override = override or tok == OVERRIDE
            after_wrapper = False
        elif os.path.basename(tok) in COMMAND_WRAPPERS:
            after_wrapper = True
        else:
            if after_wrapper:
                hit = next((k for k, cand in enumerate(argv[i:i + WRAPPER_ARG_WINDOW])
                            if os.path.basename(cand) in ("rm", "find")), None)
                i = len(argv) if hit is None else i + hit
            break
        i += 1
    return i, override


def _record_assignments(argv, assigned):
    """Add the names ARGV assigns; True when ARGV sources or evaluates text."""
    for tok in argv:
        for match in REFERENCE.finditer(tok):
            if match.group(1) and (match.group(2) or "").startswith(ASSIGNING):
                assigned.add(match.group(1))
    words = list(argv)
    while words and words[0] in SHELL_KEYWORDS - {"for"}:
        words = words[1:]
    if words[:1] in (["for"], ["select"]):
        assigned.update(words[1:2])
        return False
    lead = next((k for k, tok in enumerate(words) if not ASSIGNMENT.match(tok)), len(words))
    if lead == len(words):
        assigned.update(ASSIGNMENT.match(tok).group(1) for tok in words)
        return False
    program, rest = os.path.basename(words[lead]), words[lead + 1:]
    if program in DECLARE:
        assigned.update(m.group(1) for m in map(ASSIGNMENT.match, rest) if m)
    elif program in READERS:
        assigned.update(tok for tok in rest if tok.isidentifier())
    elif program == "printf":
        assigned.update(b for a, b in zip(rest, rest[1:]) if a == "-v")
    return program in SOURCING


def _targets(head):
    """The operands of a recursive `rm`, or the starting points of a deleting `find`."""
    program, rest = os.path.basename(head[0]), head[1:]
    if program == "rm":
        end = rest.index("--") if "--" in rest else len(rest)
        options = [tok for tok in rest[:end] if tok.startswith("-") and tok != "-"]
        recursive = any(RECURSIVE.match(tok) for tok in options)
        operands = [tok for tok in rest[:end] if tok not in options] + rest[end + 1:]
        return operands if recursive else []
    if program != "find" or "-delete" not in rest and not any(
            a in FIND_EXEC and os.path.basename(b) == "rm" for a, b in zip(rest, rest[1:])):
        return []
    starts = []
    for tok in rest:
        if tok in ("-H", "-L", "-P") and not starts:
            continue
        if tok.startswith(("-", "(", "!", ",")):
            break
        starts.append(tok)
    return starts


def _hit(command):
    """`(segment, reference, name, target)` for the first refused delete, or None."""
    assigned = set()
    for piece in shell_c_expansions(command):
        text = re.sub(r"\\\r?\n", " ", _heredoc_free(piece))
        argvs = simple_commands(_mask(_comment_free(text)))
        for argv in argvs or []:
            lead, override = _program(argv)
            if argv[lead:] and not override:
                for target in _targets(argv[lead:]):
                    found = _unset_reference(target, assigned)
                    if found:
                        return (" ".join(argv).replace(MASK, "$"), *found,
                                target.replace(MASK, "$"))
            if _record_assignments(argv, assigned):
                break
    return None


def main() -> int:
    try:  # unreadable input, or a guard bug, must not block every command
        payload = json.load(sys.stdin)
        inp = payload.get("tool_input") or {}
        command = inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or ""
        hit = (shell_c_expansions and isinstance(command, str) and payload.get("tool_name")
               in ("Bash", "bash", "run_command", "execute_command", "terminal", "shell")
               and _hit(command))
    except Exception as exc:
        print(f"no-recursive-rm-unset-variable: not evaluated ({exc})", file=sys.stderr)
        return 0
    if hit:
        segment, ref, name, target = hit
        reason = DENY.format(segment=segment, ref=ref, name=name, target=target,
                             override=OVERRIDE)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
