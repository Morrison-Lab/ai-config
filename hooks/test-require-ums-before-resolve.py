#!/usr/bin/env python3
"""Tests for hooks/require-ums-before-resolve.py (ai-config#4480).

Run: python3 hooks/test-require-ums-before-resolve.py [path-to-hook]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "require-ums-before-resolve.py")
RESOLVE = "mcp__hearthbot__set_thread_resolved"


def user(text):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def result():
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}}


def tool(name, inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp}]}}


def run(records, payload_extra, sentinel_dir, times=1):
    fd, tpath = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    outs = []
    try:
        for _ in range(times):
            payload = dict(payload_extra, transcript_path=tpath)
            p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                               capture_output=True, text=True,
                               env=dict(os.environ, TMPDIR=sentinel_dir))
            if p.returncode != 0:
                sys.exit(f"FATAL: exit {p.returncode}\n{p.stderr}")
            outs.append(p.stdout.strip())
    finally:
        os.unlink(tpath)
    return outs if times > 1 else outs[0]


def resolve(resolved=True, thread="cmsg_1"):
    return {"hook_event_name": "PreToolUse", "tool_name": RESOLVE,
            "tool_input": {"resolved": resolved, "thread_id": thread}}


failures = 0


def check(desc, ok):
    global failures
    failures += not ok
    print(f"  {'ok' if ok else 'WRONG':<6} {desc}")


def fresh():
    return tempfile.mkdtemp()


work = [user("fix the bug"), tool("Edit", {"file_path": "/r/x.py"})]
print("PreToolUse on set_thread_resolved:")
sd = fresh()
out = run(work, resolve(), sd)
check("denied when no UMS since the last user message", '"deny"' in out)
sd = fresh()
outs = run(work, resolve(), sd, times=2)
check("second attempt is allowed (one refusal per thread)", '"deny"' in outs[0] and outs[1] == "")
sd = fresh()
check("a different thread is refused again",
      '"deny"' in run(work, resolve(thread="cmsg_A"), sd)
      and '"deny"' in run(work, resolve(thread="cmsg_B"), sd))
for desc, rec in [
    ("Skill ums", tool("Skill", {"skill": "ums"})),
    ("Agent prompt naming UMS", tool("Agent", {"prompt": "Run UMS on this thread"})),
    ("Bash invoking update-memories-and-skills", tool("Bash", {"command": "echo update memories"})),
    ("Write under ai-config", tool("Write", {"file_path": "/h/ai-config/shared/x.md"})),
]:
    check(f"allowed after {desc}", run(work + [rec], resolve(), fresh()) == "")
check("UMS before the last user message does not count",
      '"deny"' in run([tool("Skill", {"skill": "ums"}), user("more work")], resolve(), fresh()))
check("a tool_result record is not a user message",
      run([user("go"), tool("Skill", {"skill": "ums"}), result()], resolve(), fresh()) == "")
check("resolved:false (reopen) is not gated", run(work, resolve(resolved=False), fresh()) == "")
check("another tool is ignored",
      run(work, {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                 "tool_input": {"command": "ls"}}, fresh()) == "")
check("missing transcript fails open",
      subprocess.run([sys.executable, HOOK], input=json.dumps(
          dict(resolve(), transcript_path="/nonexistent")), capture_output=True,
          text=True).stdout == "")
for raw in ("", "not json", "[1]"):
    p = subprocess.run([sys.executable, HOOK], input=raw, capture_output=True, text=True)
    check(f"malformed stdin {raw!r} is silent", p.returncode == 0 and p.stdout == "")

print("UserPromptSubmit merge event:")
merged = ('<wake reason="external-event"><event source="github" kind="pull_request_merged">'
          '{"number": 4480}</event></wake>')
other = ('<wake reason="external-event"><event source="github" kind="check_run">'
         '{"conclusion": "success"}</event></wake>')
sd = fresh()
outs = run([], {"hook_event_name": "UserPromptSubmit", "prompt": merged}, sd, times=2)
check("merge event reminds once", "post-merge" in outs[0] and outs[1] == "")
check("a CI event does not remind",
      run([], {"hook_event_name": "UserPromptSubmit", "prompt": other}, fresh()) == "")
check("the word merged in plain chat does not remind",
      run([], {"hook_event_name": "UserPromptSubmit", "prompt": "the PR merged yesterday"}, fresh()) == "")
check("state merged inside event JSON reminds",
      "post-merge" in run([], {"hook_event_name": "UserPromptSubmit", "prompt":
          '<event source="github" kind="pull_request">{"state": "merged"}</event>'}, fresh()))

print(f"\n{'FAILED' if failures else 'all passed'}: {failures} wrong")
sys.exit(1 if failures else 0)
