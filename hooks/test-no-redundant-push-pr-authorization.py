#!/usr/bin/env python3
"""Test the routine-push/PR authorization guard.

Run: python3 hooks/test-no-redundant-push-pr-authorization.py \\
  hooks/no-redundant-push-pr-authorization.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]
TOOL = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "input": {"command": "git status --short"}}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": text}]}}


def reply(text):
    return {"type": "assistant", "message": {"content": [{
        "type": "tool_use", "name": "mcp__hearthbot__reply", "input": {"text": text}
    }]}}


CASES = [
    ([TOOL, say("May I push this branch and open a pull request?")], True,
     "direct push and PR authorization ask blocks"),
    ([TOOL, say("Would you like me to open a PR now?")], True,
     "PR abbreviation authorization ask blocks"),
    ([TOOL, say("May I create a pull request now?")], True,
     "create-pull-request authorization ask blocks"),
    ([TOOL, say("Can I update the merge request with these changes?")], True,
     "update-merge-request authorization ask blocks"),
    ([TOOL, say("I need your approval before I push the changes.")], True,
     "approval requirement for a routine push blocks"),
    ([TOOL, reply("Can I open a merge request for this?")], True,
     "reply-tool merge-request authorization ask blocks"),
    ([TOOL, say("Should I force-push over the other session's commit?")], False,
     "force-push authorization remains allowed"),
    ([TOOL, say("May I merge this PR now?")], False,
     "merge authorization remains allowed"),
    ([TOOL, say("Membership is unverified for this external repository; may I push this branch?")], False,
     "unverified external membership allows an explicit authorization request"),
    ([TOOL, say("Pushed 2cfcd37 and opened PR #3868.")], False,
     "past-tense completion does not block"),
    ([TOOL, say("The documented example is `May I push this branch?`.")], False,
     "inline-code quotation does not block"),
    ([TOOL, say("````text\nWould you like me to open a PR?\n````")], False,
     "fenced quotation does not block"),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    try:
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        result = subprocess.run(
            [sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
            capture_output=True, text=True, env=env,
        )
        return '"decision": "block"' in result.stdout
    finally:
        os.unlink(path)


def main():
    failures = 0
    for events, expected, label in CASES:
        got = run(events)
        if got == expected:
            print(f"PASS: {label}")
        else:
            print(f"FAIL: {label} (expected block={expected}, got {got})")
            failures += 1
    print(f"\n{len(CASES) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
