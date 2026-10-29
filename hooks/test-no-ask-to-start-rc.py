#!/usr/bin/env python3
"""Tests for hooks/no-ask-to-start-rc.py.

Run: python3 hooks/test-no-ask-to-start-rc.py [hooks/no-ask-to-start-rc.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-ask-to-start-rc.py")
POST = "mcp__hearthbot__post_message"
RELAY = "mcp__hearthbot__message_thread"
COMMENT = "mcp__github__add_issue_comment"

# (name, tool, field, text, should_deny)
CASES = [
    ("please start RC", POST, "text", "Please start Remote Control on cf463-02 so I can run the dry run.", True),
    ("can you run claude remote-control", POST, "text", "Can you run `claude remote-control` in ~/Documents/claude-fetch?", True),
    ("you need to launch RC", POST, "text", "You'll need to launch RC on the XPS before I can continue.", True),
    ("need you to start", POST, "text", "I need you to start a Remote Control session on the Mac.", True),
    ("imperative", POST, "text", "Start Remote Control on cf463-02. Then reply here.", True),
    ("passive on your machine", POST, "text", "Remote Control needs to be started on your machine first.", True),
    ("from your terminal", POST, "text", "From your terminal, run claude remote-control in that folder.", True),
    ("message_thread", RELAY, "text", "Ezra needs to start Remote Control; please ask him.", False),
    ("message_thread direct ask", RELAY, "text", "Please start RC on the XPS and tell me.", True),
    ("github comment body", COMMENT, "body", "Could you start Remote Control on cf463-02 and rerun?", True),
    ("agent started it", POST, "text", "I started a Remote Control session on cf463-02 and the dry run passed.", False),
    ("agent will start", POST, "text", "I'll start Remote Control on the XPS now.", False),
    ("negated ask", POST, "text", "I won't ask you to start Remote Control; I do it myself.", False),
    ("no need", POST, "text", "No need to run Remote Control yourself; the thread starts it.", False),
    ("RC as other word", POST, "text", "Run the rc settings check on the file.", False),
    ("start unrelated", POST, "text", "Start the render and open the report.", False),
    ("rc in code", POST, "text", "Run rc.local after the build.", False),
    ("unrelated tool", "Bash", "text", "Please start Remote Control.", False),
    ("no text", POST, "text", None, False),
]


def run(tool, field, text):
    payload = {"tool_name": tool, "tool_input": {field: text} if text is not None else {}}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool, field, text, deny in CASES:
        rc, out = run(tool, field, text)
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
