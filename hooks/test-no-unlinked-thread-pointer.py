#!/usr/bin/env python3
"""Tests for hooks/no-unlinked-thread-pointer.py (ai-config#4590).

Run: python3 hooks/test-no-unlinked-thread-pointer.py [hooks/no-unlinked-thread-pointer.py]
"""
import json
import os
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "no-unlinked-thread-pointer.py")
REPLY = "mcp__hearthbot__reply"
POST = "mcp__hearthbot__post_message"
L = "[Fix the lint](#cmsg_01A)"

# (name, tool, text, expected phrase quoted in the denial; None = silent)
CASES = [
    ("each in its thread", POST, "Merge words needed, each in its thread.", "in its thread"),
    ("in that thread", POST, "Say yes in that thread.", "in that thread"),
    ("in its thread", REPLY, "Answer in its thread.", "in its thread"),
    ("update_message", "mcp__hearthbot__update_message", "Reply in its thread.", "in its thread"),
    ("their threads", POST, "Reply in their threads.", "in their threads"),
    ("in each thread", POST, "Confirm in each thread.", "in each thread"),
    ("own", POST, "Answer in its own thread.", "in its own thread"),
    ("relevant thread", POST, "Post it in the relevant thread.", "in the relevant thread"),
    ("capitalised", POST, "In Its Thread please.", "In Its Thread"),
    ("one word between", POST, "Reply in its PR thread.", "in its PR thread"),
    ("linked in same paragraph", POST, f"Say yes in its thread, {L}.", None),
    ("linked in a later sentence", POST, f"Say yes in its thread. See {L}.", None),
    ("thread URL outside the app", POST,
     "In its thread: https://claude.ai/code/project/c?thread=cmsg_01Pz", None),
    ("link in a different paragraph", POST, f"Say yes in its thread.\n\n{L}", "in its thread"),
    ("each item has its own link", POST,
     f"- a: in its thread {L}\n- b: in its thread [Other](#cmsg_01B)", None),
    ("second item unlinked", POST,
     f"- a: in its thread {L}\n- b: in its thread", "in its thread"),
    ("one link at the bottom covers only its item", POST,
     f"- a: in its thread\n- b: in its thread\n- c: in its thread {L}", "in its thread"),
    ("nested link covers parent", POST, f"- a in its thread\n  - {L}", None),
    ("in this thread is not a pointer", POST, "I will answer in this thread.", None),
    ("no pointer", POST, "Done.", None),
    ("inline code", POST, "The phrase `in its thread` is blocked.", None),
    ("fenced code", POST, "```\nin its thread\n```\nDone.", None),
    ("unclosed fence", POST, "```\nin its thread\nmore", None),
    ("other tool", "Bash", "echo in its thread", None),
    ("CRLF paragraphs", POST, f"Say yes in its thread.\r\n\r\n{L}", "in its thread"),
    ("within is not in", POST, "It is within its threads of work.", None),
]


def run(tool, text):
    event = {"tool_name": tool, "tool_input": {"text": text}}
    proc = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


def main():
    failures = 0
    for name, tool, text, expected in CASES:
        code, out = run(tool, text)
        ok = code == 0
        if expected is None:
            ok = ok and out == ""
        else:
            hso = json.loads(out)["hookSpecificOutput"] if out else {}
            reason = hso.get("permissionDecisionReason", "")
            ok = (ok and hso.get("permissionDecision") == "deny"
                  and f'says "{expected}" without' in reason)
        if not ok:
            failures += 1
            print(f"FAIL {name}: code={code} out={out!r}")
    for bad in ("", "not json", "[]", json.dumps({"tool_name": REPLY, "tool_input": []}),
                json.dumps({"tool_name": REPLY, "tool_input": {"text": 5}})):
        proc = subprocess.run([sys.executable, HOOK], input=bad,
                              capture_output=True, text=True)
        if proc.returncode != 0 or proc.stdout:
            failures += 1
            print(f"FAIL malformed input {bad!r}")
    print("ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
