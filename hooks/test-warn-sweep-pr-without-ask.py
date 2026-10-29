#!/usr/bin/env python3
"""Tests for hooks/warn-sweep-pr-without-ask.py (ai-config#4829).

Run: python3 hooks/test-warn-sweep-pr-without-ask.py [hooks/warn-sweep-pr-without-ask.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "warn-sweep-pr-without-ask.py")


def run(payload):
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else None


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def mcp(title, body=""):
    return {"tool_name": "mcp__github__create_pull_request",
            "tool_input": {"title": title, "body": body}}


CASES = [
    ("title says sweep (gh)", bash('gh pr create --title "Sweep: one term per def" --body x'), True),
    ("short -t flag", bash("gh pr create -t 'Sweeping lds for the new rule' -b x"), True),
    ("title=value form", bash('gh pr create --title="sweep lds" --body x'), True),
    ("sweep label", bash('gh pr create --title "Fix defs" --label sweep --body x'), True),
    ("mcp title says sweep", mcp("Sweep existing chapters"), True),
    ("authorized line in body (gh)", bash(
        'gh pr create --title "Sweep: defs" --body "Sweep authorized: Ezra, cmsg_014QLd5M, \'sweep lds\'"'), False),
    ("authorized line in body (mcp)", mcp("Sweep: defs", "x\nSweep authorized: cmsg_014QLd5M"), False),
    ("empty marker still warns", bash('gh pr create --title "Sweep: x" --body "Sweep authorized: "'), True),
    ("glued -t form", bash("gh pr create -tSweep -b x"), True),
    ("comma labels", bash('gh pr create --title Fix --label a,sweep --body x'), True),
    ("plain title", bash('gh pr create --title "Fix the definition of bias" --body x'), False),
    ("word inside another word", bash('gh pr create --title "Chimneysweeper notes" --body x'), False),
    ("not a pr create", bash('echo "sweep"'), False),
    ("other tool", {"tool_name": "Read", "tool_input": {"file_path": "/sweep"}}, False),
    ("unbalanced quote falls back, no crash", bash("gh pr create --title 'Sweep it --body x"), True),
]


def main():
    bad = 0
    for name, payload, expect in CASES:
        got = run(payload)
        ok = (got is not None) == expect
        print(("ok  " if ok else "FAIL"), name)
        bad += not ok
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout.strip()
    print(("ok  " if ok else "FAIL"), "bad stdin fails open")
    bad += not ok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
