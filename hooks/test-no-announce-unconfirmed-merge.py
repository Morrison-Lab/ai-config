#!/usr/bin/env python3
"""Test the no-announce-unconfirmed-merge guard.

Verifies that a reply announcing a future merge is blocked unless a merge call
since the last user turn confirmed one, the merge waits on the user's words, or
the phrase is quoted or only about a merge conflict, a policy, or the past.

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
    "message": {"content": [{"type": "tool_use", "id": "t0", "input": {"command": "git status"}}]},
}
USER = {"type": "user", "message": {"content": [{"type": "text", "text": "go"}]}}


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


def call(tool_id, command=None, name="Bash"):
    inp = {"command": command} if command else {}
    return {
        "type": "assistant",
        "message": {
            "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": inp}]
        },
    }


def result(text, tool_id, is_error=False):
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": text,
                 "is_error": is_error}
            ]
        },
    }


MERGE_CMD = "gh pr merge 5 -R Morrison-Lab/ai-config --squash"
MERGED = "Pull Request successfully merged"

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
    ([TOOL, reply("Every thread merges automatically.")], True,
     "every thread merges automatically blocks"),
    ([TOOL, say("The branch will merge as soon as checks pass.")], True,
     "narration text is read when no reply tool was used"),
    # True positives: paraphrases
    ([TOOL, reply("I'll merge it once CI is green.")], True, "I'll merge blocks"),
    ([TOOL, reply("I plan to merge after review.")], True, "I plan to merge blocks"),
    ([TOOL, reply("I am going to merge #5 tomorrow.")], True, "I am going to merge blocks"),
    ([TOOL, reply("I'll be merging them shortly.")], True, "I'll be merging blocks"),
    ([TOOL, reply("PRs are queued for merge once clean.")], True, "queued for merge blocks"),
    ([TOOL, reply("Auto-merge is enabled, so the queue merges on green.")], True,
     "merges on green blocks"),
    ([TOOL, reply("The queue merges automatically.")], True, "merges automatically blocks"),
    ([TOOL, reply("It will merge once CI passes, and the bot will ask the queue.")], True,
     "a verb like ask without a user subject is not a user-words condition"),
    ([TOOL, reply("It will merge once CI is green unless a conflict appears.")], True,
     "a condition on CI or conflicts is not a condition on the user's words"),

    # Confirmation is scoped to merge calls since the last user turn
    ([USER, call("m1", MERGE_CMD), result(MERGED, "m1"),
      reply("The rest will merge once green.")], False,
     "a confirmed merge call since the last user turn passes"),
    ([USER, call("m1", name="mcp__github__merge_pull_request"),
      result('{"merged": true}', "m1"), reply("Others will merge when clean.")], False,
     "merge tool with merged:true passes"),
    ([USER, call("m1", MERGE_CMD), result(chr(0x2713) + " Squashed and merged pull request #9", "m1"),
      reply("Next one will merge once clean.")], False,
     "gh squash output passes"),
    ([USER, call("m1", MERGE_CMD), result(MERGED, "m1", is_error=True),
      reply("It will merge once green.")], True,
     "an error result is not a confirmed merge"),
    ([USER, call("r1", "gh pr view 5 --json state"),
      result('{"state": "MERGED", "merged": true}', "r1"),
      reply("The rest will merge once green.")], True,
     "reading a merged PR's state is not a merge call"),
    ([USER, call("g1", "grep -r 'successfully merged' docs"), result(MERGED, "g1"),
      reply("It will merge once green.")], True,
     "a file or grep quoting 'successfully merged' is not a merge call"),
    ([USER, call("m1", MERGE_CMD), result(MERGED, "m1"), USER,
      reply("The next PR will merge once clean.")], True,
     "a merge before the last user turn does not excuse a later announcement"),

    # Negatives: conditional on the user's words, or the user merges
    ([TOOL, reply("It merges only after Ezra gives explicit merge words.")], False,
     "only after the user's words passes"),
    ([TOOL, reply("The PR will merge if you say so.")], False, "if you say so passes"),
    ([TOOL, reply("Nothing will be merged unless Ezra approves.")], False,
     "unless the user approves passes"),
    ([TOOL, reply("Ezra will merge when he is back.")], False,
     "the user is the merger passes"),

    ([TOOL, reply("I'm going to merge it now.")], True, "I'm going to merge blocks"),
    ([TOOL, reply("Once green, each PR gets merged.")], True, "gets merged blocks"),

    # System text in a user-role message is not a user turn
    ([USER, call("m1", MERGE_CMD), result(MERGED, "m1"),
      {"type": "user", "message": {"content": [
          {"type": "text", "text": "<system-reminder>queued wake</system-reminder>"}]}},
      reply("The rest will merge once green.")], False,
     "a system-reminder text block does not reset the confirmation"),

    # Negatives: first-person negation and deferral are the policy-correct stance
    ([TOOL, reply("I will not merge anything without your word.")], False, "will not merge passes"),
    ([TOOL, reply("I'll never merge without approval.")], False, "never merge passes"),
    ([TOOL, reply("I will merge nothing; Ezra decides.")], False, "merge nothing passes"),
    ([TOOL, reply("I'll wait for you to merge.")], False, "wait for you passes"),
    ([TOOL, reply("I'll ask you before I merge.")], False, "ask you before passes"),

    # Negatives: not an announcement
    ([TOOL, reply("Every merge requires your approval.")], False,
     "merge as a noun under approval passes"),
    ([TOOL, reply("Each merge needs your go.")], False, "merge needs your go passes"),
    ([TOOL, reply("Merging when ready is forbidden by policy.")], False,
     "policy sentence passes"),
    ([TOOL, reply("All the PRs merge cleanly into main.")], False,
     "merge cleanly passes"),
    ([TOOL, reply("Each PR merges only via the queue.")], False,
     "merges only via the queue passes"),
    ([TOOL, reply("The bot merges PRs once CI passes; that is how the repo works.")], False,
     "description of repo behaviour passes"),
    ([TOOL, reply("PR 4543 merged at 08:55 PDT.")], False, "past tense passes"),
    ([TOOL, reply("PR 4543 is open, clean, and waiting on your merge words.")], False,
     "state report passes"),
    ([TOOL, reply("The merge conflict is resolved.")], False, "merge as a noun passes"),
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

    # Fail open when the sibling module it reuses is missing.
    with tempfile.TemporaryDirectory() as d:
        lone = os.path.join(d, "no-announce-unconfirmed-merge.py")
        with open(HOOK, encoding="utf-8") as src, open(lone, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        orphan = subprocess.run([sys.executable, lone], input="{}",
                                capture_output=True, text=True)
    if orphan.returncode == 0 and not orphan.stderr.strip():
        print("PASS: missing sibling module fails open")
        passes += 1
    else:
        print("FAIL: missing sibling module fails open")
        failures += 1

    print(f"\n{passes} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
