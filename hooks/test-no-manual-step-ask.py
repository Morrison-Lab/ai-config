#!/usr/bin/env python3
"""Tests for hooks/no-manual-step-ask.py (ai-config#4698).

Run: python3 hooks/test-no-manual-step-ask.py [hooks/no-manual-step-ask.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-manual-step-ask.py")
POST = "mcp__hearthbot__post_message"

# (name, tool, text, should_deny)
CASES = [
    ("type go in RC session", POST, "Please type `go` in the Remote Control session to start.", True),
    ("say go to the session", POST, "Say go in the session on cf463-02 and it will run.", True),
    ("RC then type go", POST, "The RC session is waiting; type \"go\" there.", True),
    ("click merge button", POST, "Click the green Merge button on the PR.", True),
    ("press the merge button", POST, "Press the merge button when CI is green.", True),
    ("merge it yourself", POST, "You can merge them yourself once green.", True),
    ("plain mwc ask", POST, "Both are ready. Type `mwc` to merge them.", False),
    ("fresh session sentence", POST, "I started a fresh Remote Control session with the brief as its opening task.", False),
    ("go as an ordinary word", POST, "Let's go ahead and type the results into the table.", False),
    ("unrelated tool", "Bash", "Click the Merge button", False),
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
