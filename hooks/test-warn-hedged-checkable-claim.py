#!/usr/bin/env python3
"""Tests for hooks/warn-hedged-checkable-claim.py.

Run: python3 hooks/test-warn-hedged-checkable-claim.py [hooks/warn-hedged-checkable-claim.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "warn-hedged-checkable-claim.py")
REPLY = "mcp__hearthbot__reply"
COMMENT = "mcp__github__add_issue_comment"

# (name, tool, field, text, should_warn)
CASES = [
    ("probably + PR ref", REPLY, "text", "lds#477 is probably waiting on CI.", True),
    ("likely + merged", REPLY, "text", "It was likely merged already.", True),
    ("presumably + checks", REPLY, "text", "Presumably the checks passed.", True),
    ("i think + open", REPLY, "text", "I think the PR is still open.", True),
    ("should be + green", REPLY, "text", "CI should be green by now.", True),
    ("github comment body", COMMENT, "body", "Probably closed by #12.", True),
    ("post_message", "mcp__hearthbot__post_message", "text", "Likely conflicts on #5.", True),
    ("bare repo#N", REPLY, "text", "ai-config#2903 is probably fixed.", True),
    ("bare #N", REPLY, "text", "Probably #12 is fixed.", True),
    ("url fragment not a ref", REPLY, "text", "Probably see page.html#12 later.", False),
    ("update_issue_comment", "mcp__github__update_issue_comment", "body",
     "Probably merged in #3.", True),
    ("url ref", REPLY, "text",
     "https://github.com/o/r/pull/9 is probably done.", True),
    ("hedge, no checkable item", REPLY, "text", "This is probably the better design.", False),
    ("checkable, no hedge", REPLY, "text", "lds#477 is merged.", False),
    ("split across sentences", REPLY, "text",
     "This is probably the better design. lds#477 is merged.", False),
    ("should be able to", REPLY, "text", "Ezra should be able to merge #5.", False),
    ("inline code", REPLY, "text", "The flag `probably merged` is a label.", False),
    ("fenced code", REPLY, "text", "```\nprobably merged #4\n```\nDone.", False),
    ("other tool", "Bash", "text", "probably merged #4", False),
    ("no text", REPLY, "text", "", False),
]


def run(tool, field, text):
    event = {"tool_name": tool, "tool_input": {field: text}}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


def main():
    failures = 0
    for name, tool, field, text, should_warn in CASES:
        code, out = run(tool, field, text)
        warned = bool(out)
        context = ""
        if warned:
            context = json.loads(out)["hookSpecificOutput"].get("additionalContext", "")
        if code != 0 or warned != should_warn or (
                warned and "never say" not in context.lower()):
            failures += 1
            print(f"FAIL {name}: code={code} out={out!r}")
    for bad in ("", "not json", "[]", json.dumps({"tool_name": REPLY, "tool_input": []})):
        proc = subprocess.run([sys.executable, HOOK], input=bad,
                              capture_output=True, text=True)
        if proc.returncode != 0 or proc.stdout:
            failures += 1
            print(f"FAIL malformed input {bad!r}")
    print("ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
