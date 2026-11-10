#!/usr/bin/env python3
"""Tests for hooks/no-mwc-ask-in-other-thread-unread.py (ai-config#5013).

Run: python3 hooks/test-no-mwc-ask-in-other-thread-unread.py [hooks/no-mwc-ask-in-other-thread-unread.py]
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-mwc-ask-in-other-thread-unread.py")
POST = "mcp__hearthbot__post_message"
READ = "mcp__hearthbot__read_thread"

USER = {"type": "user", "message": {"role": "user", "content": "go ahead"}}


def call(name):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "t1", "name": name, "input": {}}]}}


# (name, tool, text, transcript entries or None for no transcript, should_deny)
ASKS_LINK = "Please type `mwc` in [HW 3 edits](#cmsg_014QLd5McmoUEgMPRiXeVnjS) for lds#1868."
ASKS_WORDS = "Type mwc in the HW 3 edits thread to merge it."
CASES = [
    ("link ask, no read", POST, ASKS_LINK, [USER], True),
    ("thread-word ask, no read", POST, ASKS_WORDS, [USER], True),
    ("link ask, thread read this turn", POST, ASKS_LINK, [USER, call(READ)], False),
    ("read before the last user turn does not count", POST, ASKS_LINK, [call(READ), USER], True),
    ("read by id counts", POST, ASKS_LINK, [USER, call("mcp__hearthbot__read_messages_by_id")], False),
    ("ask in this thread", POST, "Type `mwc` to merge both PRs.", [USER], False),
    ("no ask, mentions a thread", POST, "The work is in the HW 3 edits thread.", [USER], False),
    ("unrelated tool", "Bash", ASKS_LINK, [USER], False),
    ("no transcript path", POST, ASKS_LINK, None, False),
]


def run(tool, text, entries):
    payload = {"tool_name": tool, "tool_input": {"text": text}}
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
    for name, tool, text, entries, deny in CASES:
        rc, out = run(tool, text, entries)
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
