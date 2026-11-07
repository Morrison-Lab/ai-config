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
    ("every output in the turn counts", [say("x waits on #3."), reply("All merged.")], True),
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
    ("park then closing line still blocks", [send("mds#649 waits on gha#1544."), say("Reported in the thread.")], True),
    ("ref in a code span still an item", [say("mds#649 waits on `gha#1544`.")], True),
    ("filler before the item", [say("mds#649 waits on the PR for gha#1544.")], True),
    ("CI-noun object then a ref line", [say("Status: waiting on upstream\n#12 merged cleanly")], False),
    ("gate in another clause does not exempt", [say("gha#10 is unblocked now, but mds#649 waits on gha#1544.")], True),
    ("which-clause person gate exempts", [say("This waits on #5, which requires a manual action on a device.")], False),
    ("until without a parking verb passes", [say("I ran the watcher loop until #12 is merged, and all checks are now green.")], False),
    ("parked on", [say("mds#649 is parked on gha#1544.")], True),
    ("once item merges", [say("I'll pick mds#649 back up once gha#1544 merges.")], True),
    ("needs to merge first", [say("gha#1544 needs to merge first.")], True),
    ("meta line is not a user turn", [reply("mds#649 waits on gha#1544."),
                                      {"type": "user", "isMeta": True,
                                       "message": {"content": [{"type": "text", "text": "note"}]}}], True),
    ("reminder is not a user turn", [reply("mds#649 waits on gha#1544."), user("<system-reminder>x</system-reminder>")], True),
    ("json anchor is not an item", [say("The test waits on docs/spec.json#2.")], False),
    ("possessive ref is not the object", [say("I'll wait for #12's CI.")], False),
    # Round 3 (agy): bypasses.
    ("which-unblocked does not exempt", [say("mds#649 waits on gha#1544, which is unblocked.")], True),
    ("which-depends-on-nothing does not exempt", [say("mds#649 waits on gha#1544, which depends on nothing.")], True),
    ("since-no-longer-blocked does not exempt",
     [say("mds#649 waits on gha#1544, since gha#1544 is no longer blocked.")], True),
    ("bare and splits clauses", [say("gha#10 is unblocked and mds#649 waits on gha#1544.")], True),
    ("wrapped filler before ref", [say("mds#649 waits on the\ngha#1544 PR.")], True),
    ("linked ref before merges",
     [say("I'll pick mds#649 back up once [gha#1545](https://github.com/o/r/pull/1545) merges.")], True),
    ("linked ref needs to merge first", [say("[gha#1544](https://github.com/o/r/pull/1544) needs to merge first.")], True),
    ("needs to be merged first", [say("gha#1544 needs to be merged first.")], True),
    ("code span with PR prefix", [say("mds#649 waits on `PR #1544`.")], True),
    ("workflow PR is an item", [say("mds#649 waits on the workflow PR gha#1544.")], True),
    ("test fix in item", [say("mds#649 waits on the test fix in gha#1544.")], True),
    ("awaiting", [say("mds#649 is awaiting gha#1544.")], True),
    ("is blocking", [say("gha#1544 is blocking mds#649.")], True),
    ("gated on", [say("mds#649 is gated on gha#1544.")], True),
    ("still pending", [say("mds#649 is still pending gha#1544.")], True),
    # Round 3 (agy): false positives.
    ("wrapped person gate", [say("mcs#99 waits on\n#12 for your approval.")], False),
    ("wrapped phrase then manual gate", [say("mcs#99 waits\non #12, which requires a manual action.")], False),
    ("wrapped no longer", [say("#5 no longer\nwaits on #6.")], False),
    ("stopping point label is not a park verb",
     [say("**Stopping Point**: Clean; I polled until #12 is merged, and all checks are green.")], False),
    ("past-tense until is a report", [say("I waited until #12 is merged, and all checks are now green.")], False),
    ("until with your approval", [say("I'm holding #5 until #6 merges with your approval.")], False),
    ("auto-merge report", [say("Auto-merge will fire once #12 is ready.")], False),
    ("auto-close report", [say("GitHub closes #10 automatically when #12 merges.")], False),
    ("deploy report", [say("The deploy workflow runs after #12 lands.")], False),
    ("codecov for item", [say("Waiting on codecov for #12.")], False),
    ("benchmark results for item", [say("Waiting on benchmark results for #12.")], False),
    ("leading because gate", [say("Because this needs your approval, mcs#99 waits on #12.")], False),
    ("semicolon it-clause gate", [say("mcs#99 waits on #12; it needs your approval.")], False),
    ("requires your secret", [say("mcs#99 waits on #12, which requires your secret.")], False),
    ("needs a secret", [say("mcs#99 waits on #12, which needs a secret.")], False),
    ("until you approve", [say("mcs#99 waits on #12 until you approve it.")], False),
    ("possessive url", [say("I'll wait for https://github.com/o/r/pull/12's CI.")], False),
    ("possessive code span", [say("I'll wait for `#12`'s CI.")], False),
    ("possessive link", [say("I'll wait for [#12](https://github.com/o/r/pull/12)'s CI.")], False),
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
