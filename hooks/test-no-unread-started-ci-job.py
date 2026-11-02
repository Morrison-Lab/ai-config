#!/usr/bin/env python3
"""Regression test for no-unread-started-ci-job.py (ai-config#4873)."""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1]


def prompt(text="go"):
    return {"type": "user", "message": {"content": [{"type": "text", "text": text}]}}


def call(name, **inputs):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inputs}]}}


def result():
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


RERUN = call("mcp__github__actions_run_trigger", method="rerun_failed_jobs", run_id=1)
BASH_RERUN = call("Bash", command="gh run rerun 123 --failed")
READ = call("mcp__github__actions_get", method="get_workflow_run", run_id=1)
BASH_READ = call("Bash", command="gh run watch 123")
WAKE = call("mcp__claude-code-remote__send_later", message="check", delay_minutes=5)


def run(records, active=False):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "t.jsonl")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write("\n".join(json.dumps(r) for r in records))
        payload = json.dumps({"transcript_path": path, "session_id": "s" + str(id(records)),
                              "stop_hook_active": active})
        env = dict(os.environ, TMPDIR=tmp)
        return subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                              text=True, env=env, check=True).stdout


def check(label, records, blocks, active=False):
    out = run(records, active)
    got = bool(out.strip()) and json.loads(out).get("decision") == "block"
    assert got == blocks, f"{label}: got {out!r}"
    print(f"PASS: {label}")


check("rerun with no read blocks", [prompt(), RERUN, result()], True)
check("gh run rerun with no read blocks", [prompt(), BASH_RERUN, result()], True)
check("scheduling a wake is not a read", [prompt(), RERUN, result(), WAKE, result()], True)
check("read after the rerun is fine", [prompt(), RERUN, result(), READ, result()], False)
check("gh run watch after the rerun is fine", [prompt(), BASH_RERUN, BASH_READ], False)
check("a read before the rerun does not count", [prompt(), READ, RERUN, result()], True)
check("a rerun in an earlier turn is not this turn's", [prompt(), RERUN, result(), prompt("next")], False)
check("no job started is silent", [prompt(), READ], False)
check("stop_hook_active never blocks again", [prompt(), RERUN, result()], False, active=True)
