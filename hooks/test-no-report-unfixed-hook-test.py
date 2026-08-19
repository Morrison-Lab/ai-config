#!/usr/bin/env python3
"""Regression tests for no-report-unfixed-hook-test.py."""
import importlib.util
import json
import os
import sys
import tempfile

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def scan(blocks):
    handle, path = tempfile.mkstemp()
    with os.fdopen(handle, "w") as stream:
        for block in blocks:
            stream.write(json.dumps({"message": {"content": [block]}}) + "\n")
    try:
        return subject.scan(path)
    finally:
        os.unlink(path)


failure = {"type": "tool_result", "content": "FAIL: hooks/example.py has no test (test-example.py); add one"}
repair = {"type": "tool_use", "name": "Write", "input": {"file_path": "hooks/test-example.py"}}
assert scan([failure]) == {"test-example.py"}
assert not scan([failure, repair])
assert not scan([{"type": "tool_result", "content": "other failure"}])
print("PASS: a concrete missing hook test blocks status until that test is written")
