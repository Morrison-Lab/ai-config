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

        # The SIGTERM lands while our Popen handle keeps the child's exit
        # status unreaped, so what the probe can see afterwards is
        # topology-dependent: POSIX signal-0 keeps succeeding until the
        # reap, while the OpenProcess probe reads the recorded exit code
        # immediately -- and each topology must report honestly either way.
        with open(state_path, "w", encoding="utf-8") as stream:
            json.dump({"pid": process.pid, "checked_at": time.time()}, stream)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            result = subject.stop_stale_daemon(state_path, STALE, wait_seconds=0.5)
        check("live recorded daemon is stopped", result == process.pid)
        if os.name == "nt":
            check("windows probe confirms the stop once the exit code lands",
                  "stopped stale monitor daemon" in captured.getvalue())
        else:
            check("an exhausted wait reports the pid as still observable",
                  "still observable" in captured.getvalue())
        process.wait(timeout=15)
        check("stopped daemon actually exits", process.poll() is not None)
    finally:
        if process.poll() is None:
            process.kill()

    # A probe that reports the pid gone takes the confirmed-stop path
    # without exhausting the wait; a stubbed hook module makes that branch
    # deterministic on every platform.
    with open(state_path, "w", encoding="utf-8") as stream:
        json.dump({"pid": 4242, "checked_at": time.time()}, stream)

    class GoneModule:
        STATE_PATH = state_path
        POLL_SECONDS = 120

        @staticmethod
        def alive(pid):
            return False

    real_loader = subject.monitor_module
    real_kill = os.kill
    try:
        # The SIGTERM itself must succeed against the fake pid, or the
        # quiet no-op branch fires before the probe is ever reached.
        os.kill = lambda pid, sig: None
        subject.monitor_module = lambda: GoneModule
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
        subject.monitor_module = real_loader

# --- Windows persistence surface (#2082) ---
real_nt = subject.IS_NT
try:
    subject.IS_NT = True
    command = subject.windows_task_command(r"C:\py\python.exe")
    check("task command quotes interpreter and hook",
          command.startswith('"C:\\py\\python.exe" "') and command.endswith('" --monitor'))

    ran = {}

    def fake_run(args, **kwargs):
        ran["args"] = args
        return type("Result", (), {"returncode": 0, "stdout": ""})()

    real_run = subject.subprocess.run
    try:
        subject.subprocess.run = fake_run
        subject.install_windows(r"C:\py\python.exe")
        args = ran["args"]
        check("schtasks registers a named recurring task",
              args[:2] == ["schtasks", "/Create"] and "/SC" in args
              and args[args.index("/MO") + 1] == str(subject.POLL_MINUTES)
              and args[args.index("/TN") + 1] == subject.TASK_NAME)
        check("schtasks /TR carries the quoted command line",
              args[args.index("/TR") + 1] == command)

        missing = type("Result", (), {"returncode": 1, "stdout": ""})()
        subject.subprocess.run = lambda args_, **k: missing
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = subject.status_windows()
        check("status says not installed when the query fails",
              code != 0 and "not installed" in captured.getvalue())

        found = type("Result", (), {"returncode": 0,
                                    "stdout": f"TaskName: {subject.TASK_NAME}\n"})()
        subject.subprocess.run = lambda args_, **k: found
        check("status passes a successful query through",
              subject.status_windows() == 0)

        subject.subprocess.run = fake_run
        subject.uninstall_windows()
        check("uninstall deletes the named task",
              ran["args"][:2] == ["schtasks", "/Delete"])

        # resolve_dependencies falls back to the running interpreter when
        # python3.exe is absent, which is the typical Windows layout.
        shutil.which = lambda name: (r"C:\gh.exe" if name == "gh" else None)
        check("missing python3 falls back to the running interpreter",
              subject.resolve_dependencies() == sys.executable)
    finally:
        shutil.which = real_which
finally:
    subject.IS_NT = real_nt

saved_nt = subject.IS_NT
try:
    subject.IS_NT = False
    check("status is refused off-Windows",
          exits(subject.main, ["--status"]) is not None)
finally:
    subject.IS_NT = saved_nt

print(f"{passes} passed, {failures} failed")
sys.exit(1 if failures else 0)
