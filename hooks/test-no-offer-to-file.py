#!/usr/bin/env python3
"""Test the no-offer-to-file guard.

Verifies that offers to file or record in ordinary prose are blocked, while
trigger phrases quoted inside backtick code spans, fenced code blocks, or
standard non-offer replies pass cleanly.

Run: python3 hooks/test-no-offer-to-file.py hooks/no-offer-to-file.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

TOOL = {
    "type": "assistant",
    "message": {
        "content": [{"type": "tool_use", "input": {"command": "git status"}}]
    },
}


def say(text):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


CASES = [
    # True positives: direct offers in prose
    ([TOOL, say("Want me to file an issue for this?")], True, "want me to file blocks"),
    ([TOOL, say("Should I record this learning?")], True, "should I record blocks"),
    ([TOOL, say("Shall I save this in memory?")], True, "shall I save blocks"),
    ([TOOL, say("Say the word and I will file an issue.")], True, "say the word and I will file blocks"),
    ([TOOL, say("Is this worth filing as an issue?")], True, "worth filing blocks"),
    ([TOOL, say("Let me know if you'd like me to file a bug report.")], True, "let me know if you would like me to file blocks"),
    ([TOOL, say("I could file an issue about this?")], True, "i could file an issue blocks"),
    ([TOOL, say("Want me to file the issue and open that PR?")], True, "bundled offer blocks"),

    # Negative cases: trigger phrases quoted inside inline code spans
    (
        [TOOL, say("We shouldn't add a hook for `want me to file` because it is too broad.")],
        False,
        "trigger phrase in inline code span does not block",
    ),
    (
        [TOOL, say("The regex matches `should I record` or `worth filing?` examples.")],
        False,
        "multiple trigger phrases in inline code spans do not block",
    ),

    # Negative cases: trigger phrases inside fenced code blocks
    (
        [
            TOOL,
            say(
                "Here is an example:\n```\nwant me to file an issue?\n```\nThat was a quote."
            ),
        ],
        False,
        "trigger phrase in fenced code block does not block",
    ),

    # Negative cases: ordinary prose and completions
    (
        [TOOL, say("Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948).")],
        False,
        "past-tense filing report does not block",
    ),
    (
        [TOOL, say("Implementation complete and all tests pass.")],
        False,
        "standard completion report does not block",
    ),
    ([TOOL], False, "turn with no text does not block"),

    # Antigravity format cases
    (
        [
            {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git status"}}]},
            {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Want me to file an issue for this?"}
        ],
        True,
        "antigravity format offer blocks",
    ),
    (
        [
            {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "git status"}}]},
            {"source": "MODEL", "type": "PLANNER_RESPONSE", "content": "Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948)."}
        ],
        False,
        "antigravity format non-offer does not block",
    ),
]


def run(events):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
        out = subprocess.run(
            [sys.executable, HOOK],
            input=json.dumps({"transcript_path": path}),
            capture_output=True,
            text=True,
            env=env,
        ).stdout
        return '"decision": "block"' in out or '"decision":"block"' in out
    finally:
        os.unlink(path)


def main():
    passes = failures = 0
    for events, expected, label in CASES:
        got = run(events)
        if got == expected:
            print(f"PASS: {label}")
            passes += 1
        else:
            print(f"FAIL: {label} (expected block={expected}, got {got})")
            failures += 1

    # Sentinel behavior: same message twice should not block on second run
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(say("Want me to file an issue?")) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    payload = json.dumps({"transcript_path": path})
    first = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    second = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    os.unlink(path)

    if "block" in first and "block" not in second:
        print("PASS: sentinel stops repeating block on same message")
        passes += 1
    else:
        print("FAIL: sentinel did not suppress repeat block")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
