#!/usr/bin/env python3
"""Test no-implicit-session-environment.py: create_session names its environment.

Run:  python3 hooks/test-no-implicit-session-environment.py hooks/no-implicit-session-environment.py
"""
import json
import subprocess
import sys

HOOK = sys.argv[1]
passes = failures = 0
TOOL = "mcp__claude-code-remote__create_session"


def run(payload):
    res = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                         capture_output=True, encoding="utf-8")
    out = json.loads(res.stdout) if res.stdout.strip() else {}
    return res.returncode, out


def decision(out):
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision")


def check(name, cond):
    global passes, failures
    passes += cond
    failures += (not cond)
    print(("PASS: " if cond else "FAIL: ") + name)


def call(tool_input, tool=TOOL):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}


# The measured case: no environment_id at all.
rc, out = run(call({"title": "Polish block A", "source_url": "https://github.com/Morrison-Lab/lds",
                    "prompt": "polish"}))
check("missing environment_id is denied", rc == 0 and decision(out) == "deny")
reason = (out.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")
check("the reason names list_environments and the issue",
      "list_environments" in reason and "ai-config#4819" in reason)

rc, out = run(call({"prompt": "x", "environment_id": ""}))
check("an empty environment_id is denied", decision(out) == "deny")

rc, out = run(call({"prompt": "x", "environment_id": "   "}))
check("a whitespace environment_id is denied", decision(out) == "deny")

rc, out = run(call({"prompt": "x", "environment_id": "env_01FsTeprQaVKBbsBxkWtNWMR"}))
check("an explicit environment_id passes silently", rc == 0 and out == {})

rc, out = run(call({"prompt": "x"}, tool="create_session"))
check("an unprefixed create_session tool name is still guarded", decision(out) == "deny")

rc, out = run(call({"prompt": "x"}, tool="mcp__claude-code-remote__create_trigger"))
check("a different tool is ignored", rc == 0 and out == {})

rc, out = run(call({"prompt": "x"}, tool="Bash"))
check("Bash is ignored", rc == 0 and out == {})

res = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, encoding="utf-8")
check("unparseable input exits 0 with no output", res.returncode == 0 and not res.stdout.strip())

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
