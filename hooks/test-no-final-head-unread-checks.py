#!/usr/bin/env python3
"""Tests for hooks/no-final-head-unread-checks.py (ai-config#5198).

Run: python3 hooks/test-no-final-head-unread-checks.py [hooks/no-final-head-unread-checks.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-final-head-unread-checks.py")
COORD = "mcp__hearthbot__message_coordinator"
POST = "mcp__hearthbot__post_message"

USER = {"type": "user", "message": {"role": "user", "content": "check the PRs"}}


def call(name, tool_input=None, tid="t1"):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": name, "input": tool_input or {}}]}}


def result(text="total_count 20", is_error=False, tid="t1"):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "content": text, "is_error": is_error}]}}


RUNS_MCP = call("mcp__github__pull_request_read", {"method": "get_check_runs", "pullNumber": 5165})
RUNS_BASH = call("Bash", {"command": "gh api repos/o/r/commits/abc/check-runs?per_page=100"})
FULLY = call("Bash", {"command": "python3 scripts/check-pr-fully-clean.py 5165"})
OTHER_PR_READ = call("mcp__github__pull_request_read", {"method": "get", "pullNumber": 5165})
FINAL_MSG = "Final head: [ai-config#5165](https://github.com/Morrison-Lab/ai-config/pull/5165) at f592a252."
IS_FINAL = "ai-config#5173 at 1c28ea4b is final: review Clean, CI green."

# (name, tool, text, transcript entries or None for no transcript, should_deny)
CASES = [
    ("final head, no read", COORD, FINAL_MSG, [USER], True),
    ("is final, no read", POST, IS_FINAL, [USER], True),
    ("final head, MCP check-runs read", COORD, FINAL_MSG, [USER, RUNS_MCP, result()], False),
    ("final head, Bash check-runs read", COORD, FINAL_MSG, [USER, RUNS_BASH, result()], False),
    ("final head, fully-clean script", COORD, FINAL_MSG, [USER, FULLY, result()], False),
    ("read before the last user turn does not count", COORD, FINAL_MSG, [RUNS_MCP, result(), USER], True),
    ("a plain PR read is not a check-runs read", COORD, FINAL_MSG, [USER, OTHER_PR_READ], True),
    ("read with no result yet", COORD, FINAL_MSG, [USER, RUNS_MCP], True),
    ("read that errored", COORD, FINAL_MSG, [USER, RUNS_MCP, result(is_error=True)], True),
    ("read whose output is an HTTP error", COORD, FINAL_MSG, [USER, RUNS_BASH, result("HTTP 403: nope")], True),
    ("negated claim", COORD, "ai-config#5167 is not final yet: validate is running.", [USER], False),
    ("no PR cited", COORD, "The final head will be reported soon.", [USER], False),
    ("no final claim", COORD, "ai-config#5167: Clean review, CI running.", [USER], False),
    ("unrelated tool", "Bash", FINAL_MSG, [USER], False),
    ("no transcript path", COORD, FINAL_MSG, None, False),
]


def run(tool, text, entries, env=None):
    payload = {"tool_name": tool, "tool_input": {"text": text}}
    path = None
    if entries is not None:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(e) + "\n" for e in entries))
        payload["transcript_path"] = path
    try:
        p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                           capture_output=True, text=True, env=env)
    finally:
        if path:
            os.unlink(path)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool, text, entries, deny in CASES:
        rc, out = run(tool, text, entries)
        denied = '"permissionDecision": "deny"' in out
        ok = rc == 0 and denied == deny
        print(("  ok      " if ok else "  FAIL    ") + name)
        fails += 0 if ok else 1
    env = dict(os.environ, ALLOW_FINAL_HEAD="1")
    rc, out = run(COORD, FINAL_MSG, [USER], env=env)
    ok = rc == 0 and not out
    print(("  ok      " if ok else "  FAIL    ") + "ALLOW_FINAL_HEAD=1 overrides")
    fails += 0 if ok else 1
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    ok = p.returncode == 0 and not p.stdout
    print(("  ok      " if ok else "  FAIL    ") + "fails open on garbage stdin")
    fails += 0 if ok else 1
    total = len(CASES) + 2
    print(f"\n{total - fails}/{total} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
