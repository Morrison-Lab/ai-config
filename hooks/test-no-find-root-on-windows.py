#!/usr/bin/env python3
"""Tests for no-find-root-on-windows.py (ai-config#3897).

Exercises both unit-level evaluation and end-to-end hook subprocess invocation.
Verifies positive denials (whole system / bare drive roots in Windows/MSYS),
negatives (bounded searches, non-find tools, quotes, non-Windows), and overrides.

Run:
    python3 hooks/test-no-find-root-on-windows.py [hooks/no-find-root-on-windows.py]
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

# Locate subject hook
if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    HOOK_PATH = os.path.realpath(sys.argv[1])
else:
    HOOK_PATH = os.path.realpath(os.path.join(
        os.path.dirname(__file__), "no-find-root-on-windows.py"
    ))

spec = importlib.util.spec_from_file_location("hook", HOOK_PATH)
if spec is None or spec.loader is None:
    sys.exit(f"FATAL: could not load {HOOK_PATH}")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

failures: list[str] = []
ran = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global ran
    ran += 1
    if ok:
        print(f"PASS: {label}")
    else:
        msg = f"FAIL: {label}"
        if detail:
            msg += f" - {detail}"
        print(msg)
        failures.append(msg)


def run_hook_subproc(payload: dict, env: dict | None = None) -> tuple[int, dict]:
    child_env = os.environ.copy()
    # Strip Antigravity agent marker so systemMessage behaves standardly
    child_env.pop("ANTIGRAVITY_AGENT", None)
    if env:
        child_env.update(env)

    proc = subprocess.run(
        [sys.executable, HOOK_PATH],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=child_env,
        timeout=10,
    )
    if not proc.stdout.strip():
        return proc.returncode, {}
    try:
        return proc.returncode, json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return proc.returncode, {"_raw": proc.stdout}


def test_positives() -> None:
    """Commands that MUST be denied on Windows."""
    denied_cases = [
        ("reported incident 1: find / -iname *self-review*",
         "find / -iname *self-review*"),
        ("reported incident 2: find.exe / -maxdepth 6 -iname *check-new-line-breaks*",
         "find.exe / -maxdepth 6 -iname *check-new-line-breaks*"),
        ("reported incident 3: find.exe / -maxdepth 6 -iname *Godot_v4.7*console*",
         "find.exe / -maxdepth 6 -iname *Godot_v4.7*console*"),
        ("bare find / without args", "find /"),
        ("bare find /c without args", "find /c"),
        ("bare find /c/ without args", "find /c/"),
        ("bare find /C without args", "find /C"),
        ("bare find C: without args", "find C:"),
        ("bare find C:/ without args", "find C:/"),
        (r"bare find 'C:\' without args", "find 'C:\\'"),
        ("find with multiple paths including /c", "find /home /c"),
        ("find /c with unquoted path argument", "find /c dir1"),
        ("find with multiple paths including /", "find . / -name foo"),
        ("double slash root", "find // -name foo"),
        ("bare backslash root (single quoted)", "find '\\' -name foo"),
        ("bare backslash root (double quoted)", 'find "\\\\" -name foo'),
        ("bare double backslash root", "find '//' -name foo"),
        ("bare /c drive", "find /c -type f"),
        ("bare /c/ drive with trailing slash", "find /c/ -name foo"),
        ("bare /d/ drive", "find /d/ -type f"),
        ("uppercase /C/ drive", "find /C/ -name bar"),
        ("cygdrive /cygdrive/c/", "find /cygdrive/c/ -name baz"),
        ("cygdrive /cygdrive/c without trailing slash", "find /cygdrive/c -type f"),
        ("bare C: drive", "find C: -name foo"),
        ("bare C:/ drive", "find C:/ -name foo"),
        (r"bare C:\ drive (single quoted)", "find 'C:\\' -name foo"),
        (r"bare C:\ drive (double quoted)", 'find "C:\\\\" -name foo'),
        (r"bare d:\ drive (single quoted)", "find 'd:\\' -name foo"),
        ("global flag -L before /", "find -L / -name bar"),
        ("global flag -H before /c", "find -H /c -name bar"),
        ("global flag -P before /", "find -P / -name bar"),
        ("global flag -O3 before /", "find -O3 / -name bar"),
        ("global flag -D stat before /", "find -D stat / -name bar"),
        ("full path /usr/bin/find /", "/usr/bin/find / -name foo"),
        ("wrapped with sudo", "sudo find / -name foo"),
        ("wrapped with time", "time find /c/ -name foo"),
        ("wrapped with nohup", "nohup find / -name foo &"),
        ("chained command: cd /repo && find / -name foo", "cd /repo && find / -name foo"),
        ("pipeline command: find / -name foo | grep bar", "find / -name foo | grep bar"),
        ("subshell grouping: ( find / -name foo )", "( find / -name foo )"),
        ("compound statement: { find / -name foo; }", "{ find / -name foo; }"),
    ]

    for label, cmd in denied_cases:
        res = hook.evaluate_command(cmd, is_windows=True)
        check(f"positives: {label}", res is not None, f"got None for {cmd!r}")


def test_negatives() -> None:
    """Commands that MUST be allowed on Windows."""
    allowed_cases = [
        ("current directory .", "find . -name foo"),
        ("relative path ./src", "find ./src -type f"),
        ("bounded MSYS path /c/Users/dougm/repo", "find /c/Users/dougm/repo -name foo"),
        ("bounded Windows path C:/Users/dougm/repo", "find C:/Users/dougm/repo -name foo"),
        (r"bounded Windows path C:\Users\dougm\repo", r"find C:\Users\dougm\repo -name foo"),
        ("home directory ~/.claude", "find ~/.claude -name '*.json'"),
        ("temp directory /tmp", "find /tmp -name '*.log'"),
        ("usr bin directory /usr/bin", "find /usr/bin -name git"),
        ("default current dir (no path specified)", "find -name foo"),
        ("find with -maxdepth but default dir", "find -maxdepth 2 -name foo"),
        ("echo quoting find /", 'echo "find / -name foo"'),
        ("git commit message mentioning find /", 'git commit -m "deny find / in git bash"'),
        ("python command mentioning find /", "python -c \"import os; print('find /')\""),
        ("grep command on root", "grep -rn 'find' /repo"),
        ("ls command on root", "ls /"),
        ("cd command to root", "cd /"),
        ("windows find string searcher", 'find "needle" haystack.txt'),
        ("windows find.exe string searcher with flag", 'find /I "needle" haystack.txt'),
        ("windows find.exe /c count flag", 'find /c "needle" file.txt'),
        ("windows find.exe /C uppercase count flag", 'find /C "needle" file.txt'),
        ("windows find.exe combined /i /c flags", 'find /i /c "needle" file.txt'),
        ("windows find.exe combined /v /c flags", 'find /v /c "needle" file.txt'),
        ("windows find.exe single quoted needle", "find /c 'needle' file.txt"),
        ("windows find.exe /c stdin search", 'find /c "needle"'),
    ]

    for label, cmd in allowed_cases:
        res = hook.evaluate_command(cmd, is_windows=True)
        check(f"negatives: {label}", res is None, f"unexpectedly blocked: {res!r}")


def test_overrides() -> None:
    """ALLOW_FIND_ROOT=1 clears the denial."""
    # 1. Command-prefixed env assignment
    cmd1 = "ALLOW_FIND_ROOT=1 find / -name foo"
    check("override: prefixed ALLOW_FIND_ROOT=1",
          hook.evaluate_command(cmd1, is_windows=True) is None)

    # 2. Leading export assignment
    cmd2 = "export ALLOW_FIND_ROOT=1 && find / -name foo"
    check("override: leading export ALLOW_FIND_ROOT=1",
          hook.evaluate_command(cmd2, is_windows=True) is None)

    # 3. Leading plain assignment
    cmd3 = "ALLOW_FIND_ROOT=1 && find / -name foo"
    check("override: leading plain assignment",
          hook.evaluate_command(cmd3, is_windows=True) is None)

    # 4. OS environment variable
    old_val = os.environ.get("ALLOW_FIND_ROOT")
    try:
        os.environ["ALLOW_FIND_ROOT"] = "1"
        check("override: os.environ[ALLOW_FIND_ROOT]=1",
              hook.evaluate_command("find / -name foo", is_windows=True) is None)
    finally:
        if old_val is None:
            os.environ.pop("ALLOW_FIND_ROOT", None)
        else:
            os.environ["ALLOW_FIND_ROOT"] = old_val


def test_platform_gating() -> None:
    """Non-Windows environments are not blocked unless simulated."""
    # When is_windows=False, find / is permitted
    check("platform: Linux/macOS allows find /",
          hook.evaluate_command("find / -name foo", is_windows=False) is None)

    # When SIMULATE_WINDOWS=0, hook evaluates as non-Windows
    old_sim = os.environ.get("SIMULATE_WINDOWS")
    try:
        os.environ["SIMULATE_WINDOWS"] = "0"
        check("platform: SIMULATE_WINDOWS=0 allows find /",
              hook.evaluate_command("find / -name foo") is None)

        os.environ["SIMULATE_WINDOWS"] = "1"
        check("platform: SIMULATE_WINDOWS=1 blocks find /",
              hook.evaluate_command("find / -name foo") is not None)
    finally:
        if old_sim is None:
            os.environ.pop("SIMULATE_WINDOWS", None)
        else:
            os.environ["SIMULATE_WINDOWS"] = old_sim


def test_subproc_end_to_end() -> None:
    """End-to-end JSON protocol execution via subprocess."""
    # Denied case
    payload_deny = {
        "tool_name": "Bash",
        "tool_input": {"command": "find / -iname *self-review*"}
    }
    rc, out = run_hook_subproc(payload_deny, env={"SIMULATE_WINDOWS": "1"})
    check("subproc: exit code is 0 on denial", rc == 0)
    hook_out = out.get("hookSpecificOutput") or {}
    check("subproc: permissionDecision is deny",
          hook_out.get("permissionDecision") == "deny")
    reason = hook_out.get("permissionDecisionReason", "")
    check("subproc: reason cites find / and alternatives",
          "Blocked: `find` starting at `/`" in reason and "command -v" in reason)
    check("subproc: systemMessage emitted",
          "Blocked `find` starting at `/` on Windows." in out.get("systemMessage", ""))

    # Allowed case (bounded search)
    payload_allow = {
        "tool_name": "Bash",
        "tool_input": {"command": "find . -name foo"}
    }
    rc, out = run_hook_subproc(payload_allow, env={"SIMULATE_WINDOWS": "1"})
    check("subproc: allowed command exits 0 with empty stdout", rc == 0 and out == {})

    # Tool other than Bash (e.g. Read)
    payload_read = {
        "tool_name": "Read",
        "tool_input": {"path": "/"}
    }
    rc, out = run_hook_subproc(payload_read, env={"SIMULATE_WINDOWS": "1"})
    check("subproc: non-Bash tool exits 0 with empty stdout", rc == 0 and out == {})


def main() -> int:
    print(f"Testing {HOOK_PATH}...")
    test_positives()
    test_negatives()
    test_overrides()
    test_platform_gating()
    test_subproc_end_to_end()

    print(f"\n{ran} cases ran, {len(failures)} failures.")
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
