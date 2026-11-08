#!/usr/bin/env python3
"""Tests for hooks/no-owner-silence-while-pr-waits.py (ai-config#5116)."""
import json
import os
import subprocess
import sys
import tempfile
import uuid

HOOK = os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-owner-silence-while-pr-waits.py")
NOW = "2026-11-08T19:00:00Z"
PR = "mcp__github__create_pull_request"
POST = "mcp__hearthbot__post_message"


def user(ts):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": "continue"}}


def tool(ts, name, inp=None, ident="t", error=False):
    """A tool_use entry followed by its tool_result, as the transcript records them."""
    return [
        {"type": "assistant", "timestamp": ts, "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": ident, "name": name, "input": inp or {}}]}},
        {"type": "user", "timestamp": ts, "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": ident, "is_error": error, "content": "x"}]}},
    ]


def flat(*parts):
    return [e for p in parts for e in (p if isinstance(p, list) else [p])]


CASES = [
    ("pr open, last post 90 min ago", flat(
        user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR, ident="a"),
        tool("2026-11-08T17:30:00Z", POST, ident="b"), user("2026-11-08T18:59:00Z")), True),
    ("pr open, last post 10 min ago", flat(
        user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR, ident="a"),
        tool("2026-11-08T18:50:00Z", POST, ident="b")), False),
    ("no report ever, thread 2h old", flat(
        user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR, ident="a")), True),
    ("no pr owned", flat(
        user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:30:00Z", POST, ident="b")), False),
    ("thread resolved after pr", flat(
        user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR, ident="a"),
        tool("2026-11-08T17:20:00Z", "mcp__hearthbot__set_thread_resolved", {"resolved": True}, ident="b")), False),
    ("coordinator message counts", flat(
        user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR, ident="a"),
        tool("2026-11-08T18:40:00Z", "mcp__hearthbot__message_coordinator", ident="b")), False),
    ("a failed create does not make an owner", flat(
        user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR, ident="a", error=True)), False),
    ("a failed create after a good one keeps the owner", flat(
        user("2026-11-08T17:00:00Z"), tool("2026-11-08T17:10:00Z", PR, ident="a"),
        tool("2026-11-08T17:20:00Z", PR, ident="c", error=True)), True),
]


def run(entries, extra=None):
    """Run the hook twice on one payload, returning both stdout strings."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(e) for e in entries) + "\n")
        env = dict(os.environ, OWNER_SILENCE_NOW=NOW)
        # A fresh session id keeps agent_notice's once-per-turn sentinel unique to this run.
        payload = dict({"transcript_path": p, "session_id": uuid.uuid4().hex}, **(extra or {}))
        text = json.dumps(payload)
        return [subprocess.run([sys.executable, HOOK], input=text, capture_output=True,
                               text=True, env=env).stdout for _ in range(2)]


fails = 0
for name, entries, deny in CASES:
    first, second = run(entries)
    # The second run of a blocked turn degrades to a systemMessage, never a second block.
    out1 = json.loads(first) if first else {}
    out2 = json.loads(second) if second else {}
    blocked = out1.get("decision") == "block" and "reported nothing" in out1.get("reason", "")
    ok = blocked == deny and out2.get("decision") != "block"
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
