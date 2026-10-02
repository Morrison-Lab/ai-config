#!/usr/bin/env python3
"""Tests for hooks/remind-encode-user-correction.py (ai-config#4208)."""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "remind-encode-user-correction.py")

FIRES = [
    # The two messages that motivated the hook, verbatim.
    "it's so frustrating when I have to tell you to do things that feel "
    "obvious, and hwen I have to repeat msyelf between sessions or projects",
    "even now, you're still interpreting my instructions too narrowly",
    "I already told you to put the tables at the end",
    "how many times do I have to say this",
    "you forgot the attribution footer again",
    "I shouldn't have to remind you to check the render",
]
SILENT = [
    "please render the manuscript again",
    "always use Pacific time in recaps",
    "what is the status of the sankey issue?",
    "run the tests one more time",
    "",
]


def run(stdin):
    return subprocess.run([sys.executable, HOOK], input=stdin,
                          capture_output=True, text=True, timeout=30)


failures = 0
for text in FIRES:
    proc = run(json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": text}))
    if proc.returncode != 0 or "remind-encode-user-correction" not in proc.stdout:
        print(f"FAIL: did not fire on {text!r}: {proc.stdout!r} {proc.stderr!r}")
        failures += 1
    elif "Morrison-Lab/ai-config" not in proc.stdout:
        print(f"FAIL: reminder does not name ai-config for {text!r}")
        failures += 1
for text in SILENT:
    proc = run(json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": text}))
    if proc.returncode != 0 or proc.stdout:
        print(f"FAIL: fired on {text!r}: {proc.stdout!r}")
        failures += 1
for raw in ("not json", json.dumps([1, 2]), json.dumps({"prompt": 3})):
    proc = run(raw)
    if proc.returncode != 0 or proc.stdout:
        print(f"FAIL: malformed payload {raw!r} -> {proc.returncode} {proc.stdout!r}")
        failures += 1

total = len(FIRES) + len(SILENT) + 3
print(f"{total - failures}/{total} passed")
sys.exit(1 if failures else 0)
