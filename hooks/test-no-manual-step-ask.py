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
    ("reply then go ahead, session later", POST, "Reply if you disagree; otherwise we can go ahead and the session will start.", False),
    ("say we go, RC mentioned", POST, "You said we should go with the RC plan, so I started a session.", False),
    ("use the merge queue", POST, "Use the merge queue; the button is disabled by policy.", False),
    ("append to settings", POST, "Append this string to the autoMode.allow list in ~/.claude/settings.json.", True),
    ("paste into file", POST, "Please paste this into the file and save it.", True),
    ("you can add to config", POST, "You can add the entry to your config.json by hand.", True),
    ("script command form", POST, "Run `python3 ~/Documents/claude-fetch/add-automode-allow.py`; it adds the entry to settings.json and keeps a backup.", False),
    ("script handed over beside a could-add clause", POST, "You could add an entry to the allowlist in settings.json, but run `python3 ~/scripts/add-entry.py` instead; it does it.", False),
    ("copy as a code instruction", POST, "Copy the array into a new variable before mutating it, to avoid aliasing in the config.", False),
    ("bare add to settings.json", POST, "Add the key to settings.json.", True),
    ("bare put into config", POST, "Put this entry into your config.", True),
    ("bare add line to home settings", POST, "Add the following line to ~/.claude/settings.json.", True),
    ("agent did the edit", POST, "I added the entry to the file myself and the probe passes.", False),
    ("agent will add", POST, "I'll add the rule to the file in the next commit.", False),
    ("unrelated tool","Bash", "Click the Merge button", False),
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
