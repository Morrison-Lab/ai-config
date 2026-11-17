#!/usr/bin/env python3
"""Test the no-ums-deferral-in-stopping-point guard.

Run: python3 hooks/test-no-ums-deferral-in-stopping-point.py hooks/no-ums-deferral-in-stopping-point.py
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
    return {"type": "assistant", "message": {"content": [{
        "type": "tool_use", "name": "mcp__hearthbot__post_message", "input": {"text": text}}]}}


def user(text):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def run(entries):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
        path = fh.name
    payload = {"transcript_path": path, "session_id": str(uuid.uuid4()), "stop_hook_active": False}
    try:
        out = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                             capture_output=True, text=True, timeout=20).stdout.strip()
    finally:
        os.unlink(path)
    return json.loads(out) if out else {}


CASES = [
    ("measured: not yet run", [reply("**Stopping Point**: Not clean; UMS not yet run.")], True),
    ("not executed", [say("**Stopping Point**: Clean stopping point reached --- UMS not executed")], True),
    ("pending", [say("Stopping Point: Not clean; UMS pending")], True),
    ("will run later", [say("**Stopping Point**: Not clean; will run UMS later")], True),
    ("no UMS", [say("- **Stopping Point**: Clean; no UMS this turn")], True),
    ("skipped", [say("**Stopping Point**: Clean; UMS skipped")], True),
    ("didn't run", [say("**Stopping Point**: Not clean; didn't run UMS yet.")], True),
    ("haven't run", [say("**Stopping Point**: Not clean; we haven't run UMS this turn.")], True),
    ("isn't done", [say("**Stopping Point**: Not clean; UMS isn't done.")], True),
    ("won't run", [say("**Stopping Point**: Clean; won't run UMS.")], True),
    ("executed passes", [say("**Stopping Point**: Clean stopping point reached --- session done; UMS executed; no follow-up items pending")], False),
    ("pending CI before a comma", [say("**Stopping Point**: Not clean. CI and review are still pending, UMS has run, and nothing new needs filing.")], False),
    ("UMS ran, CI pending after a comma", [say("**Stopping Point**: Not clean; UMS ran, CI pending")], False),
    ("ran UMS passes", [say("**Stopping Point**: Not clean; ran UMS, gha#1 awaits CI")], False),
    ("no stopping point line", [say("UMS not yet run, but this is a status reply.")], False),
    ("in fence", [say("```\n**Stopping Point**: Not clean; UMS not yet run\n```")], False),
    ("earlier turn ignored", [say("**Stopping Point**: UMS not yet run"), user("ok"), say("done")], False),
    ("empty", [], False),
]

fails = 0
for name, entries, want in CASES:
    got = run(entries).get("decision") == "block"
    if got != want:
        fails += 1
        print("FAIL", name, "want", want, "got", got)
print("{} cases, {} failures".format(len(CASES), fails))
sys.exit(1 if fails else 0)
