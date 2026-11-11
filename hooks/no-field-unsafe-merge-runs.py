#!/usr/bin/env python3
"""PreToolUse guard: run the docx skill's merge_runs.py only through the field-safe wrapper.

The `docx` skill lists `merge_runs.py` in its standard edit recipe, and the
script merges a field code's `begin`, `instrText`, `separate`, result and
`end` runs into one run.  A Zotero, Mendeley or EndNote citation, a
cross-reference, a table of contents or a HYPERLINK field then disappears or
moves, and the damage looks like the agent's own edit (ai-config#2918;
measured in `memories/office-open-xml.md`).  The memory's "Don't run
`merge_runs.py` reflexively" was advice, and the skill's recipe keeps
prompting the reflex.

## What it REFUSES

A Bash command in which a Python interpreter (`python`, `python3`,
`python3.12`, `py`, `uv run`) runs a script whose basename is
`merge_runs.py` (its first positional argument), runs the module
`merge_runs` with `-m`, or reads code that imports `merge_runs` from `-c` or
from stdin; or the script is run directly (`./merge_runs.py`).  Leading
assignments, wrappers (`sudo -u x`, `timeout 60`, `xargs`), shell keywords
(`do`, `then`, `{`) and a shell's `-c` string are looked through.  The deny names
`scripts/docx-merge-runs-field-safe.py`, which takes the same arguments and
keeps runs holding field markers apart, so a refusal is always satisfiable
in one retry: on a document with no field codes the wrapper does exactly
what the skill's script does.

The one reason to run the skill's script itself is the diagnostic recipe in
`memories/office-open-xml.md`, which runs it on a throwaway copy to see
whether it caused a scrambled document.  Put
`ALLOW_FIELD_UNSAFE_MERGE_RUNS=1` among the leading assignments of that
simple command; anywhere else (an argument, a comment, another command) it
exempts nothing.

Mentions pass: `grep merge_runs.py`, `cat .../merge_runs.py`, `md5sum`, and
`merge_runs.py` as a later argument (`python3 -m pytest merge_runs.py`).

Known gaps: a script file of your own that imports `merge_runs` is not read,
and neither is a copy of the skill's script under another name.
If `scripts/lib/shellcmd.py` cannot load, the hook says so on stderr and
gates nothing, as the other shellcmd-based hooks do.

Run with `--dry-run '<command>'` to see the verdict without acting.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
try:
    _LIB = os.path.join(os.path.dirname(_HERE), "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import simple_commands, shell_c_expansions
except Exception as _exc:
    print(f"no-field-unsafe-merge-runs: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not gating", file=sys.stderr)
    simple_commands = shell_c_expansions = None

TARGET = "merge_runs.py"
SAFE = "scripts/docx-merge-runs-field-safe.py"
PYTHON = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?|py|pypy\d*)$")
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WRAPPERS = {"sudo", "doas", "env", "command", "exec", "nohup", "time", "nice",
            "ionice", "stdbuf", "timeout", "xargs"}
KEYWORDS = {"!", "{", "(", "if", "then", "elif", "else", "while", "until", "do"}
LOOKAHEAD = 4
ESCAPE = "ALLOW_FIELD_UNSAFE_MERGE_RUNS=1"
USES = re.compile(r"\bimport\b[^\n;]*\bmerge_runs\b|\bfrom\s+merge_runs\s+import\b"
                  r"|import_module\(\s*['\"]merge_runs['\"]")


def _runs_something(tok):
    name = os.path.basename(tok)
    return bool(PYTHON.match(name)) or name in (TARGET, "uv")


def _program(argv):
    """(leading assignments, ARGV from its program token on)."""
    rest, env = list(argv), []
    while rest:
        tok = rest[0]
        if ENV_ASSIGNMENT.match(tok):
            env.append(tok)
        elif tok in WRAPPERS:
            window = rest[1:1 + LOOKAHEAD]
            hit = next((i for i, t in enumerate(window, 1) if _runs_something(t)), 1)
            rest = rest[hit:]
            continue
        elif tok not in KEYWORDS:
            break
        rest = rest[1:]
    if rest and os.path.basename(rest[0]) == "uv" and rest[1:2] == ["run"]:
        rest = rest[2:]
    return env, rest


def _python_runs_it(args, command):
    """True when an interpreter given ARGS runs or imports merge_runs."""
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in ("-W", "-X", "-Q"):
            i += 2
            continue
        if tok.startswith("-") and not tok.startswith("--") and len(tok) > 1:
            flags = tok[1:]
            pos = min((flags.find(f) for f in "cm" if f in flags), default=-1)
            if pos >= 0:
                value = flags[pos + 1:] or (args[i + 1] if i + 1 < len(args) else "")
                if flags[pos] == "m":
                    return value == "merge_runs"
                return bool(USES.search(value))
            i += 1
            continue
        if tok.startswith("--"):
            i += 1
            continue
        if tok == "-":
            break
        return os.path.basename(tok) == TARGET
    return bool(USES.search(command))  # code read from stdin, e.g. a heredoc


def runs_merge_runs(command):
    """The offending simple command, joined, or None."""
    if simple_commands is None:
        return None
    for piece in shell_c_expansions(command):
        for argv in simple_commands(piece) or []:
            env, rest = _program(argv)
            if not rest or ESCAPE in env:
                continue
            prog = os.path.basename(rest[0])
            if prog == TARGET or (PYTHON.match(prog) and _python_runs_it(rest[1:], piece)):
                return " ".join(argv)
    return None


def decide(payload):
    if payload.get("tool_name") != "Bash":
        return None
    cmd = (payload.get("tool_input") or {}).get("command")
    hit = runs_merge_runs(cmd) if isinstance(cmd, str) else None
    if not hit:
        return None
    return (
        "The docx skill's merge_runs.py merges a field code's runs into one, "
        "which deletes or moves Zotero/Mendeley/EndNote citations, "
        "cross-references, TOC entries and HYPERLINK fields (ai-config#2918; "
        "memories/office-open-xml.md).\n\n"
        f"    This call: {hit}\n\n"
        f"Run python3 {os.path.join(os.path.dirname(_HERE), SAFE)} "
        "with the same arguments instead: it is the skill's own "
        "script with runs holding field markers kept apart. Only to "
        "diagnose a scrambled document on a throwaway copy, prefix the "
        "command with ALLOW_FIELD_UNSAFE_MERGE_RUNS=1.")


def main():
    args = sys.argv[1:]
    if "--dry-run" in args:
        positional = [a for a in args if a != "--dry-run"]
        payload = {"tool_name": "Bash",
                   "tool_input": {"command": positional[0] if positional else ""}}
    else:
        try:
            payload = json.load(sys.stdin)
        except Exception as exc:
            print(f"no-field-unsafe-merge-runs: unreadable hook input ({exc})",
                  file=sys.stderr)
            return 0
    text = decide(payload if isinstance(payload, dict) else {})
    if text:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": text}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
