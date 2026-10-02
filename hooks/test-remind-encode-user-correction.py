#!/usr/bin/env python3
"""Tests for hooks/remind-encode-user-correction.py (ai-config#4208).

Every pattern has at least one firing case and, where a nearby benign
phrasing exists, a near-miss that must stay silent.
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "remind-encode-user-correction.py")

FIRES = [
    # The two messages that motivated the hook, verbatim (typos included).
    "it's so frustrating when I have to tell you to do things that feel "
    "obvious, and hwen I have to repeat msyelf between sessions or projects",
    "even now, you're still interpreting my instructions too narrowly",
    # One per pattern.
    "I'm tired of repeating myself",
    "I keep reminding you about the footer",
    "I already told you to put the tables at the end",
    "I've told you this before",
    "like I said, Pacific time",
    "as I said earlier, link the PRs",
    "how many times do I have to say this",
    "this should be obvious",
    "you read that too literally",
    "you still not linking the PRs",
    "you keep forgetting the attribution line",
    "every time I start a session I have to remind you",
    "I shouldn't have to remind you to check the render",
    "you forgot the attribution footer again",
    "you’ve ignored the style guide again",
    # Curly apostrophe in the user's own words.
    "I shouldn’t have to tell you this",
]
SILENT = [
    "please render the manuscript again",
    "always use Pacific time in recaps",
    "what is the status of the sankey issue?",
    "run the tests one more time",
    "",
    # Near-misses for the narrowed patterns.
    "the CI is still not green",
    "is this still not merged?",
    "how many times does the loop run?",
    "do I need to tell you which branch?",
    "I already asked Sandy about the byline",
    "keep this between sessions",
    "you made the figure larger again, thanks",
    "the answer seems clear to me",
    # Correction words only inside text the user did not type as one.
    "fix this test:\n```\nassert 'I already told you' in out\n```\n",
    "> I already told you to stop\n\nthat's what the reviewer wrote; reply to it",
    "<system-reminder>you keep forgetting X</system-reminder>\nwhat next?",
    "<pasted_content id=\"a\">how many times do I need to say it</pasted_content> summarize",
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
