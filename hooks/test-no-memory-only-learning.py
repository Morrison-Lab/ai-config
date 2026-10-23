#!/usr/bin/env python3
"""Tests for hooks/no-memory-only-learning.py (ai-config#4698).

Run: python3 hooks/test-no-memory-only-learning.py [hooks/no-memory-only-learning.py]
"""
import json
import os
import subprocess
import sys
import tempfile
import uuid

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-memory-only-learning.py")
MEM = "/tmp/claude/memory/team/silo/MEMORY.md"


def user(text):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def tool(name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}


def say(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


# (events, should_block, label)
CASES = [
    ([user("learn this"), tool("Write", file_path=MEM)], True, "memory only"),
    ([user("learn this"), tool("Edit", file_path="/x/memory/a.md")], True, "memory dir edit only"),
    ([user("learn this"), tool("Write", file_path=MEM), tool("Write", file_path="/r/ai-config/hooks/x.py")],
     False, "hook written too"),
    ([user("learn this"), tool("Write", file_path=MEM), tool("Write", file_path="/r/ai-config/shared/workflow/a.md")],
     False, "shared fragment written too"),
    ([user("learn this"), tool("Write", file_path=MEM), tool("mcp__github__issue_write", title="x")],
     False, "issue filed"),
    ([user("learn this"), tool("Write", file_path=MEM), say("Done.\nMechanism: https://github.com/o/r/pull/1")],
     False, "mechanism cited"),
    ([user("learn this"), tool("Write", file_path=MEM), say("memory only: a one-off device path")],
     False, "memory-only reason stated"),
    ([user("old"), tool("Write", file_path=MEM), say("ok"), user("next"), say("hi")], False,
     "an earlier turn's memory write is not this turn's"),
    ([user("hi"), say("hello")], False, "no memory write"),
]


def run(events):
    path = os.path.join(tempfile.gettempdir(), f"test-nmol-{uuid.uuid4().hex}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    try:
        p = subprocess.run([sys.executable, HOOK], input=json.dumps({"transcript_path": path}),
                           capture_output=True, text=True)
    finally:
        os.remove(path)
    return p.returncode, p.stdout


def main():
    fails = 0
    for events, block, label in CASES:
        rc, out = run(events)
        blocked = '"decision": "block"' in out
        ok = rc == 0 and blocked == block
        print(("  ok      " if ok else "  FAIL    ") + label)
        fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
