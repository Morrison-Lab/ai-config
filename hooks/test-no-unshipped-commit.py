#!/usr/bin/env python3
"""Regression tests for no-unshipped-commit.py."""
import importlib.util
import json
import os
import sys
import tempfile

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def transcript(commands):
    handle, path = tempfile.mkstemp()
    with os.fdopen(handle, "w") as stream:
        for command in commands:
            record = {"type": "assistant", "message": {"content": [{
                "type": "tool_use", "name": "Bash", "input": {"command": command}
            }]}}
            stream.write(json.dumps(record) + "\n")
    return path


unshipped = transcript(["git commit -m hook"])
pushed = transcript(["git commit -m hook", "git push origin branch"])
pr_opened = transcript(["git commit -m hook", "gh pr create --fill"])
try:
    assert subject.pending_commit(unshipped) == "git commit -m hook"
    assert subject.pending_commit(pushed) is None
    assert subject.pending_commit(pr_opened) is None
finally:
    os.unlink(unshipped)
    os.unlink(pushed)
    os.unlink(pr_opened)
print("PASS: an unshipped commit blocks, while push and PR creation discharge it")
