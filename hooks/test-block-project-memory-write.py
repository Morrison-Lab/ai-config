#!/usr/bin/env python3
"""Tests for hooks/block-project-memory-write.py.

Run: python3 hooks/test-block-project-memory-write.py [hooks/block-project-memory-write.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "block-project-memory-write.py")
STORE = "/tmp/claude/memory/team/silo/"

# (payload, should_block, label)
CASES = [
    ({"tool_name": "Write", "tool_input": {"file_path": STORE + "feedback-x.md"}}, True, "write a memory file"),
    ({"tool_name": "Edit", "tool_input": {"file_path": STORE + "feedback-x.md"}}, True, "edit a memory file"),
    ({"tool_name": "MultiEdit", "tool_input": {"file_path": STORE + "a.md"}}, True, "multi-edit a memory file"),
    ({"tool_name": "Write", "tool_input": {"file_path": STORE + "MEMORY.md"}}, False, "the MEMORY.md index is allowed"),
    ({"tool_name": "Write", "tool_input": {"file_path": "/home/user/lds/.claude/project-memory.md"}}, False,
     "a tracked repo file is allowed"),
    ({"tool_name": "Write", "tool_input": {"file_path": "/home/user/ai-config/memories/x.md"}}, False,
     "ai-config memories/ is allowed"),
    ({"tool_name": "Read", "tool_input": {"file_path": STORE + "feedback-x.md"}}, False, "reading is allowed"),
    ({"tool_name": "Bash", "tool_input": {"command": "echo hi"}}, False, "a Bash call is out of scope"),
]


def run(stdin):
    p = subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    fails = 0
    for payload, block, label in CASES:
        rc, out = run(json.dumps(payload))
        blocked = '"permissionDecision": "deny"' in out
        ok = rc == 0 and blocked == block
        print(("  ok      " if ok else "  FAIL    ") + label)
        fails += 0 if ok else 1
    rc, out = run("not json")
    ok = rc == 0 and not out
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 1
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
