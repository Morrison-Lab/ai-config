#!/usr/bin/env python3
"""Tests for flag-argv-printing-process-listing.py.

Run: python3 hooks/test-flag-argv-printing-process-listing.py

The silent cases are as load-bearing as the firing ones: the remedy the
warning recommends (`pgrep -f`, `ps -o pid,comm`) must not itself draw the
warning, or the guard teaches nothing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                    "flag-argv-printing-process-listing.py")
FAILURES = []


def run(command, tool="Bash", env_extra=None):
    payload = {"tool_name": tool, "tool_input": {"command": command}}
    env = dict(os.environ)
    env.pop("ANTIGRAVITY_AGENT", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=30, env=env)
    if p.returncode != 0 or p.stderr.strip():
        FAILURES.append(f"{command!r}: rc={p.returncode} stderr={p.stderr!r}")
    return p.stdout.strip()


def check(command, want_fire, **kw):
    got = run(command, **kw)
    if bool(got) != want_fire:
        FAILURES.append(f"{command!r}: expected "
                        f"{'fire' if want_fire else 'silence'}, got "
                        f"{'fire' if got else 'silence'}")
        return None
    if got:
        out = json.loads(got)
        hso = out.get("hookSpecificOutput", {})
        if hso.get("hookEventName") != "PreToolUse" or not hso.get("additionalContext"):
            FAILURES.append(f"{command!r}: malformed output {out!r}")
        if "permissionDecision" in hso:
            FAILURES.append(f"{command!r}: a warn hook must not set permissionDecision")
        return out
    return None


# ------------------------------------------------------------- the real case
check('ps -eo pid,etime,command | grep -E "itpm2|curl" | grep -v grep', True)

# ------------------------------------------------------------------ fires
for cmd in [
    "ps aux",
    "ps aux | grep curl",
    "ps ax",
    "ps x",
    "ps -aux",
    "ps -ef",
    "ps -eF",
    "ps -f -p 123",
    "ps -o pid,args",
    "ps -opid,cmd",
    "ps -o pid= -o args=",
    "ps --format pid,command",
    "ps --format=pid,args",
    "ps -O args",
    "ps axce",
    "ps -C curl -o pid,args",
    "pgrep -af curl",
    "pgrep -a -f curl",
    "pgrep --list-full curl",
    "pstree -a",
    "pstree -ap 1",
    "top -bc -n1",
    "top -b -n 1 -c",
    "cat /proc/1234/cmdline",
    "tr '\\0' ' ' < /proc/$pid/cmdline",
    "cat /proc/self/environ",
    "sudo ps aux",
    "timeout 5 ps aux",
    "watch -n1 ps aux",
    "FOO=1 ps -ef",
    "bash -c 'ps aux | grep curl'",
    "sleep 1; ps -ef | head",
    "if true; then ps aux; fi",
]:
    check(cmd, True)

# ----------------------------------------------------------------- silent
for cmd in [
    "pgrep -f curl",
    "pgrep -fl curl",
    "pkill -f curl",
    "ps",
    "ps -e",
    "ps -p 123",
    "ps -C curl",
    "ps -eo pid,etime,comm",
    "ps -o pid,comm -p 123",
    "ps -ef -o pid,comm",
    "ps axc",
    "ps axo pid,comm",
    "top -b -n1",
    "pstree -p",
    'echo "ps aux"',
    'git commit -m "never run ps aux on a shared host"',
    'git commit -m "see /proc/1/cmdline"',
    "ls /proc/1",
    "grep -rn 'ps -ef' docs/",
]:
    check(cmd, False)

# --------------------------------------------------------- tool and payload
check("ps aux", False, tool="Read")
for bad in ["not-a-dict", 42, ["a"], None]:
    p = subprocess.run([sys.executable, HOOK],
                       input=json.dumps({"tool_name": "Bash", "tool_input": bad}),
                       capture_output=True, text=True, timeout=30)
    if p.returncode != 0 or p.stdout.strip() or p.stderr.strip():
        FAILURES.append(f"tool_input={bad!r}: expected silent rc=0, got "
                        f"rc={p.returncode} out={p.stdout!r} err={p.stderr!r}")
p = subprocess.run([sys.executable, HOOK], input="not json",
                   capture_output=True, text=True, timeout=30)
if p.returncode != 0 or p.stdout.strip():
    FAILURES.append("malformed stdin should fail open silently")

# ---------------------------------------------------------- output channels
out = check("ps aux", True)
if out is not None and "systemMessage" not in out:
    FAILURES.append("systemMessage missing outside Antigravity")
out = check("ps aux", True, env_extra={"ANTIGRAVITY_AGENT": "1"})
if out is not None and "systemMessage" in out:
    FAILURES.append("systemMessage must be omitted under Antigravity")

if FAILURES:
    print(f"{len(FAILURES)} failure(s):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("all flag-argv-printing-process-listing tests passed")
