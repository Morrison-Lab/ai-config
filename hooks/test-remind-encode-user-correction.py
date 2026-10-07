#!/usr/bin/env python3
"""Tests for hooks/remind-encode-user-correction.py (ai-config#4208).

Every pattern has a firing case that no other pattern matches (checked by
the uniqueness pass at the bottom), and the benign phrasings found in review
are kept as SILENT near-misses.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "remind-encode-user-correction.py")
RSQ = chr(0x2019)

FIRES = [
    # The two messages that motivated the hook, verbatim (typos included).
    "it's so frustrating when I have to tell you to do things that feel "
    "obvious, and hwen I have to repeat msyelf between sessions or projects",
    "even now, you're still interpreting my instructions too narrowly",
    # Having to say something again.
    "I'm tired of repeating myself",
    "please don't make me repeat this",
    "I repeat: link the PRs",
    "I keep reminding you to link the PRs",
    "why do I have to keep saying this",
    "I just told you",
    "I already explained this to you",
    "I told you yesterday to use Pacific time",
    "I've said this before",
    "didn't I tell you to always link PRs?",
    "haven't I told you about Pacific time?",
    "hity to use Pacific time",
    "as I said before, Pacific time",
    "how many times do I have to say this",
    "for the third time: use semantic line breaks",
    "we went over this last session",
    "every time I start a session I have to remind you",
    "I shouldn" + RSQ + "t have to remind you to check the render",
    "I shouldn" + RSQ + "t have to ask for this",
    "I keep having to tell you",
    "I've had to say it five times",
    "I've had to tell you this in every session",
    "I told you that already",
    "I've repeated this many times",
    "you're doing it again",
    "you still haven't fixed the footer",
    "you misread my instruction",
    "Thats not what I asked",
    # The agent repeating a miss.
    "you still not linking the PRs",
    "you keep forgetting the attribution line",
    "you never remember to add the footer",
    "you forgot the attribution footer again",
    "you" + RSQ + "ve ignored the style guide again",
    "you did it again",
    "same mistake as last time",
    # The agent reading an instruction wrongly.
    "you're taking it too literally",
    "this should handle things that seem obvious",
    "that's not what I asked for",
    "you ignored my instruction",
]
SILENT = [
    "please render the manuscript again",
    "always use Pacific time in recaps",
    "what is the status of the sankey issue?",
    "run the tests one more time",
    "",
    "the CI is still not green",
    "is this still not merged?",
    "how many times does the loop run?",
    "how many times do I need to run the migration?",
    "how many times should I retry a flaky test?",
    "do I need to tell you which branch?",
    "I already asked Sandy about the byline",
    "keep this between sessions",
    "you made the figure larger again, thanks",
    "the answer seems clear to me",
    "as I said in the PR description, this adds a cache",
    "like I said, thanks, that looks great",
    "like I asked, can you also add tests",
    "the docs say the fix should be obvious from the stack trace",
    "it seems obvious that the bug is in parse()",
    "the regex matches too literally, can you loosen it",
    "the README is worded too narrowly; broaden it",
    "are you still getting that error?",
    "you still getting the 403?",
    "I have to tell you something: the meeting moved",
    "I've told you the password is in the vault, right?",
    "you missed nothing, again great work",
    "you broke the build again? no, CI flake",
    "every time the CI runs it posts.\nCan you tell me why?",
    "it's not what I wanted to hear but OK",
    "you're doing great",
    # Correction words only inside text the user did not type as one.
    "fix this test:\n```\nassert 'I already told you' in out\n```\n",
    "> I already told you to stop\n\nthat's what the reviewer wrote; reply to it",
    "<system-reminder>you keep forgetting X</system-reminder>\nwhat next?",
    "<pasted_content id=\"a\">how many times do I have to say it</pasted_content> summarize",
    'add a test where the user says "you keep forgetting"',
    "add a test for `I just told you`",
    "    > quoted inside indented code: I already told you",
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

# Every pattern must be the only match for at least one FIRES case, so
# deleting any one pattern fails this test.
spec = importlib.util.spec_from_file_location("hook", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)
compiled = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in hook.PATTERNS]
for index, pattern in enumerate(compiled):
    sole = [t for t in FIRES
            if pattern.search(hook.typed_text(t))
            and not any(o.search(hook.typed_text(t))
                        for j, o in enumerate(compiled) if j != index)]
    if not sole:
        print(f"FAIL: pattern {index} has no FIRES case only it matches: "
              f"{hook.PATTERNS[index]!r}")
        failures += 1

total = len(FIRES) + len(SILENT) + 3 + len(compiled)
print(f"{total - failures}/{total} passed")
sys.exit(1 if failures else 0)
