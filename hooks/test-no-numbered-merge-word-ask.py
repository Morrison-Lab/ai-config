#!/usr/bin/env python3
"""Tests for hooks/no-numbered-merge-word-ask.py (ai-config#4698).

Run: python3 hooks/test-no-numbered-merge-word-ask.py [hooks/no-numbered-merge-word-ask.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-numbered-merge-word-ask.py")
POST = "mcp__hearthbot__post_message"

# (name, tool, text, should_deny)
CASES = [
    ("mwc number in code", POST, "Type `mwc 4699` here to merge.", True),
    ("mwc hash number", POST, "Say mwc #4699 when ready.", True),
    ("mwc owner repo ref", POST, "Reply `mwc Morrison-Lab/gha#1178`.", True),
    ("slash mwc number", POST, "Send /mwc 12 please.", True),
    ("mwc for PR", POST, "Type mwc for PR 1178.", True),
    ("one per PR", POST, "Type `mwc 4699` and `mwc 1178`.", True),
    ("bare mwc", POST, "Both are ready. Type `mwc` to merge them.", False),
    ("mwc then a link", POST, "Type mwc to merge [PR 4699](https://github.com/o/r/pull/4699).", False),
    ("number elsewhere", POST, "Type mwc. There are 2 ready PRs.", False),
    ("unrelated tool", "Bash", "mwc 4699", False),
    ("no text", POST, None, False),
]


def run(tool, text):
    payload = {"tool_name": tool, "tool_input": {"text": text} if text is not None else {}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool, text, deny in CASES:
        rc, out = run(tool, text)
        denied = '"permissionDecision": "deny"' in out
        ok = rc == 0 and denied == deny
        print(("  ok      " if ok else "  FAIL    ") + name)
        fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
