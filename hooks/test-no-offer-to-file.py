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


def reply(text):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "mcp__hearthbot__reply",
                    "input": {"text": text},
                }
            ]
        },
    }


def narrate_and_reply(narration, text):
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": narration},
                {
                    "type": "tool_use",
                    "name": "mcp__hearthbot__reply",
                    "input": {"text": text},
                },
            ]
        },
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

    # Statement-shaped offers (no question mark): both let through before
    (
        [TOOL, say(
            "I can also file a gha issue about the `@claude` job committing "
            "leftover session files onto PR branches, since that will happen "
            "again whenever someone writes \"@claude review\". Say if you want it."
        )],
        True,
        "statement offer 'I can also file ... Say if you want it' blocks",
    ),
    (
        [TOOL, say("I haven't filed an issue about it. Say if you want one.")],
        True,
        "statement offer 'I haven't filed an issue ... Say if you want one' blocks",
    ),
    ([TOOL, say("I haven't filed an issue about it.")], True, "haven't filed an issue alone blocks"),
    ([TOOL, say("I can file an issue for the flaky test.")], True, "i can file an issue statement blocks"),
    (
        [TOOL, say("The memory entry would cover this. Just say the word.")],
        True,
        "say the word near a memory mention blocks",
    ),
    (
        [TOOL, say("This deserves an issue. Let me know if you want me to file it.")],
        True,
        "let me know if you want me to file blocks",
    ),

    # Legitimate reports that share vocabulary with the statement patterns
    (
        [TOOL, say("I filed https://github.com/Morrison-Lab/gha/issues/981 about it.")],
        False,
        "report of a filed issue by URL does not block",
    ),
    (
        [TOOL, say(
            "I haven't filed an issue because "
            "https://github.com/Morrison-Lab/gha/issues/981 already tracks it."
        )],
        False,
        "not filing a duplicate does not block",
    ),
    (
        [TOOL, say(
            "Filed https://github.com/Morrison-Lab/gha/issues/981. "
            "Say if you want me to open a PR for the fix."
        )],
        False,
        "discretionary PR offer after a filed issue does not block",
    ),
    (
        [TOOL, say(
            "Filed https://github.com/Morrison-Lab/gha/issues/981 and recorded "
            "the lesson in memories/hooks.md. Say if you want it closed once the PR merges."
        )],
        False,
        "say if you want it <verb> after a filing report does not block",
    ),
    (
        [TOOL, say("The hook matches `I can also file a gha issue` statements now.")],
        False,
        "statement pattern quoted in a code span does not block",
    ),
    (
        [TOOL, say("I can't file an issue in that repo: the token lacks access.")],
        False,
        "reporting inability to file does not block",
    ),

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

    # Reply-tool visibility cases (project threads)
    (
        [TOOL, reply("Want me to file an issue for this?")],
        True,
        "reply-tool payload offer blocks",
    ),
    (
        [TOOL, reply("Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948).")],
        False,
        "reply-tool payload non-offer does not block",
    ),
    (
        [
            TOOL,
            narrate_and_reply(
                "Want me to file an issue for this?",
                "Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948).",
            ),
        ],
        False,
        "undelivered narration offer does not block when reply spoke",
    ),
    (
        [
            TOOL,
            narrate_and_reply(
                "Filed as [#1948](https://github.com/Morrison-Lab/ai-config/issues/1948).",
                "Want me to file an issue for this?",
            ),
        ],
        True,
        "reply-tool offer wins over clean narration",
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
