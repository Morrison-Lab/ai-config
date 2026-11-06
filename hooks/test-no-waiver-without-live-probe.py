#!/usr/bin/env python3
"""Tests for hooks/no-waiver-without-live-probe.py (ai-config#5018).

Run: python3 hooks/test-no-waiver-without-live-probe.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.realpath(__file__)), "no-waiver-without-live-probe.py")
POST = "mcp__hearthbot__post_message"
WAIVE = "The cross-harness review is waived: agy and OpenCode quotas are exhausted."


def human(text="go"):
    return {"type": "user", "message": {"content": text}}


def bash(i, cmd, out="ok"):
    return [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": cmd}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": out}]}},
    ]


def relay(i, tool, out):
    return [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"t{i}", "name": tool, "input": {}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": out}]}},
    ]


def run(tool, text, recs, field="text"):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    payload = {"tool_name": tool, "tool_input": {field: text}, "transcript_path": path}
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    os.unlink(path)
    assert p.returncode == 0, p.stderr
    return '"permissionDecision": "deny"' in p.stdout


AGY = bash(1, "ssh cf463-02 'agy -p ok'", "pong")
OC = bash(2, "opencode run -m kimi-k3 ok", "GoUsageLimitError")
CURL = bash(3, "curl -s https://opencode.ai/zen/go/v1/chat/completions -d '{}'", "{}")

CASES = [
    ("waiver with no probe", POST, WAIVE, [human()], True),
    ("waiver from a note only", POST, "Review waived; the memory note says OpenCode is exhausted.", [human()], True),
    ("relay to coordinator", "mcp__hearthbot__message_coordinator", WAIVE, [human()], True),
    ("probe of both, CLI", POST, WAIVE, [human()] + AGY + OC, False),
    ("probe of both, agy + curl", POST, WAIVE, [human()] + AGY + CURL, False),
    ("probe of one only", POST, WAIVE, [human()] + OC, True),
    ("version flag does not count", POST, WAIVE, [human()] + bash(1, "agy --version") + OC, True),
    ("probe before the latest human turn does not count", POST, WAIVE, [human()] + AGY + OC + [human("again")], True),
    ("relayed probe counts", POST, WAIVE, [human()] + relay(1, "mcp__hearthbot__read_thread", "RC probe: agy models ok; opencode GoUsageLimitError"), False),
    ("relayed text without probe output", POST, WAIVE, [human()] + relay(1, "mcp__hearthbot__read_thread", "agy and opencode are on the list"), True),
    ("not exhausted is no claim", POST, "agy is not exhausted, so I ran it.", [human()], False),
    ("unrelated unavailable", POST, "The runner is unavailable until 5pm.", [human()], False),
    ("unrelated tool", "Bash", WAIVE, [human()], False),
    ("forge comment is out of scope", "mcp__github__add_issue_comment", WAIVE, [human()], False),
]


def main():
    fails = 0
    for name, tool, text, recs, deny in CASES:
        field = "body" if tool.startswith("mcp__github__") else "text"
        got = run(tool, text, recs, field)
        ok = got == deny
        print(("  ok      " if ok else "  FAIL    ") + name)
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
