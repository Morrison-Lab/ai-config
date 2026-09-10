#!/usr/bin/env python3
"""PreToolUse guard: a blanket `git worktree remove --force` fallback.

## The mistake this catches

`skills/clean-worktrees/SKILL.md` step 5 is explicit: `git worktree remove`
"refuses on a dirty tree -- a safety net; do NOT blindly --force." The
refusal is the signal that a worktree was misclassified, and the prescribed
response is to re-inspect, not to retry with `--force`.

A blanket fallback defeats that signal by construction: a command of the
shape

    git worktree remove "$p" || git worktree remove --force "$p"

(or the loop form, forcing every iteration regardless of why the plain
removal failed) never reads *why* the first attempt refused before
discarding whatever made it refuse. Self-hit during a `clean-git` session on
2026-09-10: this exact fallback was written for a batch removal, and
`hooks/no-mistake-without-a-hook.py` is what flagged writing it as a mistake
worth mechanizing -- the auto-mode permission classifier denied the command
before it ran, which is the only reason nothing was lost.

## Why this warns rather than blocks

The skill documents one legitimate single-shot `--force`: a worktree whose
tree is genuinely clean (`git -C <path> status --short` empty) but that
contains a submodule, where `git worktree remove` refuses with `fatal:
working trees containing submodules cannot be moved or removed` -- a
different refusal, triggered by the submodule's presence alone, not by dirty
state. That case occurred later in the same 2026-09-10 session and the
force there was correct. This hook cannot tell a submodule-only refusal from
a dirty-tree refusal from the command text alone (the refusal reason is only
known at runtime, after the plain attempt), so it can never safely deny --
it only ever adds context naming the fallback and the exception.

## Scope

Fires when a Bash command's tokens (heredoc bodies and comments stripped,
same preprocessing `scripts/lib/shellcmd.py` applies before splitting) show:

  - a `git worktree remove` invocation carrying `--force` or `-f`, AND
  - either (a) a *plain* `git worktree remove` (no force) elsewhere in the
    same command, connected through a `||` token -- the fallback shape --
    or (b) a loop keyword (`for`/`while`/`until`) opening a segment in the
    same command -- the forced-every-iteration shape.

Matched on the tokenized argv (via `shellcmd.simple_commands` and
`git_subcommand`), not on raw text, so a command merely *quoting* or
documenting the pattern (a commit message, a heredoc writing this file)
does not trip it. Fails OPEN on any parse trouble.
"""
import json
import os
import re
import shlex
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (
        git_subcommand, simple_commands,
        _comment_free, _heredoc_free,
    )
except Exception as _exc:  # broken install; fail open and say so
    print(f"warn-blanket-worktree-force-remove: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); not evaluating",
          file=sys.stderr)
    git_subcommand = simple_commands = None
    _comment_free = _heredoc_free = None

_LOOP_KEYWORDS = {"for", "while", "until"}


def _raw_tokens(command):
    """Tokenize COMMAND (heredoc/comment stripped) keeping operator tokens.

    `shellcmd.simple_commands` drops `||`/`&&`/`;` once it has used them to
    split -- exactly the information this hook needs to see a `||` fallback.
    So this reimplements only the preprocessing-then-tokenize half of
    `simple_commands_with_scope`, stopping short of the split, and reuses
    the library's own heredoc/comment stripping rather than a second
    implementation of it.
    """
    cmd = _heredoc_free(command)
    cmd = re.sub(r"\\\r?\n", " ", cmd)
    cmd = _comment_free(cmd)
    cmd = cmd.replace("\n", ";")
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def _is_worktree_remove(argv):
    """Forced-ness of one simple-command ARGV, or `None` if not a `git
    worktree remove` invocation at all."""
    sub = git_subcommand(argv)
    if sub is None:
        return None
    subcommand, rest, _env = sub
    if subcommand != "worktree" or not rest or rest[0] != "remove":
        return None
    forced = "--force" in rest[1:] or "-f" in rest[1:]
    return forced


def find_offense(command):
    """`(has_forced, has_bare, has_pipe, has_loop)` for COMMAND, or `None`
    on a parse failure (caller reads that as fail-open)."""
    if simple_commands is None:
        return None
    cmds = simple_commands(command)
    if cmds is None:
        return None
    tokens = _raw_tokens(command)
    if tokens is None:
        return None

    has_forced = False
    has_bare = False
    for argv in cmds:
        forced = _is_worktree_remove(argv)
        if forced is None:
            continue
        if forced:
            has_forced = True
        else:
            has_bare = True

    has_pipe = "||" in tokens
    has_loop = any(
        argv and argv[0] in _LOOP_KEYWORDS for argv in cmds
    )
    return has_forced, has_bare, has_pipe, has_loop


NOTE = (
    "This command force-removes a git worktree as part of a {shape}:\n\n"
    "`skills/clean-worktrees/SKILL.md` step 5 is explicit that a `git "
    "worktree remove` refusal is a safety net -- do NOT blindly `--force` "
    "it. A refusal means the worktree was likely misclassified (dirty "
    "tree, unpushed work); re-inspect with `git -C <path> status --short` "
    "before forcing, rather than retrying blind.\n\n"
    "The one case where a single-shot `--force` is correct: a worktree "
    "whose tree is genuinely CLEAN but that contains a submodule, where "
    "removal refuses with `fatal: working trees containing submodules "
    "cannot be moved or removed` -- a different refusal, triggered by the "
    "submodule's presence alone. If that is what this command is doing, "
    "disregard this warning."
)


def _read_payload():
    args = sys.argv[1:]
    is_dry_run = "--dry-run" in args or "--simulate" in args
    if is_dry_run:
        positional = [a for a in args if not a.startswith("-")]
        if positional:
            raw_cmd = positional[0].strip()
            if raw_cmd.startswith("{") and raw_cmd.endswith("}"):
                try:
                    return json.loads(raw_cmd), True
                except Exception:
                    pass
            return {"tool_name": "Bash", "tool_input": {"command": raw_cmd}}, True
    try:
        payload = json.load(sys.stdin)
        return (payload if isinstance(payload, dict) else {}), is_dry_run
    except Exception as exc:
        print(f"warn-blanket-worktree-force-remove: unreadable hook input "
              f"({exc})", file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    if not isinstance(payload, dict) or payload.get("tool_name") not in (
        "Bash", "bash", "run_command", "execute_command", "terminal", "shell",
    ):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0
    command = (
        tool_input.get("command")
        or tool_input.get("CommandLine")
        or tool_input.get("cmd")
        or tool_input.get("script")
    )
    if not isinstance(command, str) or not command.strip():
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    try:
        result = find_offense(command)
    except Exception as exc:  # fail open on any parse trouble
        print(f"warn-blanket-worktree-force-remove: could not parse command "
              f"({exc})", file=sys.stderr)
        return 0

    if result is None:
        return 0
    has_forced, has_bare, has_pipe, has_loop = result

    shape = None
    if has_forced and has_bare and has_pipe:
        shape = "`||` fallback (plain removal, forced on failure)"
    elif has_forced and has_loop:
        shape = "loop (forced every iteration)"
    if shape is None:
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(shape=shape),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            "Blanket `git worktree remove --force` fallback detected "
            f"({shape}). Step 5 says do NOT blindly --force a refusal -- "
            "re-inspect first, unless this is the documented "
            "submodule-on-a-clean-tree exception."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
