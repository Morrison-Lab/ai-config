#!/usr/bin/env python3
"""Test the no-announce-unconfirmed-merge guard.

Verifies that a reply announcing a future merge is blocked when the transcript
holds no confirmed merge, and passes when the merge is conditional on the
user's words, already confirmed, past tense, or quoted in code.

Run: python3 hooks/test-no-announce-unconfirmed-merge.py hooks/no-announce-unconfirmed-merge.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]

TOOL = {
    "type": "assistant",
    "message": {"content": [{"type": "tool_use", "input": {"command": "git status"}}]},
}


def reply(text, name="mcp__hearthbot__post_message"):
    return {
        "type": "assistant",
        "message": {
            "content": [{"type": "tool_use", "name": name, "input": {"text": text}}]
        },
    }


def say(text):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def result(text, is_error=False):
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "content": text, "is_error": is_error}
            ]
        },
    }


CASES = [
    # True positives: the announcement shapes seen in the incident
    ([TOOL, reply("Each thread merges as soon as it is clean.")], True,
     "each thread merges as soon as blocks"),
    ([TOOL, reply("PR 4543 will merge once CI is green.")], True,
     "will merge once blocks"),
    ([TOOL, reply("Both PRs will be merged when review finishes.")], True,
     "will be merged when blocks"),
    ([TOOL, reply("It merges after the review is clean.")], True,
     "merges after blocks"),
    ([TOOL, reply("The PR is going to be merged shortly.")], True,
     "going to be merged blocks"),
    ([TOOL, say("The branch will merge as soon as checks pass.")], True,
     "narration text is read when no reply tool was used"),
    ([TOOL, result("Pull Request successfully merged", is_error=True),
      reply("It will merge once green.")], True,
     "an error result is not a confirmed merge"),
    ([TOOL, reply("Every thread merges automatically.")], True,
     "every thread merges without a trailing condition blocks"),
    ([TOOL, result("Pull request #5 opened"), reply("It will merge once green.")], True,
     "an unrelated tool result is not a confirmed merge"),

    # Negatives: merge confirmed in the transcript
    ([TOOL, result("Pull Request successfully merged"), reply("The rest will merge once green.")],
     False, "a confirmed merge result earlier in the transcript passes"),
    ([TOOL, result([{"type": "text", "text": "✓ Squashed and merged pull request #9"}]),
      reply("Next one will merge once clean.")], False,
     "a confirmed merge in list-form content passes"),
    ([TOOL, result('{"merged": true}'), reply("Others will merge when clean.")], False,
     "merged:true JSON passes"),

    # Negatives: conditional on the user's words
    ([TOOL, reply("It merges only after Ezra gives explicit merge words.")], False,
     "only after the user's words passes"),
    ([TOOL, reply("The PR will merge if you say so.")], False,
     "if you say so passes"),
    ([TOOL, reply("Nothing will be merged unless Ezra approves.")], False,
     "unless the user approves passes"),

    # Negatives: not an announcement
    ([TOOL, reply("PR 4543 merged at 08:55 PDT.")], False, "past tense passes"),
    ([TOOL, reply("PR 4543 is open, clean, and waiting on your merge words.")], False,
     "state report passes"),
    ([TOOL, reply("The merge conflict is resolved.")], False,
     "merge as a noun passes"),
    ([TOOL, reply("The hook flags `will merge as soon as` phrasing.")], False,
     "phrase quoted in a code span passes"),
    ([TOOL, say("Done.")], False, "unrelated text passes"),
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
        return '"decision": "block"' in out
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

    # Sentinel: the same message twice blocks once.
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(reply("It will merge once green.")) + "\n")
    env = dict(os.environ, TMPDIR=tempfile.mkdtemp())
    payload = json.dumps({"transcript_path": path})
    outs = [
        subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                       text=True, env=env).stdout
        for _ in range(2)
    ]
    os.unlink(path)
    if "block" in outs[0] and "block" not in outs[1]:
        print("PASS: sentinel stops repeating block on same message")
        passes += 1
    else:
        print("FAIL: sentinel stops repeating block on same message")
        failures += 1

    # Fail open on an unreadable payload.
    bad = subprocess.run([sys.executable, HOOK], input="not json",
                         capture_output=True, text=True)
    if bad.returncode == 0 and not bad.stdout.strip():
        print("PASS: unreadable payload fails open")
        passes += 1
    else:
        print("FAIL: unreadable payload fails open")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
