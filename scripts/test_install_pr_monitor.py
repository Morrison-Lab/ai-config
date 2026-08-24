#!/usr/bin/env python3
"""Offline regression tests for install-pr-monitor.py's pure helpers."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT = Path(__file__).with_name("install-pr-monitor.py")
spec = importlib.util.spec_from_file_location("install_pr_monitor", SCRIPT)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)

passes = failures = 0


def check(name, condition):
    global passes, failures
    if condition:
        print(f"PASS: {name}")
        passes += 1
    else:
        print(f"FAIL: {name}")
        failures += 1


def exits(callable_, *args):
    try:
        callable_(*args)
    except SystemExit as exit_call:
        return str(exit_call.code)
    return None


# resolve_dependencies fails fast when gh is unresolvable.
real_which = shutil.which
try:
    shutil.which = lambda name: None if name == "gh" else real_which(name)
    message = exits(subject.resolve_dependencies)
    check("missing gh refuses the install", message is not None and "gh" in message)
finally:
    shutil.which = real_which

# interactive_path refuses a PATH carrying a double quote and passes a
# clean one through unchanged.
real_path = os.environ.get("PATH", "")
try:
    os.environ["PATH"] = '/usr/bin:/evil"dir'
    check("double quote in PATH refuses the install",
          exits(subject.interactive_path) is not None)
    os.environ["PATH"] = "/usr/bin:/evil\ndir"
    check("control character in PATH refuses the install",
          exits(subject.interactive_path) is not None)
    os.environ["PATH"] = "/usr/bin:/opt/homebrew/bin"
    check("clean PATH passes through",
          subject.interactive_path() == "/usr/bin:/opt/homebrew/bin")
finally:
    os.environ["PATH"] = real_path

# The systemd drop-in doubles literal % (specifier expansion) and quotes
# the assignment.
text = subject.dropin_text("/usr/bin:/opt/we%rd")
check("drop-in escapes percent", 'Environment="PATH=/usr/bin:/opt/we%%rd"' in text)
check("drop-in targets [Service]", text.startswith("[Service]\n"))

# The cron line runs env with the persisted PATH and the absolute python3,
# and refuses a line cron would corrupt at the first %.
line = subject.cron_line("/opt/python3", "/usr/bin:/opt/homebrew/bin")
check("cron line persists PATH via env",
      '/usr/bin/env PATH="/usr/bin:/opt/homebrew/bin"' in line)
check("cron line uses the absolute python3", " /opt/python3 " in line)
check("cron line carries the marker", line.rstrip().endswith(subject.CRON_MARKER))
check("percent anywhere in the cron line refuses the install",
      exits(subject.cron_line, "/opt/python3", "/opt/we%rd") is not None)

# stop_stale_daemon kills the recorded pid and reports it; a missing or
# stale state file is a quiet no-op.
STALE = 600
with tempfile.TemporaryDirectory() as d:
    state_path = os.path.join(d, "all-open-prs.json")
    check("missing state file is a no-op",
          subject.stop_stale_daemon(state_path, STALE) is None)

    with open(state_path, "w", encoding="utf-8") as stream:
        json.dump({"pid": None}, stream)
    check("state without a pid is a no-op",
          subject.stop_stale_daemon(state_path, STALE) is None)

    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        # A state file past the freshness horizon leaves even a live pid
        # alone: the pid may have been recycled to an unrelated process,
        # and the daemon that wrote the file is dead anyway.
        with open(state_path, "w", encoding="utf-8") as stream:
            json.dump({"pid": process.pid, "checked_at": time.time() - 2 * STALE},
                      stream)
        check("stale state file leaves a live pid alone",
              subject.stop_stale_daemon(state_path, STALE) is None
              and process.poll() is None)

        # In this topology the dying pid stays observable (an unreaped
        # child on POSIX, an open handle on Windows), so the wait exhausts
        # and must say so rather than claiming a confirmed stop.
        with open(state_path, "w", encoding="utf-8") as stream:
            json.dump({"pid": process.pid, "checked_at": time.time()}, stream)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            result = subject.stop_stale_daemon(state_path, STALE, wait_seconds=0.5)
        check("live recorded daemon is stopped", result == process.pid)
        check("an exhausted wait reports the pid as still observable",
              "still observable" in captured.getvalue())
        process.wait(timeout=15)
        check("stopped daemon actually exits", process.poll() is not None)
    finally:
        if process.poll() is None:
            process.kill()

    # When the probe raises, the confirmed-stop path fires without
    # exhausting the wait; a fake kill makes that branch deterministic in
    # every topology.
    with open(state_path, "w", encoding="utf-8") as stream:
        json.dump({"pid": 4242, "checked_at": time.time()}, stream)
    real_kill = os.kill

    def fake_kill(pid, sig):
        if sig == 0:
            raise OSError("no such process")

    try:
        os.kill = fake_kill
        captured = io.StringIO()
        started = time.monotonic()
        with contextlib.redirect_stdout(captured):
            result = subject.stop_stale_daemon(state_path, STALE, wait_seconds=5.0)
        check("a gone daemon takes the confirmed-stop path",
              result == 4242 and "stopped stale monitor daemon" in captured.getvalue())
        check("the confirmed stop does not exhaust the wait",
              time.monotonic() - started < 2.0)
    finally:
        os.kill = real_kill

print(f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
