#!/usr/bin/env python3
"""Regression test for warn-overdue-scheduled-wake.py (ai-config#4873)."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]
NOW = "2026-11-02T17:00:00Z"
ID = "trig_0139YsD7HeQFDRhgCvXKk1bh"


def armed(due="2026-11-02T15:56:00Z"):
    text = json.dumps({"fire_at": due, "now": "2026-11-02T15:40:00Z", "trigger_id": ID})
    return {"type": "user", "timestamp": "2026-11-02T15:40:11Z", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1",
         "content": [{"type": "text", "text": text}]}]}}


ARM_USE = {"type": "assistant", "timestamp": "2026-11-02T15:40:10Z", "message": {"content": [
    {"type": "tool_use", "id": "t1", "name": "mcp__x__send_later", "input": {}}]}}


def tool_use(name, when, **inputs):
    return {"type": "assistant", "timestamp": when, "message": {"content": [
        {"type": "tool_use", "name": name, "input": inputs}]}}


def run(records, session, shared=None):
    records = [ARM_USE] + records
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.jsonl")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write("\n".join(json.dumps(r) for r in records))
        env = dict(os.environ, OVERDUE_WAKE_NOW=NOW, TMPDIR=shared or tmp)
        payload = json.dumps({"transcript_path": path, "session_id": session})
        out = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                             text=True, env=env, check=True)
        return out.stdout


def check(label, records, expect_warning):
    out = run(records, label)
    assert bool(out.strip()) == expect_warning, f"{label}: got {out!r}"
    if expect_warning:
        assert ID in json.loads(out)["hookSpecificOutput"]["additionalContext"], label
    print(f"PASS: {label}")


check("overdue and never checked warns", [armed()], True)
check("not yet due is silent", [armed("2026-11-02T17:30:00Z")], False)
check("within grace is silent", [armed("2026-11-02T16:50:00Z")], False)
check("get_trigger after due is silent",
      [armed(), tool_use("mcp__x__get_trigger", "2026-11-02T16:00:00Z", trigger_id=ID)], False)
check("get_trigger for another id still warns",
      [armed(), tool_use("mcp__x__get_trigger", "2026-11-02T16:00:00Z", trigger_id="trig_other")], True)
check("list_triggers after due is silent",
      [armed(), tool_use("mcp__x__list_triggers", "2026-11-02T16:00:00Z")], False)
check("check made before the due time does not count",
      [armed(), tool_use("mcp__x__get_trigger", "2026-11-02T15:50:00Z", trigger_id=ID)], True)
check("scheduled continuation after due is silent",
      [armed(), {"type": "user", "isMeta": True, "promptSource": "sdk",
                 "timestamp": "2026-11-02T16:10:00Z", "message": {"content": "check"}}], False)

# A tool_result from another tool that merely looks like send_later output is ignored.
stray = armed()
stray["message"]["content"][0]["tool_use_id"] = "t2"
bash_use = {"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "t2", "name": "Bash", "input": {}}]}}
check("lookalike output from another tool is ignored", [bash_use, stray], False)

# Each task is reported once per session.
records = [armed()]
with tempfile.TemporaryDirectory() as shared:
    assert run(records, "once", shared)
    assert not run(records, "once", shared).strip(), "second run in one session must be silent"
print("PASS: reported once per session")
