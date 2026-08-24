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
# The command must run the absolutely-resolved GH_PATH; the literal "gh"
# reappearing in open_prs would be a revert of the #1953 fix. CPython folds
# a list display into a tuple inside co_consts, so nested consts are
# searched too -- a top-level-only check passes on the reverted code.
assert not any(
    value == "gh"
    for const in subject.open_prs.__code__.co_consts
    for value in (const if isinstance(const, (tuple, list)) else (const,)))

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

# require_gh fails fast instead of starting a monitor that can only error
saved_gh = subject.GH_PATH
try:
    subject.GH_PATH = None
    try:
        subject.require_gh()
        raise AssertionError("require_gh should exit when gh is unresolvable")
    except SystemExit as exit_call:
        assert "gh" in str(exit_call.code)
finally:
    subject.GH_PATH = saved_gh

# Consecutive failures accumulate an error_streak; success resets it.
with tempfile.TemporaryDirectory() as d:
    orig_path = subject.STATE_PATH
    real_open_prs = subject.open_prs

    def failing():
        raise OSError("[Errno 2] No such file or directory: 'gh'")

    def working():
        return [{"number": 7}]

    try:
        subject.STATE_PATH = os.path.join(d, "streak.json")
        subject.open_prs = failing
        state = subject.poll_once({})
        assert state["error"].endswith("'gh'")
        assert "data" not in state
        assert state["error_streak"] == 1
        state = subject.poll_once(state)
        assert state["error_streak"] == 2

        # A different error text restarts the streak: the streak counts
        # consecutive polls of the SAME error, so a new failure mode earns
        # its own persistent report downstream.
        def failing_differently():
            raise OSError("connection timed out")

        subject.open_prs = failing_differently
        state = subject.poll_once(state)
        assert state["error"] == "connection timed out"
        assert state["error_streak"] == 1
        state = subject.poll_once(state)
        assert state["error_streak"] == 2

        subject.open_prs = working
        state = subject.poll_once(state)
        assert "error" not in state
        assert state["error_streak"] == 0
        assert state["data"] == [{"number": 7}]
    finally:
        subject.open_prs = real_open_prs
        subject.STATE_PATH = orig_path

# alive() must be truthful on every platform: signal-0 does not track
# liveness on Windows (#2082), so the probe is OpenProcess there.
# Non-positive and garbage pids are refused before any probe -- signal 0
# to -1 would address a whole process group on POSIX.
for bad in (None, "abc", 0, -1, -999):
    assert subject.alive(bad) is False, f"alive({bad!r}) should be False"
assert subject.alive(os.getpid()) is True
assert subject.alive(2 ** 30) is False
if os.name == "nt":
    assert subject._alive_windows(os.getpid()) is True

print("PASS: gh is resolved or refused at startup; failures accumulate an "
      "error streak that success resets")
