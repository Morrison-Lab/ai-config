#!/usr/bin/env python3
"""Tests for hooks/no-stepwise-approval-ask.py (ai-config#4726).

Run: python3 hooks/test-no-stepwise-approval-ask.py [hooks/no-stepwise-approval-ask.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-stepwise-approval-ask.py")
POST = "mcp__hearthbot__post_message"

# (name, tool, text, should_deny)
CASES = [
    ("reply yes to re-upload", POST, "Reply `yes` to re-upload the corrected key.", True),
    ("say approve and I will replace", POST, "Say approve and I will replace the PDF in Canvas.", True),
    ("type okay to continue", POST, "Type okay to continue with the upload.", True),
    ("shall I re-upload", POST, "The key changed. Shall I re-upload it?", True),
    ("want me to replace", POST, "Do you want me to replace the posted file?", True),
    ("can I repost", POST, "Can I repost the announcement with the fix?", True),
    ("plain mwc ask", POST, "Type `mwc` to merge them.", False),
    ("replace a variable name", POST, "Should I replace this variable name with a clearer one?", False),
    ("replace deprecated calls", POST, "Do you want me to replace the deprecated function calls?", False),
    ("re-run tests", POST, "Should I re-run the test suite to confirm?", False),
    ("overwrite config", POST, "Can I overwrite the old config file with this one?", False),
    ("past tense report", POST, "I re-uploaded the corrected key and replaced the old file.", False),
    ("reply if you disagree", POST, "Reply if you disagree; otherwise it stays as posted.", False),
    ("one-line covering ask", POST, "Say `mwc` and I merge all three; nothing else is waiting on you.", False),
    ("yes as an ordinary word", POST, "Yes, the key was posted and the replacement is live.", False),
    ("unrelated tool", "Bash", "Shall I re-upload it?", False),
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
