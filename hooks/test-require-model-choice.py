#!/usr/bin/env python3
"""Test require-model-choice.py.

Run:  python3 hooks/test-require-model-choice.py hooks/require-model-choice.py
"""
import json
import subprocess
import sys

HOOK = sys.argv[1]
fails = 0


def verdict(tool, inp):
    r = subprocess.run([sys.executable, HOOK], input=json.dumps({"tool_name": tool, "tool_input": inp}),
                       capture_output=True, encoding="utf-8")
    assert r.returncode == 0
    out = json.loads(r.stdout) if r.stdout.strip() else {}
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision")


def check(name, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(("PASS: " if ok else "FAIL: ") + name)


check("Agent without model denied", verdict("Agent", {"prompt": "x"}), "deny")
check("Agent blank model denied", verdict("Agent", {"prompt": "x", "model": " "}), "deny")
check("Task without model denied", verdict("Task", {"prompt": "x"}), "deny")
check("Agent with sonnet silent", verdict("Agent", {"prompt": "x", "model": "sonnet"}), None)
check("start_thread without model denied", verdict("mcp__hearthbot__start_thread", {"prompt": "x"}), "deny")
check("start_thread with model silent", verdict("mcp__hearthbot__start_thread", {"prompt": "x", "model": "opus"}), None)
check("start_thread with Model-fit line silent",
      verdict("mcp__hearthbot__start_thread", {"prompt": "do x\nModel-fit: sonnet -- bounded edit"}), None)
check("create_thread is not a start tool", verdict("mcp__hearthbot__create_thread", {"prompt": "x"}), None)
check("create_session without model denied", verdict("mcp__claude-code-remote__create_session", {"prompt": "x"}), "deny")
check("message_thread without reason denied", verdict("mcp__hearthbot__message_thread", {"text": "do more"}), "deny")
check("message_thread with reason silent",
      verdict("mcp__hearthbot__message_thread", {"text": "do more\nWhy-not-new-thread: same PR, context needed"}), None)
check("No-new-work line silent",
      verdict("mcp__hearthbot__message_thread", {"text": "pin sha abc\nNo-new-work: head for the runner"}), None)
check("empty Why-not-new-thread denied",
      verdict("mcp__hearthbot__message_thread", {"text": "Why-not-new-thread:"}), "deny")
check("Bash ignored", verdict("Bash", {"command": "ls"}), None)
check("non-dict input silent", verdict("Agent", "oops"), None)
r = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, encoding="utf-8")
check("malformed stdin exits 0 quietly", (r.returncode, r.stdout.strip()), (0, ""))
print("failures:", fails)
sys.exit(1 if fails else 0)
