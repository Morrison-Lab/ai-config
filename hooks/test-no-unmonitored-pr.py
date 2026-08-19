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
try:
    assert subject.pending(opened)
    assert not subject.pending(scheduled)
    assert subject.monitor_path("https://github.com/o/r/pull/1") == subject.monitor_path("https://github.com/o/r/pull/1")
    assert subject.monitor_path("https://github.com/o/r/pull/1") != subject.monitor_path("https://github.com/o/r/pull/2")
    assert subject.cwd_monitor_path("/foo/bar") == subject.cwd_monitor_path("/foo/bar")
    assert subject.cwd_monitor_path("/foo/bar") != subject.cwd_monitor_path("/foo/baz")

    # Verify start_monitor early return without pr_url call when cwd monitor is alive
    orig_state_dir = subject.STATE_DIR
    with tempfile.TemporaryDirectory() as d:
        subject.STATE_DIR = d
        cwd_state = subject.cwd_monitor_path(d)
        subject.write_json(cwd_state, {"pid": os.getpid()})
        # Monkeypatch pr_url to raise if called
        orig_pr_url = subject.pr_url
        subject.pr_url = lambda cwd: (_ for _ in ()).throw(AssertionError("pr_url should not be called"))
        try:
            assert subject.start_monitor(d) is False
        finally:
            subject.pr_url = orig_pr_url
            subject.STATE_DIR = orig_state_dir
finally:
    os.unlink(opened)
    os.unlink(scheduled)
print("PASS: detects an unmonitored PR and gives each PR a stable timer state file")
