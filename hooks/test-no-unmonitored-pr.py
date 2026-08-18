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
finally:
    os.unlink(opened)
    os.unlink(scheduled)
print("PASS: detects an unmonitored PR and gives each PR a stable timer state file")
