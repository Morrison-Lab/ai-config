"""Test the flag-cant-without-tool-check guard.

Run: python3 hooks/test-flag-cant-without-tool-check.py hooks/flag-cant-without-tool-check.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def say(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def reply(text):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "mcp__hearthbot__post_message", "input": {"text": text}}]}}


def tool(name):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": {"query": "select:x"}}]}}


def user(text):
    return {"type": "user", "message": {"content": text}}


RESULT = {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}

CASES = [
    ([user("switch to auto mode"), say("I can't, only you control that.")], True,
     "the founding incident warns"),
    ([user("switch"), reply("I can\u2019t change my own permission mode.")], True,
     "post_message payload with a curly apostrophe warns"),
    ([user("switch"), say("Only you can approve that.")], True, "'only you can' warns"),
    ([user("switch"), say("I am unable to reach that host from my sandbox.")], True, "unable to warns"),
    ([user("switch"), tool("ToolSearch"), RESULT, say("I can't: no mode-switch tool exists.")],
     False, "a ToolSearch in the turn stays silent"),
    ([user("old"), tool("ToolSearch"), RESULT, say("done"), user("new"),
      say("I can't do that from this session.")], True, "a ToolSearch from an earlier turn does not count"),
    ([user("go"), say("The hook text says `I can't` in its example.")], False,
     "a quoted claim stays silent"),
    ([user("go"), say("I can't believe it. I can't tell if this is a bug. I can't find the file.")],
     False, "plain idioms stay silent"),
    ([user("go"), say("I can't believe this took so long. I switched the mode using the tool.")],
     False, "an idiom beside correct tool use stays silent"),
    ([user("go"), say("I can't switch my own permission mode.")], True, "can't switch warns"),
    ([user("go"), say("We are unable to merge it from this session.")], True, "we are unable to warns"),
    ([user("go"), say("I can't make sense of this. I can't change the fact that it failed.")],
     False, "idioms with action verbs stay silent"),
    ([user("go"), say("I can't stop myself from rechecking. I can't grant myself the benefit of "
                      "the doubt. I can't control my own excitement. I can't connect the dots "
                      "in this environment. I can't find my own mistake. "
                      "I can't stress enough that settings like these need review. "
                      "I can't say whether this works given the access restrictions.")],
     False, "idioms beside capability nouns stay silent"),
    ([user("go"), say("I am unable to reproduce it. I can't reach a conclusion. We can't "
                      "control what happens next.")], False, "unable-to and verb idioms stay silent"),
]


def run(events, payload_extra=None):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
        payload = {"transcript_path": path, "session_id": "s-" + os.path.basename(d)}
        payload.update(payload_extra or {})
        env = dict(os.environ, TMPDIR=d)
        out = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                             capture_output=True, text=True, env=env)
        return out.stdout, out.returncode


fails = 0
for events, expect, name in CASES:
    out, rc = run(events)
    data = json.loads(out) if out.strip() else {}
    got = data.get("decision") == "block" and "never searched for tools" in data.get("reason", "")
    ok = rc == 0 and got == expect
    print(("ok   " if ok else "FAIL ") + name)
    fails += not ok

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "t.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for e in [user("x"), say("I can't do that from this session.")]:
            fh.write(json.dumps(e) + "\n")
    env = dict(os.environ, TMPDIR=d)
    args = dict(input=json.dumps({"transcript_path": path, "session_id": "once"}),
                capture_output=True, text=True, env=env)
    first = subprocess.run([sys.executable, HOOK], **args).stdout
    second = subprocess.run([sys.executable, HOOK], **args).stdout
    ok = "never searched" in first and second == ""
    print(("ok   " if ok else "FAIL ") + "warns once per message")
    fails += not ok

out = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
ok = out.returncode == 0 and out.stdout == ""
print(("ok   " if ok else "FAIL ") + "fails open on bad input")
fails += not ok
sys.exit(1 if fails else 0)
