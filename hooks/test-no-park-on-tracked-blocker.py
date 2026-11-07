#!/usr/bin/env python3
"""Test the no-park-on-tracked-blocker guard.

Run: python3 hooks/test-no-park-on-tracked-blocker.py hooks/no-park-on-tracked-blocker.py
"""
import json
import os
import subprocess
import sys
import tempfile
import uuid

HOOK = sys.argv[1]


def say(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def reply(text):
    return {
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use",
            "name": "mcp__hearthbot__post_message",
            "input": {"text": text},
        }]},
    }


def send(text):
    return {
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use",
            "name": "mcp__claude-code-remote__send_message",
            "input": {"message": text},
        }]},
    }


def user(text):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def tool_result():
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


def run(entries, active=False):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
        path = fh.name
    payload = {
        "transcript_path": path,
        "session_id": str(uuid.uuid4()),
        "stop_hook_active": active,
    }
    try:
        out = subprocess.run(
            [sys.executable, HOOK], input=json.dumps(payload),
            capture_output=True, text=True, timeout=20,
        ).stdout.strip()
    finally:
        os.unlink(path)
    return json.loads(out) if out else {}


def blocked(entries, active=False):
    return run(entries, active).get("decision") == "block"


CASES = [
    # (name, entries, expect_block)
    ("measured case", [reply("**Stopping Point**: Not clean; mds#649 waits on gha#1544.")], True),
    ("blocked by url", [say("This is blocked by https://github.com/o/r/issues/12 for now.")], True),
    ("depends on bare ref", [say("The stub change depends on #1545.")], True),
    ("until merges", [say("I'll hold the mds PR until gha#1545 merges.")], True),
    ("person gate passes", [say("mcs#99 waits on your approval.")], False),
    ("needs you passes", [say("gha#12 is blocked: it needs you to rotate the secret.")], False),
    ("no ref passes", [say("CI is still waiting on the runner.")], False),
    ("code span passes", [say("The phrase `waits on gha#1` is what the hook matches.")], False),
    ("plain status passes", [say("I merged mds#679, which closed #656.")], False),
    ("reply wins over text", [say("x waits on #3."), reply("All merged.")], False),
    ("wrapped line still caught", [say("mds#649 waits\non gha#1544, so I stopped.")], True),
    ("pending phrasing", [say("The stub PR is held pending gha#1545.")], True),
    ("no longer passes", [say("Unblocked: #5 no longer depends on #6.")], False),
    ("depends on nothing passes", [say("Done: closes #5; this depends on nothing.")], False),
    ("past tense passes", [say("I waited for #12 to merge, and it did.")], False),
    ("user gate passes", [say("Blocked on user: #5")], False),
    ("ezra's approval passes", [say("#5 is blocked on Ezra's approval.")], False),
    ("mwc passes", [say("PR #5 waits on mwc from the user.")], False),
    ("human-readable is not a gate", [say("It is human-readable, but waits on #5.")], True),
    ("separate bullets stay separate", [say("- waits on a fix\n- merged #4")], False),
    ("malformed lines tolerated", [[1], "x", {"type": "assistant", "message": "str"},
                                   say("x waits on #5.")], True),
    # ai-config#5063 review findings (agy, 2026-11-07).
    ("earlier turn's park does not block", [reply("mds#649 waits on gha#1544."), user("go"),
                                            say("I drove gha#1544 and merged mds#649; all done.")], False),
    ("earlier turn's all-clear does not hide", [reply("All clean."), user("go"),
                                                say("mds#649 waits on gha#1544.")], True),
    ("tool result is not a new turn", [reply("mds#649 waits on gha#1544."), tool_result()], True),
    ("CI wait with a later ref passes", [say("Waiting on CI for #12.")], False),
    ("ref as subject passes", [say("PR #12 is waiting on the macOS runner before auto-merge fires.")], False),
    ("past-tense which-clause passes", [say("I merged gha#1545, which mds#649 was waiting on.")], False),
    ("table rows stay separate", [say("| #12 | Merged |\n| Release | Waiting on tag build |")], False),
    ("status lines stay separate", [say("Merged #12\nWaiting on the deploy job")], False),
    ("until url merges", [say("Holding mds#685 until https://github.com/o/r/pull/12 merges.")], True),
    ("until dotted repo merges", [say("Holding it until owner/repo.name#7 merges.")], True),
    ("depending on", [say("Stopping here, depending on gha#1544.")], True),
    ("depend on", [say("Both mds#649 and mds#650 depend on gha#1544.")], True),
    ("held until ready", [say("mds#649 is held until gha#1544 is ready.")], True),
    ("bare mwc does not exempt", [say("Even with mwc active, mds#649 waits on gha#1544.")], True),
    ("bare approval does not exempt", [say("The token-approval PR (#649) waits on gha#1544.")], True),
    ("bare no longer does not exempt", [say("mds#649 no longer fails lint, and now waits on gha#1544.")], True),
    ("file anchor is not an item", [say("The test waits on [section 2](README.md#2) of the spec.")], False),
    ("send_message payload checked", [send("mds#649 waits on gha#1544.")], True),
]


def main():
    failures = 0
    for name, entries, expect in CASES:
        got = blocked(entries)
        if got != expect:
            failures += 1
            print(f"FAIL {name}: expected block={expect}, got {got}")
    if blocked([say("mds#649 waits on gha#1544.")], active=True):
        failures += 1
        print("FAIL stop_hook_active must not block")
    total = len(CASES) + 1
    print(f"{total - failures} of {total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
