#!/usr/bin/env python3
"""Tests for hooks/no-user-correction-without-mechanism.py (ai-config#4698).

Run: python3 hooks/test-no-user-correction-without-mechanism.py hooks/no-user-correction-without-mechanism.py

Regression cases are Ezra's own messages from 2026-10-23.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def user(text):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def github(author, body, shape="flat"):
    who = {"flat": author, "nested": {"login": author}}[shape]
    key = "user" if shape == "nested" else "author"
    event = json.dumps({key: who, "comment": body, "pr": "Morrison-Lab/x#1"})
    return user('<wake reason="external-event"><event source="github" kind="issue_comment.created" '
                'trust="relay">' + event + "</event></wake>")


def tool(blob):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Write", "input": {"file_path": blob}}]}}


TIRED = "I'm tired of watching the agents make the same mistakes over and over again"
WHY = "why aren't the subagents following our rules reliably?"
WHAT = "what happened to one div per file?"

# (events, should_block, label)
CASES = [
    ([user(TIRED), say("Understood, fixing.")], True, "tired of repeats, no mechanism"),
    ([user(WHY), say("Because hooks do not reach them.")], True, "why aren't the subagents following"),
    ([user(WHAT), say("It was broken.")], True, "what happened to one div per file"),
    ([user(TIRED), tool("/x/ai-config/hooks/no-offer-to-ask-lists.py")], False, "hook written"),
    ([user(TIRED), tool("/x/gha/check-foo/action.yml")], False, "gha check written"),
    ([user(TIRED), say("Mechanism: https://github.com/Morrison-Lab/ai-config/pull/1")], False, "mechanism cited"),
    ([user(TIRED), say("This mistake is not mechanizable: no condition decidable from the transcript.")], False, "not hookable, stated"),
    ([github("d-morrison", "you keep forgetting to link the term, same mistake again"), say("Fixed.")], True,
     "PR review comment from the user is a correction"),
    ([github("github-actions[bot]", "you keep forgetting to link the term, same mistake again"), say("Fixed.")], False,
     "a bot's review comment is not"),
    ([github("github-actions[bot]", "you keep forgetting to link the term, same mistake again", "nested"), say("Fixed.")],
     False, "a bot's comment in the nested user.login shape is not"),
    ([github("d-morrison", "you keep forgetting to link the term, same mistake again", "nested"), say("Fixed.")],
     True, "the owner's comment in the nested user.login shape is"),
    ([user(TIRED), say("ok"), user("[SYSTEM NOTIFICATION] CI finished"), say("fine")], True,
     "a later notification does not clear the correction"),
    ([user("please run the tests"), say("done")], False, "ordinary request"),
    ([user(TIRED), say("ok"), user("thanks"), say("welcome")], True, "a later plain message does not clear the correction"),
    ([user("The rule is quoted: `you keep forgetting`"), say("ok")], False, "quoted phrase"),
]


def run(events, tmp):
    path = os.path.join(tmp, "t.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    p = subprocess.run([sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
                       capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for i, (events, should_block, label) in enumerate(CASES):
        tmp = tempfile.mkdtemp()
        try:
            # distinct text per case keeps the once-per-message sentinel from leaking between cases
            events = [dict(e) for e in events]
            salt = f" (case {i} {os.getpid()})"
            for e in events:
                if e["type"] == "user":
                    e["message"] = {"content": [{"type": "text", "text": e["message"]["content"][0]["text"] + salt}]}
            rc, out = run(events, tmp)
            blocked = '"decision": "block"' in out
            ok = rc == 0 and blocked == should_block
            print(("  ok      " if ok else "  FAIL    ") + label)
            fails += 0 if ok else 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # Once per message: the second run on the same transcript is silent.
    tmp = tempfile.mkdtemp()
    ev = [user(TIRED + f" (once {os.getpid()})"), say("ok")]
    first = '"decision": "block"' in run(ev, tmp)[1]
    second = '"decision": "block"' in run(ev, tmp)[1]
    ok = first and not second
    print(("  ok      " if ok else "  FAIL    ") + "blocks once per message")
    fails += 0 if ok else 1
    # Fails open on garbage and on a missing transcript.
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    print(f"\n{len(CASES) + 2 - fails}/{len(CASES) + 2} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
