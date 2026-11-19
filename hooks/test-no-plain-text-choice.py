#!/usr/bin/env python3
"""Tests for hooks/no-plain-text-choice.py (ai-config#5826).

Run: python3 hooks/test-no-plain-text-choice.py
"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT = os.path.join(HERE, "no-plain-text-choice.py")
spec = importlib.util.spec_from_file_location("hook", SCRIPT)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

POST = "mcp__hearthbot__post_message"

# (name, text, should_deny)
CASES = [
    ("start now or file", "Should I start it now or file an issue?", True),
    ("start now or file, second sentence", "Done with the fix. Do you want me to start now or file?", True),
    ("lettered list", "Which one?\n(a) Keep the cap\n(b) Remove the cap", True),
    ("numbered list", "Which do you prefer?\n1. Hook\n2. Memory", True),
    ("bulleted letters", "Pick one?\n- A) Hook\n- B) Memory", True),
    ("option labels", "Option A is a hook. Option B is a memory. Which do you want?", True),
    ("open question", "What should the hook be named?", False),
    ("list, no question", "Steps:\n1. Clone\n2. Edit", False),
    ("question, one option only", "Which file?\n1. hooks.json", False),
    ("fenced typed line", "Type this:\n```\nmwc lds 5 abc\n```\nOK?", False),
    ("empty", "", False),
]


def denied(text, tool=POST):
    os.environ.pop(hook.OVERRIDE, None)
    return hook.denial({"tool_name": tool, "tool_input": {"text": text}}) is not None


def main() -> int:
    bad = 0

    def check(name, ok):
        nonlocal bad
        bad += not ok
        print(("ok   " if ok else "FAIL ") + name)

    for name, text, want in CASES:
        check(name, denied(text) == want)
    check("request_decision ignored", not denied("Which one?\n(a) X\n(b) Y",
                                                  tool="mcp__hearthbot__request_decision"))
    check("message_thread ignored", not denied("Which one?\n(a) X\n(b) Y",
                                                tool="mcp__hearthbot__message_thread"))
    os.environ[hook.OVERRIDE] = "1"
    check("override clears it", hook.denial(
        {"tool_name": POST, "tool_input": {"text": "Now or file?"}}) is None)
    os.environ.pop(hook.OVERRIDE)
    r = subprocess.run([sys.executable, SCRIPT], input="not json", capture_output=True, text=True)
    check("bad stdin exits 0 silently", r.returncode == 0 and not r.stdout)
    payload = json.dumps({"tool_name": POST, "tool_input": {"text": "Start now or file?"}})
    r = subprocess.run([sys.executable, SCRIPT], input=payload, capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != hook.OVERRIDE})
    check("subprocess denies", '"permissionDecision": "deny"' in r.stdout)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
