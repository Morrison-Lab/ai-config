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
    # review round 1 (measured on procps-ng 4.0.4): -O preloads `command`
    "ps -O rss -e",
    "ps -e -O pid",
    "ps O rss",
    # BSD `e` prints environments even under an explicit -o format
    "ps axe -o pid,comm",
    "ps -e -o pid,comm e",
    "ps -e eo pid,comm",
    # wrappers that run the listing
    "pgrep -f curl | xargs ps -fp",
    "pgrep -f curl | xargs ps -o pid,args -p",
    "setsid ps aux",
    "flock /tmp/l ps aux",
    "sudo -u me ps aux",
    # command substitutions, quoted or not
    'out="$(ps -eo pid,args)"; echo "$out"',
    "printf '%s\\n' \"$(pgrep -af curl)\"",
    'echo "$(ps aux)"',
    "echo `ps aux`",
    "echo $(ps aux)",
    # remote and container listings print into the same transcript
    "ssh host ps aux",
    "ssh host 'ps aux'",
    "ssh -i key -p 22 host 'ps -ef | grep curl'",
    "docker exec c ps aux",
    "kubectl exec p -- ps aux",
    "docker exec c sh -c 'ps aux'",
    "busybox ps",
    "busybox ps -o pid,args",
    # per-thread /proc paths
    "cat /proc/1234/task/1235/cmdline",
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
    # review round 1: a letter inside an attached value is not an option
    "ps -Cx",
    "ps -Cxterm",
    "ps -pxx",
    "ps -Ux",
    # existence tests on /proc files print no contents
    "[ -e /proc/$pid/cmdline ] && echo alive",
    "test -r /proc/1/environ",
    "ls /proc/*/cmdline",
    "grep -l curl /proc/*/cmdline",
    # container CLIs outside `exec`, and single-quoted text, run nothing
    "docker ps -a",
    "docker ps --format '{{.ID}}'",
    "echo '$(ps aux)'",
    "busybox ps -o pid,comm",
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
