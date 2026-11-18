#!/usr/bin/env python3
"""Tests for hooks/require-pr-read-before-resolve.py (ai-config#5806).

Run: python3 hooks/test-require-pr-read-before-resolve.py [hooks/require-pr-read-before-resolve.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "require-pr-read-before-resolve.py")
RESOLVE = "mcp__hearthbot__set_thread_resolved"
LIST = "mcp__hearthbot__list_threads"
TID = "cmsg_014QLd5McmoUEgMPRiXeVnjS8Vww6PuiqjsHxn7zK891Nf"

USER = {"type": "user", "message": {"role": "user", "content": "sweep idle threads"}}


def call(args, uid="u1"):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": uid, "name": LIST, "input": args}]}}


def result(text, uid="u1"):
    return {"type": "user", "isMeta": True, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": uid, "content": text}]}}


OPEN_ROW = f'{{"id": "{TID}", "title": "Add psw rule", "state": "done", "pull_requests": [{{"number": 2623, "state": "open"}}]}}'
MERGED_ROW = f'{{"id": "{TID}", "title": "Add psw rule", "state": "done", "pull_requests": [{{"number": 2623, "state": "merged"}}]}}'
NO_PR_ROW = f'{{"id": "{TID}", "title": "Add psw rule", "state": "done", "pull_requests": []}}'

# (name, tool_input, transcript entries or None, should_deny)
CASES = [
    ("no list_threads read", {"resolved": True, "thread_id": TID}, [USER], True),
    ("list_threads without include_pull_requests", {"resolved": True, "thread_id": TID},
     [USER, call({"state": "done"}), result(NO_PR_ROW)], True),
    ("read before the last user turn does not count", {"resolved": True, "thread_id": TID},
     [call({"include_pull_requests": True}), result(NO_PR_ROW), USER], True),
    ("row shows an open PR", {"resolved": True, "thread_id": TID},
     [USER, call({"include_pull_requests": True}), result(OPEN_ROW)], True),
    ("row shows a merged PR", {"resolved": True, "thread_id": TID},
     [USER, call({"include_pull_requests": True}), result(MERGED_ROW)], False),
    ("row shows no PR", {"resolved": True, "thread_id": TID},
     [USER, call({"include_pull_requests": True}), result(NO_PR_ROW)], False),
    ("own-thread resolve with a read", {"resolved": True},
     [USER, call({"include_pull_requests": True}), result(NO_PR_ROW)], False),
    ("resolved false is not checked", {"resolved": False, "thread_id": TID}, [USER], False),
    ("no transcript path", {"resolved": True, "thread_id": TID}, None, False),
]


def run(tool_input, entries):
    payload = {"tool_name": RESOLVE, "tool_input": tool_input}
    path = None
    if entries is not None:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(e) + "\n" for e in entries))
        payload["transcript_path"] = path
    try:
        p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                           capture_output=True, text=True)
    finally:
        if path:
            os.unlink(path)
    return p.returncode, p.stdout


def main():
    fails = 0
    for name, tool_input, entries, deny in CASES:
        rc, out = run(tool_input, entries)
        denied = '"permissionDecision": "deny"' in out
        ok = rc == 0 and denied == deny
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
