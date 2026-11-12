#!/usr/bin/env python3
"""Tests for hooks/no-thread-model-claim-without-get-session.py.

Run: python3 hooks/test-no-thread-model-claim-without-get-session.py [path-to-hook]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "no-thread-model-claim-without-get-session.py")
if not os.path.isfile(HOOK):
    sys.exit(f"FATAL: hook not found at {HOOK}")
POST = "mcp__hearthbot__post_message"
CLAIM = "Every thread is now off Fable and running on claude-opus-5-5."


def user(text):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def result():
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}}


def tool(name, inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}


def run(records, name, text, times=1):
    td = tempfile.mkdtemp()
    path = os.path.join(td, "t.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    outs = []
    try:
        for _ in range(times):
            p = subprocess.run(
                [sys.executable, HOOK],
                input=json.dumps({"transcript_path": path, "tool_name": name,
                                  "tool_input": {"text": text}}),
                capture_output=True, text=True,
                env=dict(os.environ, TMPDIR=td, TEMP=td, TMP=td))
            assert p.returncode == 0, p.stderr
            outs.append('"deny"' in p.stdout)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    return outs


ASK = [user("switch every thread off fable")]
CASES = [
    (run(ASK, POST, CLAIM), [True], "a thread-model claim with no get_session is denied"),
    (run(ASK, POST, CLAIM, times=2), [True, False], "the retry in the same turn is allowed"),
    (run(ASK + [tool("mcp__claude-code-remote__get_session", {"session_id": "session_1"}), result()],
         POST, CLAIM), [False], "a get_session call since the user message clears it"),
    (run([tool("mcp__claude-code-remote__get_session", {}), result()] + ASK, POST, CLAIM),
     [True], "a get_session call before the user message does not clear it"),
    (run(ASK, "mcp__hearthbot__message_coordinator", CLAIM), [True],
     "message_coordinator is checked too"),
    (run(ASK, POST, "The thread is done.\n\nOpus reviewed the PR."), [False],
     "thread and model in different paragraphs pass"),
    (run(ASK, POST, "Merged the PR; the thread is resolved."), [False],
     "a thread with no model named passes"),
    (run(ASK, POST, "Ran `get_session` on the `opus` thread."), [False],
     "names inside inline code are ignored"),
    (run(ASK, "mcp__github__add_issue_comment", CLAIM), [False],
     "a non-reply tool is out of scope"),
]

fails = 0
for got, want, label in CASES:
    ok = got == want
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}: {label}" + ("" if ok else f" (got {got}, want {want})"))
print(f"\n{len(CASES) - fails} passed, {fails} failed")
sys.exit(1 if fails else 0)
