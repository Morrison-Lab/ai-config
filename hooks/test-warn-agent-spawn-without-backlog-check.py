#!/usr/bin/env python3
"""Tests for warn-agent-spawn-without-backlog-check.py.

The negative cases carry the weight: a reminder that fires after a search ran,
on a read-only searcher, or twice in one session gets switched off.

Run: python3 hooks/test-warn-agent-spawn-without-backlog-check.py
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HOOK = str(pathlib.Path(__file__).resolve().parent / "warn-agent-spawn-without-backlog-check.py")


def use(name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}


def run(events, tool="Agent", subagent="general-purpose", session=None):
    session = session or os.urandom(6).hex()
    with tempfile.TemporaryDirectory() as d:
        tp = os.path.join(d, "t.jsonl")
        with open(tp, "w", encoding="utf-8") as fh:
            for ev in events:
                fh.write(json.dumps(ev) + "\n")
        payload = {"tool_name": tool, "tool_input": {"subagent_type": subagent},
                   "transcript_path": tp, "session_id": session}
        out = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                             capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    if not out.stdout.strip():
        return False
    ctx = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    return "triage-new-asks" in ctx


CASES = [
    ("no query, general-purpose agent warns", dict(events=[use("Bash", command="ls")]), True),
    ("no query, Task warns", dict(events=[], tool="Task"), True),
    ("MCP issue search discharges", dict(events=[use("mcp__github__search_issues", query="x")]), False),
    ("MCP PR list discharges", dict(events=[use("mcp__github__list_pull_requests", owner="o")]), False),
    ("gh issue list discharges", dict(events=[use("Bash", command="gh issue list --state all --search x")]), False),
    ("gh pr list after && discharges", dict(events=[use("Bash", command="cd r && gh pr list")]), False),
    ("quoted gh issue list in an echo does not discharge",
     dict(events=[use("Bash", command="echo 'gh issue list'")]), True),
    ("read-only Explore agent is exempt", dict(events=[], subagent="Explore"), False),
    ("non-Agent tool is ignored", dict(events=[], tool="Bash"), False),
]


def main():
    bad = 0
    for label, kw, want in CASES:
        got = run(**kw)
        if got != want:
            bad += 1
            print(f"FAIL {label}: warned={got}, want {want}")
    sid = os.urandom(6).hex()
    first, second = run([], session=sid), run([], session=sid)
    if not (first and not second):
        bad += 1
        print(f"FAIL once per session: first={first} second={second}")
    print(f"{len(CASES) + 1 - bad}/{len(CASES) + 1} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
