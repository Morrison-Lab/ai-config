#!/usr/bin/env python3
"""Tests for scripts/lib/agent_notice.py (ai-config#4796).

Pins the two properties the helper exists for:
  1. A Stop hook's warning reaches the agent: the first call in a turn blocks,
     with the message as the `reason`, and keeps a `systemMessage` copy.
  2. It can never wedge a session: at most one block per hook per turn, and
     none while `stop_hook_active` is set; a non-blocking call still shows the
     user the message.
Plus the shape of `context_notice`, which must not deny the tool call.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
os.environ["TMPDIR"] = tempfile.mkdtemp()
tempfile.tempdir = None  # re-read TMPDIR so sentinels land in the fresh dir

import agent_notice  # noqa: E402

passes = 0
failures = 0


def check(name, got, want):
    global passes, failures
    if got == want:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}: got {got!r}, want {want!r}")
        failures += 1


def stop(payload, message="warn", hook="h1"):
    return json.loads(agent_notice.stop_notice(payload, message, hook))


turn = {"session_id": "s1", "prompt_id": "p1"}

first = stop(turn)
check("first warning in a turn blocks", first.get("decision"), "block")
check("the block's reason is the message", first.get("reason"), "warn")
check("the user keeps a systemMessage copy", first.get("systemMessage"), "warn")

second = stop(turn, message="another warning")
check("a second warning from the same hook in the turn does not block",
      "decision" in second, False)
check("...but still shows the user the message", second.get("systemMessage"),
      "another warning")
check("...and emits no orphan reason", "reason" in second, False)

other_hook = stop(turn, hook="h2")
check("a different hook in the same turn blocks once too",
      other_hook.get("decision"), "block")

next_turn = stop({"session_id": "s1", "prompt_id": "p2"})
check("the next turn blocks again", next_turn.get("decision"), "block")

continuing = stop({"session_id": "s1", "prompt_id": "p3", "stop_hook_active": True})
check("a stop that continues an earlier block never blocks",
      "decision" in continuing, False)
check("...and still shows the user the message", continuing.get("systemMessage"), "warn")

other_session = stop({"session_id": "s2", "prompt_id": "p1"})
check("another session's turn with the same id blocks independently",
      other_session.get("decision"), "block")

ctx = json.loads(agent_notice.context_notice("look first"))
check("context_notice puts the message where the model reads it",
      ctx.get("hookSpecificOutput", {}).get("additionalContext"), "look first")
check("context_notice names its event", ctx["hookSpecificOutput"].get("hookEventName"), "PreToolUse")
check("context_notice keeps a systemMessage copy", ctx.get("systemMessage"), "look first")
check("context_notice never denies the tool call",
      "permissionDecision" in ctx["hookSpecificOutput"] or "decision" in ctx, False)
check("context_notice takes the event name",
      json.loads(agent_notice.context_notice("x", "PostToolUse"))["hookSpecificOutput"]["hookEventName"],
      "PostToolUse")

print(f"\n{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
