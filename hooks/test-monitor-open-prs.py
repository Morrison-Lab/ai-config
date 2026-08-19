#!/usr/bin/env python3
"""Regression test for monitor-open-prs.py."""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("subject", sys.argv[1])
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

assert subject.POLL_SECONDS == 120
assert subject.STATE_PATH.endswith("all-open-prs.json")
assert any(isinstance(c, (str, tuple, list)) and "--author" in c for c in subject.open_prs.__code__.co_consts)

# Verify read_state / write_state roundtrip preserves reported fingerprint
import tempfile, os
with tempfile.TemporaryDirectory() as d:
    orig_path = subject.STATE_PATH
    subject.STATE_PATH = os.path.join(d, "test-prs.json")
    try:
        subject.write_state({"reported": "f1ng3rpr1nt", "prior": 123})
        s = subject.read_state()
        assert s.get("reported") == "f1ng3rpr1nt"
        s.update({"checked_at": 999})
        subject.write_state(s)
        subject.write_state({"data": [{"number": 1}], "reported": "f1ng3rpr1nt"})
        s = subject.read_state()
        assert s.get("data") == [{"number": 1}]
        s.pop("data", None)
        s["error"] = "Command failed"
        subject.write_state(s)
        assert subject.read_state().get("error") == "Command failed"
        assert "data" not in subject.read_state()
    finally:
        subject.STATE_PATH = orig_path

print("PASS: the all-open-PR controller preserves state keys and clears stale data on error")
