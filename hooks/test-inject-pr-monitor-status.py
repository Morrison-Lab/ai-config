#!/usr/bin/env python3
"""Regression tests for inject-pr-monitor-status.py."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

first = {"data": {"state": "OPEN", "reviewDecision": ""}}
second = {"data": {"state": "OPEN", "reviewDecision": "APPROVED"}}
assert subject.fingerprint(first) == subject.fingerprint(first)
assert subject.fingerprint(first) != subject.fingerprint(second)
assert subject.fingerprint({"error": "offline"}) != subject.fingerprint(first)
assert subject.fingerprint({"error": "offline"}) == subject.fingerprint({"error": "offline"})


def run_main():
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        subject.main()
    return captured.getvalue()


def read_state(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def write_state(path, state):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(state, stream)


# A persistently-erroring monitor is surfaced once at the streak threshold,
# not repeated on every prompt, and recovery clears the flag.
with tempfile.TemporaryDirectory() as d:
    orig_dir = subject.STATE_DIR
    try:
        subject.STATE_DIR = d
        path = os.path.join(d, "monitor.json")

        # A new error is a change: reported once, then silent below the threshold.
        write_state(path, {"url": "u", "error": "no gh", "error_streak": 1, "checked_at": 1})
        assert "no gh" in run_main()
        write_state(path, {**read_state(path), "error_streak": 2, "checked_at": 2})
        assert run_main() == ""

        # At the threshold the unchanged error is surfaced once and flagged.
        write_state(path, {**read_state(path), "error_streak": 3, "checked_at": 3})
        assert "no gh" in run_main()
        assert read_state(path)["persistent_error_reported"] is True
        write_state(path, {**read_state(path), "error_streak": 4, "checked_at": 4})
        assert run_main() == ""

        # Recovery is a change: reported, and the persistent flag is cleared
        # so a later persistent error fires again.
        recovered = read_state(path)
        recovered.pop("error")
        write_state(path, {**recovered, "data": [{"number": 7}], "error_streak": 0, "checked_at": 5})
        assert '"number": 7' in run_main()
        assert "persistent_error_reported" not in read_state(path)

        # An error-text change mid-streak also re-arms the flag: the new
        # error gets its own persistent report at its own threshold (the
        # monitor restarts the streak on a text change).
        errored = read_state(path)
        errored.pop("data")
        write_state(path, {**errored, "error": "no gh", "error_streak": 3, "checked_at": 6})
        assert "no gh" in run_main()
        assert read_state(path)["persistent_error_reported"] is True
        write_state(path, {**read_state(path), "error": "timeout", "error_streak": 1, "checked_at": 7})
        assert "timeout" in run_main()
        assert "persistent_error_reported" not in read_state(path)
        write_state(path, {**read_state(path), "error_streak": 3, "checked_at": 8})
        assert "timeout" in run_main()
        assert read_state(path)["persistent_error_reported"] is True

        # An empty error message still goes persistent: presence of the
        # error key gates the report, not the truthiness of its text.
        write_state(path, {"url": "u", "error": "", "error_streak": 3, "checked_at": 9})
        assert run_main() != ""
        assert read_state(path)["persistent_error_reported"] is True
    finally:
        subject.STATE_DIR = orig_dir

# A state file with no error_streak (a per-PR watcher, a pre-fix daemon)
# surfaces its error on appearance and never persistently -- ai-config#2035.
with tempfile.TemporaryDirectory() as d:
    orig_dir = subject.STATE_DIR
    try:
        subject.STATE_DIR = d
        path = os.path.join(d, "prefix.json")
        write_state(path, {"url": "u", "error": "no gh", "checked_at": 1})
        assert "no gh" in run_main()
        write_state(path, {**read_state(path), "checked_at": 2})
        assert run_main() == ""
    finally:
        subject.STATE_DIR = orig_dir

print("PASS: only changed PR observations are injected; a persistent error is "
      "surfaced once at the streak threshold and re-armed on recovery or a "
      "text change")
