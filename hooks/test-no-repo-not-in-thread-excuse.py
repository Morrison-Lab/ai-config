#!/usr/bin/env python3
"""Tests for hooks/no-repo-not-in-thread-excuse.py.

Run: python3 hooks/test-no-repo-not-in-thread-excuse.py
"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT = os.path.join(HERE, "no-repo-not-in-thread-excuse.py")
spec = importlib.util.spec_from_file_location("hook", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"
COORD = "mcp__hearthbot__message_coordinator"

# (name, tool, text, should_deny)
CASES = [
    ("the 2026-11-12 message", COORD,
     "ai-config isn't in this thread's repos, so could you route that as an issue?", True),
    ("one of", POST, "ai-config isn't one of this thread's repos.", True),
    ("session repo scope", POST, "I can't search mlr because it isn't in this session's repo scope.", True),
    ("curly apostrophe", POST, "mlr isn’t in this thread’s repositories.", True),
    ("not attached", POST, "The repo is not attached to this session.", True),
    ("outside scope", POST, "That repository is outside this session's scope.", True),
    ("not available in", POST, "psw is not available in this thread's repos.", True),
    ("is not part of", POST, "gha is not part of the session's repos, so I stopped.", True),
    ("tried and refused", POST,
     "add_repo refused ai-config, so it is not in this session's repos.", False),
    ("attached report", POST, "I attached ai-config to this thread and opened a PR.", False),
    ("no repo word", POST, "That file isn't in this thread.", False),
    ("unrelated not in", POST, "The bug is not in this repo's main branch.", False),
    ("other tool", "Bash", "ai-config isn't in this thread's repos.", False),
]


def denied(tool, text):
    os.environ.pop(hook.OVERRIDE, None)
    return hook.denial({"tool_name": tool, "tool_input": {"text": text}}) is not None


def main() -> int:
    failures = 0
    for name, tool, text, want in CASES:
        got = denied(tool, text)
        if got != want:
            failures += 1
            print(f"FAIL {name}: want deny={want}, got {got}")
    # Override
    os.environ[hook.OVERRIDE] = "1"
    if hook.denial({"tool_name": POST, "tool_input": {"text": CASES[0][2]}}) is not None:
        failures += 1
        print("FAIL override")
    os.environ.pop(hook.OVERRIDE, None)
    # End to end through stdin
    out = subprocess.run([sys.executable, SCRIPT], input=json.dumps(
        {"tool_name": COORD, "tool_input": {"text": CASES[0][2]}}),
        capture_output=True, text=True).stdout
    if '"deny"' not in out:
        failures += 1
        print("FAIL end-to-end deny")
    out = subprocess.run([sys.executable, SCRIPT], input="not json",
                         capture_output=True, text=True)
    if out.returncode != 0 or out.stdout:
        failures += 1
        print("FAIL fail-open")
    print(f"{len(CASES) + 3 - failures}/{len(CASES) + 3} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
