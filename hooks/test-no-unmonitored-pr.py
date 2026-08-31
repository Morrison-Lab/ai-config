#!/usr/bin/env python3
"""Regression tests for no-unmonitored-pr.py."""
import importlib.util
import json
import os
import sys
import tempfile

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def transcript(blocks):
    handle, path = tempfile.mkstemp()
    with os.fdopen(handle, "w") as stream:
        for block in blocks:
            stream.write(json.dumps({"type": "assistant", "message": {"content": [block]}}) + "\n")
    return path


opened = transcript([{"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create"}}])
scheduled = transcript([{"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create"}}, {"type": "tool_use", "name": "ScheduleWakeup", "input": {"after": "2m"}}])

# Antigravity transcript
def antigravity_transcript(records_list):
    handle, path = tempfile.mkstemp()
    with os.fdopen(handle, "w") as stream:
        for rec in records_list:
            stream.write(json.dumps(rec) + "\n")
    return path

ag_opened = antigravity_transcript([
    {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "gh pr create"}}]}
])
ag_scheduled = antigravity_transcript([
    {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "gh pr create"}}]},
    {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "schedule", "args": {"DurationSeconds": 120}}]}
])

try:
    assert subject.pending(opened)
    assert not subject.pending(scheduled)
    assert subject.pending(ag_opened)
    assert not subject.pending(ag_scheduled)
    assert subject.monitor_path("https://github.com/o/r/pull/1") == subject.monitor_path("https://github.com/o/r/pull/1")
    assert subject.monitor_path("https://github.com/o/r/pull/1") != subject.monitor_path("https://github.com/o/r/pull/2")

    # Verify extract_pr_urls
    multi_pr = transcript([
        {"type": "tool_use", "name": "Bash", "input": {"command": "gh pr view 999"}},
        {"type": "tool_result", "content": "https://github.com/o/r/pull/999"},
        {"type": "text", "text": "See also https://github.com/o/r/pull/888"},
        {"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create --title 'A'"}},
        {"type": "tool_result", "content": "https://github.com/o/r/pull/10"},
        {"type": "tool_use", "name": "Bash", "input": {"command": "gh pr create --title 'B'"}},
        {"type": "tool_result", "content": "https://github.com/o/r/pull/20"}
    ])
    ag_multi_pr = antigravity_transcript([
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "gh pr create --title 'A'"}}]},
        {"source": "MODEL", "type": "GENERIC", "content": "https://github.com/o/r/pull/30"},
        {"source": "MODEL", "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "run_command", "args": {"CommandLine": "gh pr create --title 'B'"}}]},
        {"source": "MODEL", "type": "GENERIC", "content": "https://github.com/o/r/pull/40"}
    ])
    try:
        urls = subject.extract_pr_urls(multi_pr)
        assert urls == ["https://github.com/o/r/pull/10", "https://github.com/o/r/pull/20"], f"Got {urls}"
        ag_urls = subject.extract_pr_urls(ag_multi_pr)
        assert ag_urls == ["https://github.com/o/r/pull/30", "https://github.com/o/r/pull/40"], f"Got {ag_urls}"
    finally:
        os.unlink(multi_pr)
        os.unlink(ag_multi_pr)

    # Verify start_monitor_for_url early return when already alive
    orig_state_dir = subject.STATE_DIR
    with tempfile.TemporaryDirectory() as d:
        subject.STATE_DIR = d
        url1 = "https://github.com/o/r/pull/1"
        url2 = "https://github.com/o/r/pull/2"
        p1 = subject.monitor_path(url1)
        subject.write_json(p1, {"url": url1, "pid": os.getpid()})
        # url1 is alive -> returns False without error
        assert subject.start_monitor_for_url(url1, d) is False
        # url2 is not alive -> attempts to start (or starts)
        p2 = subject.monitor_path(url2)
        assert not os.path.exists(p2)
        # Verify PR 2 gets its own distinct state path and is not shadowed by PR 1
        assert p1 != p2
finally:
    os.unlink(opened)
    os.unlink(scheduled)
    os.unlink(ag_opened)
    os.unlink(ag_scheduled)

print("PASS: detects an unmonitored PR and gives each PR a stable timer state file")
