#!/usr/bin/env python3
"""PreToolUse guard: deny `find` starting at `/` or bare drive roots on Windows.

WHY THIS GUARD EXISTS (ai-config#3897)
-------------------------------------
In Git Bash / MSYS on Windows, `/` mounts every drive (`C:` on `/c`, `D:` on
`/d`, etc.). When a subagent or session runs `find / ...` or `find /c/ ...`
looking for a single binary or script, find walks the entire machine and triggers
Windows Defender scans across every file it touches.

When the agent finishes or gives up on the task, the `find.exe` process is
orphaned and continues running in the background. Measured on 2026-09-22/23 on a
developer machine during an autonomous coordinator session:
  - `find.exe / -iname *self-review* ...` ran orphaned for ~12 hours.
  - With three concurrent suites, the machine sat at 5,331 pages/sec and
    53 of 62 GB committed memory.
  - Another orphaned `find.exe / -maxdepth 6 -iname *check-new-line-breaks*` ran
    for 7.5 hours.
  - Killing the runaway processes dropped paging from 38,317 pages/sec to
    406 pages/sec and CPU from 41% to 11%.

Telling subagents in their prompt brief "never run find /" failed to stop them:
two runaway searches ran even with the prohibition explicitly in the prompt.
A mechanical check at the PreToolUse boundary prevents the command before it
can spawn.

WHAT IT MATCHES
---------------
A Bash tool invocation in a Windows/MSYS environment running `find` or `find.exe`
whose starting path is:
  - the whole-system root: `/`, `//`, `\\`, `\\\\`
  - a bare drive letter root in Unix style: `/c`, `/c/`, `/d`, `/d/`, `//c/`, etc.
  - a cygdrive mount root: `/cygdrive/c`, `/cygdrive/c/`, etc.
  - a Windows drive letter root: `C:`, `C:/`, `C:\\`, `d:`, `d:/`, `d:\\`, etc.

WHAT IT ALLOWS
--------------
  - Any search starting at a bounded directory: `find . ...`, `find src/ ...`,
    `find /c/Users/dougm/repo ...`, `find "C:\\Users\\dougm\\repo" ...`,
    `find ~/.claude ...`, `find /tmp ...`
  - Non-Windows environments (Linux, macOS) where `/` does not mount other drives,
    unless simulated via SIMULATE_WINDOWS=1.
  - Explicit bypass via `ALLOW_FIND_ROOT=1` (env var or command prefix).
  - Programs other than `find`.

FAILS OPEN
----------
Unparseable stdin, non-dict payload, or inability to import `shellcmd` returns 0
without blocking.
"""
from __future__ import annotations

import json
import os
import platform
import re
import sys

# Prohibited root patterns:
# 1. Whole-system root: / or // or \ or \\
ROOT_PATH_RE = re.compile(r"\A[/\\]{1,2}\Z")

# 2. Bare drive root in Unix/MSYS notation: /c, /c/, //c, //c/, \c, \c\
MSYS_DRIVE_ROOT_RE = re.compile(r"\A[/\\]{1,2}[a-zA-Z][/\\]?\Z")

# 3. Bare drive root in cygdrive notation: /cygdrive/c, /cygdrive/c/
CYGDRIVE_ROOT_RE = re.compile(r"\A/(?:cygdrive|proc)/[a-zA-Z][/\\]?\Z")

# 4. Windows native drive root: C:, C:/, C:\, d:, d:/, d:\
WIN_DRIVE_ROOT_RE = re.compile(r"\A[a-zA-Z]:[/\\]?\Z")

# Windows find.exe text search flags (e.g. find /I "needle" file.txt)
WIN_FIND_FLAGS = {"/i", "/v", "/n", "/off", "/offline"}

# Leading environment assignment or override regex
ENV_ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
OVERRIDE_CMD_RE = re.compile(
    r"\A[ \t]*(?:export[ \t]+)?ALLOW_FIND_ROOT=1(?:[ \t]*[;&|]|\Z)"
)

COMMAND_WRAPPERS = {
    "env", "command", "nohup", "time", "exec", "builtin",
    "sudo", "timeout", "stdbuf", "nice", "ionice", "doas",
}

SHELL_KEYWORDS = {
    "!", "{", "}", "(", ")", "if", "then", "elif", "else", "fi",
    "while", "until", "do", "done", "for", "case", "esac",
}

# Global options accepted by GNU find before starting paths
FIND_GLOBAL_OPTS_WITH_ARG = {"-D", "-O"}
FIND_GLOBAL_OPTS_NO_ARG = {"-H", "-L", "-P"}

try:
    _LIB = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "scripts", "lib"
    )
    if _LIB not in sys.path:
        sys.path.insert(0, _LIB)
    from shellcmd import simple_commands
except Exception as _exc:
    print(f"no-find-root-on-windows: cannot load scripts/lib/shellcmd.py ({_exc}); not evaluating",
          file=sys.stderr)
    simple_commands = None


def is_windows_env() -> bool:
    """True if running in a Windows or MSYS/Cygwin environment."""
    sim = os.environ.get("SIMULATE_WINDOWS")
    if sim == "1":
        return True
    if sim == "0":
        return False
    if sys.platform in ("win32", "cygwin", "msys") or os.name == "nt":
        return True
    if bool(os.environ.get("MSYSTEM")):
        return True
    return False


def is_prohibited_root(path: str, has_gnu_predicates: bool = False) -> bool:
    """True if path specifies the whole filesystem root or a bare drive root."""
    p = path.strip()
    if not p:
        return False
    if p.lower() in WIN_FIND_FLAGS:
        return False
    if ROOT_PATH_RE.match(p):
        return True
    if CYGDRIVE_ROOT_RE.match(p):
        return True
    if WIN_DRIVE_ROOT_RE.match(p):
        return True
    if MSYS_DRIVE_ROOT_RE.match(p):
        # Disambiguate /c in Windows find (find /c "needle") vs GNU find (find /c -type f or find /c)
        if p.lower() in ("/c", "\\c") and not p.endswith(("/", "\\")) and not has_gnu_predicates:
            return False
        return True
    return False


def is_find_executable(prog: str) -> bool:
    """True if program name is find or find.exe."""
    base = os.path.basename(prog).lower()
    return base in ("find", "find.exe")


def extract_find_paths(argv: list[str]) -> list[str]:
    """Extract starting path arguments from a find command argv list."""
    paths: list[str] = []
    i = 0
    n = len(argv)
    while i < n:
        tok = argv[i]
        if tok in FIND_GLOBAL_OPTS_NO_ARG:
            i += 1
            continue
        if tok in FIND_GLOBAL_OPTS_WITH_ARG:
            i += 2
            continue
        if tok.startswith("-O") and len(tok) > 2 and tok[2:].isdigit():
            i += 1
            continue
        # Expression predicates, operators, and test options begin with '-', '(', ')', '!'
        if tok.startswith("-") or tok in ("(", ")", "!"):
            break
        # Otherwise, this token is a starting path
        paths.append(tok)
        i += 1
    return paths


def evaluate_command(command: str, is_windows: bool | None = None) -> tuple[str, str] | None:
    """Evaluate a shell command string.

    Returns (prohibited_path, matched_command_str) if prohibited, else None.
    """
    if is_windows is None:
        is_windows = is_windows_env()
    if not is_windows:
        return None

    if os.environ.get("ALLOW_FIND_ROOT") == "1":
        return None

    if OVERRIDE_CMD_RE.match(command):
        return None

    if simple_commands is None:
        return None

    cmds = simple_commands(command)
    if cmds is None:
        return None

    for argv in cmds:
        if not argv:
            continue

        cmd = list(argv)
        # Strip leading environment variable assignments
        has_override = False
        while cmd and ENV_ASSIGNMENT.match(cmd[0]):
            if cmd[0] == "ALLOW_FIND_ROOT=1":
                has_override = True
            cmd.pop(0)

        if has_override or not cmd:
            continue

        # Strip command wrappers and shell keywords (e.g. '{', '(', 'do')
        while cmd and (cmd[0] in COMMAND_WRAPPERS or cmd[0] in SHELL_KEYWORDS or cmd[0].startswith("-")):
            if cmd[0] in COMMAND_WRAPPERS or cmd[0] in SHELL_KEYWORDS:
                cmd.pop(0)
                while cmd and cmd[0].startswith("-"):
                    opt = cmd.pop(0)
                    if opt in ("-u", "-k", "-s", "--signal", "--kill-after") and cmd:
                        cmd.pop(0)
            else:
                break

        if not cmd:
            continue

        if not is_find_executable(cmd[0]):
            continue

        # Check if the command contains GNU find predicates starting with '-'
        has_gnu_predicates = any(tok.startswith("-") for tok in cmd[1:])

        paths = extract_find_paths(cmd[1:])
        for p in paths:
            if is_prohibited_root(p, has_gnu_predicates=has_gnu_predicates):
                return p, " ".join(argv)

    return None


def format_deny_reason(path: str, command_str: str) -> str:
    host = platform.node().split(".")[0] or "Windows host"
    return (
        f"Blocked: `find` starting at `{path}` on Windows ({host}).\n\n"
        f"    {command_str}\n\n"
        "In Git Bash / MSYS on Windows, `/` mounts every drive (`C:` on `/c`,\n"
        "`D:` on `/d`, etc.), so a whole-filesystem search walks every drive on\n"
        "the machine and triggers Windows Defender scans across millions of files.\n"
        "When an agent turns to another task, orphaned find processes continue\n"
        "running in the background, consuming CPU and saturating memory paging\n"
        "(measured on 2026-09-22/23: runaway `find` processes ran orphaned for\n"
        "4-12 hours, driving 53 GB committed memory and 38,000 pages/sec).\n\n"
        "Use a bounded, cheap alternative instead:\n"
        "  - Search a named root: the current repo (`find . ...`), `~/.claude`, or the plugin cache\n"
        "  - Locate a binary: `command -v <name>` or `where.exe <name>`\n"
        "  - Locate a forge script: `gh api` or git inspection\n\n"
        "To bypass this check for a deliberate whole-system search, set ALLOW_FIND_ROOT=1:\n"
        f"    ALLOW_FIND_ROOT=1 find {path} ...\n"
    )


def _read_payload() -> tuple[dict, bool]:
    """Parse payload from sys.argv (--dry-run / --simulate) or sys.stdin."""
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
        print(f"no-find-root-on-windows: unreadable hook input ({exc})",
              file=sys.stderr)
        return {}, is_dry_run


def main() -> int:
    payload, is_dry_run = _read_payload()
    if not payload:
        return 0

    tool_name = (payload.get("tool_name") or "").lower()
    if tool_name not in ("bash", "run_command", "execute_command", "terminal", "shell"):
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    inp = payload.get("tool_input")
    inp = inp if isinstance(inp, dict) else {}
    command = str(inp.get("command") or inp.get("CommandLine") or inp.get("cmd") or inp.get("script") or "")

    result = evaluate_command(command)
    if result is None:
        if is_dry_run:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse"}}))
        return 0

    path, cmd_str = result
    reason = format_deny_reason(path, cmd_str)

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }
    if not os.environ.get("ANTIGRAVITY_AGENT"):
        out["systemMessage"] = (
            f"Blocked `find` starting at `{path}` on Windows. Use a bounded root "
            "(e.g. `find .`), `command -v`, or `where.exe`, or set ALLOW_FIND_ROOT=1."
        )

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
