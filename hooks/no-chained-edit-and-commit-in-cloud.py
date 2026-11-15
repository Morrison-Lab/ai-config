#!/usr/bin/env python3
"""PreToolUse (Bash): in a cloud session, don't chain an in-place edit with a commit.

ai-config#5688, from #5687 (Ezra, 2026-11-15: "avoid asking for approvals
when there's another idiomatic path forward"). A cloud Bash command that
chains `sed -i` edits with `git commit` raises an approval prompt that the
separate steps would not raise. Only when CLAUDE_CODE_REMOTE=true, this hook
DENIES a command whose simple commands, at command positions (also inside
`bash -c`), include both:

- an in-place edit: `sed` or `perl` with an `-i` flag (`-i`, `-i.bak`,
  `-Ei`, `-pi`, `--in-place`), or a `>`, `>>`, `&>` or `>|` redirect into a
  file outside `/dev/`, `/tmp/` and a `scratchpad/` directory; and
- `git commit` (after git's global options such as `-C dir` or `-c k=v`).

A redirect into a temp file (`> /tmp/msg && git commit -F /tmp/msg`) passes,
and so does either half on its own. The deny message points to the Edit tool
for the edit and a separate Bash call for the commit. It is a deny, not a
warning, because a warning is read past (ai-config#4741). Where the chain is
needed, prefix any simple command with the assignment
`ALLOW_CHAINED_EDIT_COMMIT=1` and say why. Fails open on parse trouble;
silent outside cloud sessions.
"""
import json
import os
import re
import sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                    "scripts", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
try:
    from shellcmd import simple_commands, strip_env
except ImportError as exc:
    print(f"no-chained-edit-and-commit-in-cloud: cannot load scripts/lib/shellcmd.py ({exc}); "
          "not gating", file=sys.stderr)
    simple_commands = strip_env = None

OVERRIDE = "ALLOW_CHAINED_EDIT_COMMIT=1"
SHELLS = {"bash", "sh", "zsh", "dash"}
REDIRECTS = {">", ">>", "&>", "&>>", ">|"}
# A short-flag cluster holding `i`, such as `-i`, `-Ei`, `-pi` or `-i.bak`.
INPLACE_SHORT = re.compile(r"^-[A-Za-z]*i")
# Redirect targets that are not files a commit would pick up.
SCRATCH_TARGET = re.compile(r"^(?:/dev/|/tmp/|\$TMPDIR/|\$\{TMPDIR\}/)|(?:^|/)scratchpad/")
# git's global options that take a separate value.
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}


def _inplace_edit(rest):
    """A short description of the in-place edit `rest` makes, or None."""
    prog = os.path.basename(rest[0])
    if prog in ("sed", "perl"):
        for arg in rest[1:]:
            if arg == "--":
                break
            if arg.startswith("--in-place") or (not arg.startswith("--") and INPLACE_SHORT.match(arg)):
                return f"{prog} {arg}"
    for op, target in zip(rest, rest[1:]):
        if op in REDIRECTS and not SCRATCH_TARGET.search(target):
            return f"{op} {target}"
    return None


def _is_commit(rest):
    """Whether `rest` (program first) runs `git commit`."""
    if os.path.basename(rest[0]) != "git":
        return False
    args = rest[1:]
    while args and args[0].startswith("-"):
        args = args[2:] if args[0] in GIT_VALUE_OPTS else args[1:]
    return bool(args) and args[0] == "commit"


def scan(command):
    """`(edit, commit_seen, overridden)` over the simple commands of `command`."""
    edit, commit, overridden = None, False, False
    for argv in simple_commands(command) or []:
        env, rest = strip_env(argv)
        if OVERRIDE in env:
            overridden = True
        if not rest:
            continue
        prog = os.path.basename(rest[0])
        if prog in SHELLS and "-c" in rest[1:-1]:
            inner = scan(rest[rest.index("-c", 1) + 1])
            edit = edit or inner[0]
            commit = commit or inner[1]
            overridden = overridden or inner[2]
            continue
        edit = edit or _inplace_edit(rest)
        commit = commit or _is_commit(rest)
    return edit, commit, overridden


def main() -> int:
    if os.environ.get("CLAUDE_CODE_REMOTE", "").lower() != "true" or simple_commands is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    inp = payload.get("tool_input")
    command = inp.get("command") if isinstance(inp, dict) else None
    if not isinstance(command, str):
        return 0
    try:
        edit, commit, overridden = scan(command)
    except Exception as exc:
        print(f"no-chained-edit-and-commit-in-cloud: {type(exc).__name__}: {exc}; not gating",
              file=sys.stderr)
        return 0
    if not (edit and commit) or overridden:
        return 0
    reason = (
        f"[hook: no-chained-edit-and-commit-in-cloud] This cloud Bash command chains an in-place "
        f"edit (`{edit}`) with `git commit`, which raises an approval prompt that separate steps "
        "would not (Ezra, 2026-11-15: \"avoid asking for approvals when there's another idiomatic "
        "path forward\", ai-config#5687). Make the edit with the Edit or Write tool, then run "
        "`git commit` as its own short Bash command. Only if the chain is needed, prefix "
        f"`{OVERRIDE}` and say why."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
