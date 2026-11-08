#!/usr/bin/env python3
"""Tests for hooks/no-owner-silence-while-pr-waits.py (ai-config#5116)."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-owner-silence-while-pr-waits.py")
NOW = "2026-11-08T19:00:00Z"


def user(ts):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": "continue"}}


def tool(ts, name, inp=None):
    return {"type": "assistant", "timestamp": ts, "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "t", "name": name, "input": inp or {}}]}}


PR = "mcp__github__create_pull_request"
POST = "mcp__hearthbot__post_message"
CASES = [
    ("pr open, last post 90 min ago", [user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR),
     tool("2026-11-08T17:30:00Z", POST), user("2026-11-08T18:59:00Z")], True),
    ("pr open, last post 10 min ago", [user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR),
     tool("2026-11-08T18:50:00Z", POST)], False),
    ("no report ever, thread 2h old", [user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR)], True),
    ("no pr owned", [user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:30:00Z", POST)], False),
    ("thread resolved after pr", [user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR),
     tool("2026-11-08T17:20:00Z", "mcp__hearthbot__set_thread_resolved", {"resolved": True})], False),
    ("coordinator message counts", [user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR),
     tool("2026-11-08T18:40:00Z", "mcp__hearthbot__message_coordinator")], False),
]


def run(entries, payload_extra=None, marker_reset=True):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(e) for e in entries) + "\n")
        env = dict(os.environ, OWNER_SILENCE_NOW=NOW)
        pl = json.dumps(dict({"transcript_path": p}, **(payload_extra or {})))
        outs = [subprocess.run([sys.executable, HOOK], input=pl, capture_output=True, text=True, env=env).stdout
                for _ in range(2)]
        return outs


fails = 0
for name, entries, deny in CASES:
    first, second = run(entries)
    ok = ('"block"' in first) == deny and second == ""
    print(("PASS: " if ok else "FAIL: ") + name)
    fails += not ok
out = run(CASES[0][1], {"stop_hook_active": True})[0]
ok = out == ""
print(("PASS: " if ok else "FAIL: ") + "stop_hook_active yields")
fails += not ok
r = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
ok = r.returncode == 0 and r.stdout == ""
print(("PASS: " if ok else "FAIL: ") + "bad input fails open")
fails += not ok
sys.exit(1 if fails else 0)
