#!/usr/bin/env python3
"""PreToolUse warning: pushing after running only SOME of the repo's checks.

## The failure this exists for

`scripts/run-local-validation.py` derives the check list from
`.github/workflows/validate.yml`, precisely so the list cannot be assembled
from memory. `memories/preferences.md` already says to take it from that
workflow "rather than from this bullet", and the script IS that derivation.

The rule is read at session start and broken at push time, which is why prose
does not reach it. The observed shape is not a session that skipped checking.
It is a session that checked diligently, several times, using whichever
checkers the FIRST round happened to need -- and then never widened the set.
Each later round re-runs that same subset, every run is green, and the green
means less each time because the diff has moved on to touch things the subset
does not cover.

Measured 2026-09-14/15 on ai-config#3629 and ai-config#3696, one session:

* Ten local rounds re-ran the test suite and `check-ascii-punctuation.py`.
  `check-python-escapes.py` had run ONCE, early, before the docstring that
  broke it existed. CI caught an invalid escape.
* After that was fixed and the lesson written down, the very next PR pushed a
  lead-in reading "Two forms are portable" above three bullets. CI caught it
  with `check-leadin-counts.py`, a checker the session had never run at all
  and did not know existed.

The second one is the argument for a hook rather than a better habit: the
session had just finished writing a memory entry about this exact miss.

## Why WARN and not block

The full sweep is slow -- minutes, not seconds -- and there are legitimate
pushes that should not wait for it: an empty claim commit, a one-character
fix to a file the sweep already covers, a branch whose CI runs the same checks
in parallel anyway. Blocking those would teach the operator to disable the
guard, which takes the real cases with it.

So this only ever adds a line, and it names the command to run.

## COMMAND POSITION, not substring

The first cut matched the script names anywhere in the command text, and both
directions of that were wrong (review finding, ai-config#3697):

* `grep -r "run-local-validation.py" memories/` set the "sweep already ran"
  flag and silenced the guard. Reading this very file did too, which is as
  self-defeating as a guard gets.
* `grep -rn "scripts/check-ascii-punctuation.py" README.md` counted as having
  RUN that checker, so the note asserted a checker had run when none had.

A script counts as invoked only when it sits in a command position: the
program token itself, or the first non-flag argument to an interpreter. That
is `_invoked_scripts`, and it is why `grep` naming a path is inert.

Push detection likewise delegates to `scripts/lib/shellcmd.py`'s
`git_subcommand`, which already models git's global-option grammar -- including
a long option taking a separate argument (`git --git-dir /path push`), which a
hand-rolled regex here missed. A second derivation of that grammar is exactly
the defect this hook warns about.

## Scope

Fires only when `run-local-validation.py` actually exists in the working
directory's repository. `scripts/check-*.py` is a common naming convention, so
without that gate any repo following it gets a nag pointing at a file it does
not have.

LIMITS
------
The derivation is credited SESSION-WIDE, not per repository. A transcript
record carries a command's text and not the directory it ran in -- only the
live `PreToolUse` payload has a `cwd` -- so a sweep run in one worktree
silences the guard for a push made from a different worktree of the same
repo, whose diff was never validated. That is the dangerous direction, and
this corpus's own multi-worktree workflow makes it reachable rather than
theoretical.

It is stated here rather than fixed because nothing in the transcript can
distinguish the two cases; closing it needs the sweep itself to leave a
marker naming the repository and commit it validated, which is a change to
`run-local-validation.py` rather than to this hook. Tracked as
ai-config#3698. The gap is pinned rather than left to be discovered: the
suite is a flat sequence of labelled `check()` calls rather than named test
functions, so grep its label fragment
`silences a push from ANOTHER repo`.

The residue in the OTHER direction is larger and safer: a genuine run behind
a wrapper this cannot see through -- `timeout 60 python3 <script>`,
`sudo -u me python3 <script>`, `make check`, `$PY <script>` -- is not
credited, so the warning fires when it need not have.

Fails OPEN on any trouble reading the payload or the transcript, printing
nothing. The one exception is a broken install: a `shellcmd` import failure
writes a line to STDERR saying no warning will be emitted, matching
`no-clobbering-push.py`, because a guard that has silently stopped guarding is
worse than a noisy one. Nothing is ever written to stdout except the warning
itself, so no failure path can block or alter a command.
"""
import json
import os
import sys

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib")
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import (simple_commands, git_subcommand, strip_env,
                          shell_c_expansions)
except Exception as _exc:  # broken install: degrade silently, never block
    print(f"warn-partial-validation-before-push: cannot load "
          f"scripts/lib/shellcmd.py ({_exc}); no warning will be emitted",
          file=sys.stderr)
    simple_commands = git_subcommand = strip_env = None
    shell_c_expansions = None

DERIVED = "run-local-validation.py"


# Tool names that carry a shell command, across harnesses.
SHELL_TOOLS = frozenset({
    "Bash", "bash", "PowerShell", "run_command", "execute_command",
    "terminal", "shell",
})

NOTE = (
    "This session ran {n} of the repository's own checkers by hand "
    "({names}) and has not run `scripts/{derived}`, which derives the full "
    "list from `.github/workflows/validate.yml`.\n"
    "A hand-picked subset stays fixed while the diff moves, so a green local "
    "run stops meaning what it meant when the subset was chosen. Two pushes "
    "on 2026-09-14/15 went red in CI for exactly this reason, the second one "
    "on a checker the session did not know existed.\n"
    "Run it before the push, or say why this push does not need it:\n\n"
    "    python3 scripts/{derived} --base origin/main\n"
)


def _basename(token):
    return os.path.basename(token.strip("'\"").replace("\\", "/"))


# Programs that RUN a script given as their first non-flag argument.
RUNNERS = frozenset({
    "python", "python3", "py", "python3.11", "python3.12", "python3.13",
    "uv", "uvx", "poetry", "pdm", "hatch", "pipenv", "rye", "pixi",
})

# Interpreter flags that mean "run this CODE or MODULE", not "run this file".
# `python3 -c scripts/check-x.py` evaluates that text as an expression and
# runs nothing.
# `-h`/`-V` belong here for the same reason: the interpreter prints and exits
# without ever reaching the file argument, so `python3 --version <script>`
# runs nothing (review finding, ai-config#3697).
NOT_A_FILE = frozenset({
    "-c", "--command", "-m", "--module",
    "-h", "--help", "-V", "--version",
})

# The same two flags in their ATTACHED spelling, which CPython accepts and
# which `python3 -mpip` uses in the wild. Exact-token matching missed it, so
# `python3 -munittest scripts/run-local-validation.py` credited the
# derivation and silenced the guard (review finding, ai-config#3697).
# A long option is unaffected: `--module`[:2] is `--`.
NOT_A_FILE_ATTACHED = frozenset({"-c", "-m"})

# A runner's own subcommand before the script: `uv run <script>`.
RUNNER_SUBCOMMANDS = frozenset({"run", "exec"})


def _is_tracked_script(name):
    """True for a checker or the derivation, by basename."""
    return name == DERIVED or (name.startswith("check-") and name.endswith(".py"))


def _script_after_runner(rest):
    """The tracked script this command RUNS, or None.

    `rest[0]` must itself be the runner or the script. That strictness is the
    whole of the fix, and it cost five review rounds to arrive at.

    Accepting a runner ANYWHERE earlier in the argv reads
    `grep python3 scripts/run-local-validation.py` as a run of the derivation
    --- an ordinary way to inspect a script's shebang --- which set the
    "already swept" flag and silenced the guard for the rest of the session.
    A Python file's text contains the word `python3` constantly, so that is
    not a rare shape (review finding, ai-config#3697).

    The cost is real and is the safe one: a genuine run behind a wrapper this
    cannot see through --- `timeout 60 python3 <script>`, `sudo -u me python3
    <script>`, `find ... -exec python3 <script> ;`, `make check`, `$PY
    <script>` --- is not credited, so the warning fires when it need not have.
    That spends a line. The alternative spent the guard.
    """
    if not rest:
        return None
    head = _basename(rest[0])
    if _is_tracked_script(head):
        return head  # a direct exec: ./scripts/check-x.py
    if head not in RUNNERS:
        return None
    for token in rest[1:]:
        if token in NOT_A_FILE or token[:2] in NOT_A_FILE_ATTACHED:
            return None  # runs code or a module, never this file
        if token.startswith("-") or token in RUNNER_SUBCOMMANDS:
            continue
        name = _basename(token)
        return name if _is_tracked_script(name) else None
    return None


def _invoked_scripts(command):
    """Basenames of the tracked scripts INVOKED by *command*.

    A path that is merely an argument to something else -- `grep`, a linter, a
    redirect, an editor -- is not an invocation, and neither is one named in a
    flag's value such as `--python=<path>`.
    """
    found = set()
    for line in shell_c_expansions(command):
        for argv in simple_commands(line):
            _env, rest = strip_env(argv)
            name = _script_after_runner(rest)
            if name:
                found.add(name)
    return found


def _is_push(command):
    for line in shell_c_expansions(command):
        for argv in simple_commands(line):
            parsed = git_subcommand(argv)
            if parsed and parsed[0] == "push":
                return True
    return False


def records(path):
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def _commands(record):
    """Yield every shell command string in one transcript record.

    Handles the Claude Code shape (`message.content` blocks of `tool_use`) and
    the Antigravity shape (`tool_calls`, whose arguments may arrive as a JSON
    string), matching `hooks/remind-ums-after-error.py`. CLAUDE.md's
    "Generalize instructions to every AI agent by default" applies: this hook
    branches on `ANTIGRAVITY_AGENT` below, so it must be able to read that
    harness's records.
    """
    calls = []

    blocks = (record.get("message") or {}).get("content") or record.get("content") or []
    if isinstance(blocks, list):
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                calls.append(b.get("input") or {})

    for tc in record.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        args = (tc.get("args") or tc.get("input")
                or (tc.get("function") or {}).get("arguments") or {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {"command": args}
        calls.append(args)

    for inp in calls:
        if not isinstance(inp, dict):
            continue
        for key in ("command", "CommandLine", "cmd", "script"):
            val = inp.get(key)
            if isinstance(val, str) and val.strip():
                yield val


def scan(path):
    """Return (checker_basenames, derived_seen)."""
    checkers = set()
    derived = False
    for rec in records(path):
        # A subagent's own commands are not this session's validation habit.
        if rec.get("isSidechain"):
            continue
        for cmd in _commands(rec):
            try:
                invoked = _invoked_scripts(cmd)
            except Exception:
                continue
            if DERIVED in invoked:
                derived = True
            for name in invoked:
                if name.startswith("check-") and name.endswith(".py"):
                    checkers.add(name)
    return checkers, derived


def _is_repo_root(path):
    """True for a normal checkout's root and for a bare repository's."""
    if os.path.exists(os.path.join(path, ".git")):
        return True
    return (os.path.isfile(os.path.join(path, "HEAD"))
            and os.path.isdir(os.path.join(path, "objects"))
            and os.path.isdir(os.path.join(path, "refs")))


def _repo_has_derivation(start):
    """True when `scripts/<DERIVED>` exists in the repository containing *start*.

    STOPS AT THE REPOSITORY BOUNDARY, which a bare ancestor walk does not. A
    nested clone -- a vendored dependency, a submodule, any repo checked out
    under a tree that happens to have the script -- would otherwise inherit
    its parent's answer and get a warning naming a script it does not have
    (review finding, ai-config#3697).

    A `.git` entry marks the boundary for a normal checkout, whether it is a
    directory or the file a worktree uses. A BARE repository has no such entry
    -- its root holds `HEAD` and `objects` directly -- so that shape is tested
    for too; a mirror or cache checked out inside the tracked tree is exactly
    the nesting this function exists to stop.
    """
    try:
        path = os.path.realpath(start)
    except Exception:
        return False
    seen = 0
    while seen < 40:
        if os.path.isfile(os.path.join(path, "scripts", DERIVED)):
            return True
        if _is_repo_root(path):
            return False  # repository root reached, and it lacks the script
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent
        seen += 1
    return False


def main() -> int:
    if simple_commands is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    # `SHELL_TOOLS` is the set flag-chained-push.py,
    # no-commit-chained-to-push.py and flag-unread-commit-citation.py accept,
    # PLUS `PowerShell`, which none of them carry. The addition is deliberate
    # -- this harness exposes a PowerShell tool and `CLAUDE.md` documents it --
    # and it is stated rather than folded into a claim of matching them, which
    # an earlier version of this comment made and which was false.
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    if tool and tool not in SHELL_TOOLS:
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = payload.get("toolInput")
    if not isinstance(tool_input, dict):
        return 0
    command = (
        tool_input.get("command")
        or tool_input.get("CommandLine")
        or tool_input.get("cmd")
        or tool_input.get("script")
    )
    if not isinstance(command, str) or not command.strip():
        return 0

    try:
        if not _is_push(command):
            return 0
    except Exception:
        return 0

    # Scope: only where the derivation this note names actually exists.
    #
    # WALKING UP is the point. Checking `cwd/scripts/<script>` alone silently
    # disabled the hook for any push issued from a subdirectory, which in this
    # corpus is most of them -- a session sitting in `hooks/` or `skills/x/`
    # got no warning at all (review finding, ai-config#3697).
    if not _repo_has_derivation(payload.get("cwd") or os.getcwd()):
        return 0

    path = payload.get("transcript_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    try:
        checkers, derived = scan(path)
    except Exception:
        return 0

    if derived or not checkers:
        return 0

    names = ", ".join(sorted(checkers)[:3])
    if len(checkers) > 3:
        names += ", ..."

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": NOTE.format(
                n=len(checkers), names=names, derived=DERIVED),
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Pushed after running {len(checkers)} checker(s) by hand and not "
            f"{DERIVED}, which derives the full list from validate.yml."
        )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
