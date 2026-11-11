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
`merge_runs.py`, the script is run directly (`./merge_runs.py`), or inline
code imports `merge_runs`.  The deny names
`scripts/docx-merge-runs-field-safe.py`, which takes the same arguments and
keeps runs holding field markers apart, so a refusal is always satisfiable
in one retry: on a document with no field codes the wrapper does exactly
what the skill's script does.

The one reason to run the skill's script itself is the diagnostic recipe in
`memories/office-open-xml.md`, which runs it on a throwaway copy to see
whether it caused a scrambled document.  Prefix that command with
`ALLOW_FIELD_UNSAFE_MERGE_RUNS=1`.

Mentions pass: `grep merge_runs.py`, `cat .../merge_runs.py`, `md5sum`.

Known gap: a script file of your own that imports `merge_runs` is not read.

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
    from shellcmd import simple_commands
except Exception as _exc:
    print(f"no-field-unsafe-merge-runs: cannot load scripts/lib/shellcmd.py "
          f"({_exc}); not gating", file=sys.stderr)
    simple_commands = None

TARGET = "merge_runs.py"
SAFE = "scripts/docx-merge-runs-field-safe.py"
PYTHON = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?|py|pypy\d*)$")
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WRAPPERS = {"sudo", "env", "command", "exec", "nohup", "time", "nice", "timeout"}
ESCAPE = re.compile(r"(?:^|\s)ALLOW_FIELD_UNSAFE_MERGE_RUNS=1\s")
IMPORT = re.compile(r"\b(?:import\s+merge_runs|from\s+merge_runs\s+import)\b")


def _program(argv):
    """ARGV with assignments and simple wrappers peeled off the front."""
    rest, after_wrapper = list(argv), False
    while rest:
        tok = rest[0]
        if ENV_ASSIGNMENT.match(tok) or tok in WRAPPERS:
            after_wrapper = after_wrapper or tok in WRAPPERS
        elif not (after_wrapper and re.match(r"^(?:-|\d)", tok)):
            break
        rest = rest[1:]
    if rest and os.path.basename(rest[0]) == "uv" and rest[1:2] == ["run"]:
        rest = rest[2:]
    return rest


def runs_merge_runs(command):
    """The offending simple command, joined, or None."""
    if simple_commands is None or ESCAPE.search(command):
        return None
    for argv in simple_commands(command) or []:
        rest = _program(argv)
        if not rest:
            continue
        prog = os.path.basename(rest[0])
        if prog == TARGET:
            return " ".join(argv)
        if not PYTHON.match(prog):
            continue
        if any(os.path.basename(tok) == TARGET for tok in rest[1:]):
            return " ".join(argv)
        if any(IMPORT.search(tok) for tok in rest[1:]):
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
