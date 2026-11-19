#!/usr/bin/env python3
"""Tests for scripts/lib/session_pause.py and its use in agent_notice (ai-config#3911)."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib"))

from agent_notice import stop_notice  # noqa: E402
from session_pause import is_pause_command, is_paused  # noqa: E402

FAILURES = []


def check(label, ok):
    print(("PASS: " if ok else "FAIL: ") + label)
    if not ok:
        FAILURES.append(label)


def user(text):
    return {"type": "user", "message": {"content": text}}


def say(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def transcript(*entries):
    handle, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(handle, "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
    return path


# The command itself.
for prompt in ("pause", "Pause.", "  pause  ", "/pause", "/ai-config:pause",
               "pause, back after lunch", "pause: lunch", "/pause back after lunch",
               "<command-name>/pause</command-name>\n<command-args></command-args>",
               "<command-name>/pause</command-name>\n"
               "<command-args>back after lunch</command-args>"):
    check(f"{prompt!r} pauses", is_pause_command(prompt))
for prompt in ("<command-name>/pause</command-name>\n<command-args>"
               + "x" * 81 + "</command-args>",
               "/pause " + "x" * 81,
               "pause the video at 2:13 and describe what the slide shows, "
               "then compare it with the notes page",
               "pause the docker container and check logs", "pause here",
               "don't pause", "paused", "pauses", "please continue", ""):
    check(f"{prompt!r} does not pause", not is_pause_command(prompt))

# The latest prompt decides, and harness entries are not prompts.
cases = [
    ((user("fix the test"), say("on it"), user("pause")), True,
     "the latest prompt is a pause"),
    ((user("pause"), say("paused"), user("ok, carry on")), False,
     "any later prompt ends the pause"),
    ((user("pause"), {"type": "user", "isMeta": True,
                      "message": {"content": "Stop hook feedback: push it"}}), True,
     "hook feedback after the pause does not end it"),
    ((user("pause"), {"type": "user", "toolUseResult": {}, "message": {"content": [
        {"type": "tool_result", "content": "ok"}]}}), True,
     "a tool result after the pause does not end it"),
    ((user("pause"), {"type": "user", "isSidechain": True,
                      "message": {"content": "subagent brief"}}), True,
     "a subagent's prompt does not end the pause"),
    ((user("fix the test"),), False, "no pause at all"),
]
for entries, expected, label in cases:
    path = transcript(*entries)
    try:
        check(label, is_paused({"transcript_path": path}) is expected)
    finally:
        os.unlink(path)

# A record too deeply nested for json to decode is skipped, not raised.
path = transcript(user("pause"))
with open(path, "a", encoding="utf-8") as fh:
    fh.write("[" * 100000 + "]" * 100000 + "\n")
try:
    check("a too-deep record is skipped", is_paused({"transcript_path": path}) is True)
finally:
    os.unlink(path)

check("no transcript path means unpaused", is_paused({}) is False)
check("a missing transcript means unpaused",
      is_paused({"transcript_path": "/nonexistent/t.jsonl"}) is False)

# stop_notice: blocks when unpaused, never while paused.
tmp = tempfile.mkdtemp()
os.environ["TMPDIR"] = tmp
tempfile.tempdir = tmp
paused = transcript(user("fix it"), user("pause"))
running = transcript(user("pause"), user("go on"))
try:
    out = json.loads(stop_notice({"transcript_path": running, "session_id": "s1"},
                                 "push it", "test-hook"))
    check("stop_notice blocks an unpaused session", out.get("decision") == "block")
    out = json.loads(stop_notice({"transcript_path": paused, "session_id": "s2"},
                                 "push it", "test-hook"))
    check("stop_notice does not block a paused session", "decision" not in out)
    check("the paused note still reaches the user", out.get("systemMessage") == "push it")
finally:
    os.unlink(paused)
    os.unlink(running)

if FAILURES:
    print(f"\n{len(FAILURES)} failure(s)")
    sys.exit(1)
print("\nall passed")
