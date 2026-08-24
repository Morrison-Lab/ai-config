#!/usr/bin/env python3
"""Install and start ai-config's agent-independent PR monitor service.

The daemon must survive contexts with a minimal PATH (cron, systemd user
units), so `gh` and `python3` are resolved absolutely at install time and
the interactive PATH is persisted for the daemon: into the cron line and a
systemd drop-in. The checked-in unit stays machine-generic.

On Windows the poll persists as a Task Scheduler job every five minutes;
the task inherits the user environment, so the hook's runtime `gh`
resolution sees the interactive PATH. The task runs while you are logged
on: sleep and logout pause it, which is acceptable for a secondary
backstop host (#2082).

Installing also STOPS a daemon already running under the old code: systemd's
`enable --now` no-ops on an active unit and `ensure()` returns early on a
live pid, so without an explicit stop the installer would report success
while the broken daemon kept polling (the #1953 trap).
"""
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIT = "ai-config-pr-monitor.service"
SOURCE = ROOT / "systemd" / UNIT
TARGET = Path.home() / ".config" / "systemd" / "user" / UNIT
HOOK = ROOT / "hooks" / "monitor-open-prs.py"
INSTALLED_HOOK = Path.home() / ".local" / "share" / "ai-config" / "hooks" / HOOK.name
CRON_MARKER = "# ai-config-pr-monitor"
IS_NT = os.name == "nt"
TASK_NAME = "ai-config-pr-monitor"
# Matches the Unix staleness horizon below: STALE_POLLS intervals of
# POLL_SECONDS must fit inside the schedule, or fresh-looking state could
# outlive its daemon between two task firings.
POLL_MINUTES = 5
# A live daemon rewrites checked_at every poll; a state file older than this
# many poll intervals proves the recorded pid no longer belongs to the
# monitor. The interval itself is read from the hook, not duplicated here.
STALE_POLLS = 5


def resolve_dependencies():
    python3 = shutil.which("python3")
    if python3 is None and IS_NT:
        # Windows rarely ships a python3.exe alias; run the daemon under
        # whatever interpreter is executing this installer.
        python3 = sys.executable
    gh = shutil.which("gh")
    missing = [name for name, path in (("python3", python3), ("gh", gh)) if not path]
    if missing:
        sys.exit("FATAL: cannot resolve " + ", ".join(missing) + " on PATH; "
                 "refusing to install a monitor that can only error every poll")
    return python3


def interactive_path():
    path = os.environ.get("PATH", "")
    if '"' in path or any(ord(character) < 0x20 for character in path):
        sys.exit("FATAL: PATH contains a double quote or control character, "
                 "which cannot be persisted safely into a crontab line or "
                 "systemd drop-in; clean PATH and re-run")
    return path


def dropin_text(path):
    # A literal % must be doubled in a systemd unit: specifier expansion
    # applies to Environment= values.
    return '[Service]\nEnvironment="PATH=' + path.replace("%", "%%") + '"\n'


def write_path_dropin(path):
    dropin_dir = TARGET.parent / (UNIT + ".d")
    dropin_dir.mkdir(parents=True, exist_ok=True)
    (dropin_dir / "10-path.conf").write_text(dropin_text(path), encoding="utf-8")


def cron_line(python3, path):
    line = ('@reboot /usr/bin/env PATH="' + path + '" '
            + python3 + " " + str(INSTALLED_HOOK) + " --monitor " + CRON_MARKER + "\n")
    if "%" in line:
        # cron rewrites an unescaped % in the command field into a newline,
        # and backslash-escape semantics differ across cron implementations,
        # so refuse rather than persist a corrupted line.
        sys.exit("FATAL: the generated crontab line contains '%', which cron "
                 "would corrupt; install under systemd or clean PATH")
    return line


def install_cron(python3, path):
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if existing.returncode not in (0, 1):
        return False
    existing_lines = [line for line in existing.stdout.splitlines()
                      if CRON_MARKER not in line]
    content = "\n".join(existing_lines).rstrip() + "\n" + cron_line(python3, path)
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)
    return True


def monitor_module():
    spec = importlib.util.spec_from_file_location("monitor_open_prs", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stop_stale_daemon(state_path=None, stale_seconds=None, wait_seconds=5.0):
    """Kill the recorded daemon so the start below runs the fixed code.

    Only a recently-refreshed state file proves the recorded pid still
    belongs to a live monitor; past the staleness horizon the pid may have
    been recycled to an unrelated process, and the daemon it named is dead
    anyway, so the file is left alone.  A missing, unreadable, or pid-less
    state file returns None the same quiet way: there is nothing to stop.
    The liveness probe during the wait is the hook's own alive(), which
    uses OpenProcess on Windows instead of the meaningless signal-0 kill.
    After the SIGTERM, wait for the process to disappear so the cron
    fallback's ensure() cannot observe the dying pid as alive and skip its
    respawn --- and say so when the wait exhausts, so a survived SIGTERM is
    not reported as a stop.
    """
    module = monitor_module()
    if state_path is None:
        state_path = module.STATE_PATH
    if stale_seconds is None:
        stale_seconds = STALE_POLLS * module.POLL_SECONDS
    try:
        with open(state_path, encoding="utf-8") as stream:
            state = json.load(stream)
        pid = int(state.get("pid"))
        if time.time() - float(state.get("checked_at") or 0) > stale_seconds:
            return None
        # On Windows os.kill maps SIGTERM to TerminateProcess, which is the
        # intended outcome for our own daemon; POSIX gets a real SIGTERM.
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError, TypeError):
        return None
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if not module.alive(pid):
            print(f"stopped stale monitor daemon (pid {pid})")
            return pid
        time.sleep(0.1)
    print(f"sent SIGTERM to the recorded daemon (pid {pid}), but it is still "
          f"observable after {wait_seconds}s; ensure() may see it and delay "
          "the respawn to the next prompt")
    return pid


def windows_task_command(python3):
    return f'"{python3}" "{INSTALLED_HOOK}" --monitor'


def install_windows(python3):
    subprocess.run(
        ["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", str(POLL_MINUTES),
         "/TN", TASK_NAME, "/TR", windows_task_command(python3)],
        check=True)
    print(f"scheduled task {TASK_NAME} every {POLL_MINUTES} minutes; it runs "
          "while you are logged on, so sleep and logout pause polling")


def status_windows():
    query = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME],
                           capture_output=True, text=True)
    if query.returncode == 0:
        print(query.stdout.strip())
        return 0
    print(f"{TASK_NAME}: not installed")
    return 1


def uninstall_windows():
    subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], check=True)
    print(f"deleted scheduled task {TASK_NAME}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if IS_NT:
        if argv == ["--status"]:
            return status_windows()
        if argv == ["--uninstall"]:
            uninstall_windows()
            return 0
    if argv:
        sys.exit(f"FATAL: unsupported arguments {argv} on this platform")
    python3 = resolve_dependencies()
    if not HOOK.is_file():
        sys.exit(f"FATAL: monitor source is missing at {HOOK}")
    INSTALLED_HOOK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HOOK, INSTALLED_HOOK)
    if IS_NT:
        stop_stale_daemon()
        install_windows(python3)
        return 0
    path = interactive_path()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, TARGET)
    write_path_dropin(path)
    stop_stale_daemon()
    try:
        for command in (("systemctl", "--user", "daemon-reload"),
                        ("systemctl", "--user", "enable", UNIT),
                        ("systemctl", "--user", "restart", UNIT)):
            subprocess.run(command, check=True)
    except (OSError, subprocess.SubprocessError):
        subprocess.run([sys.executable, str(INSTALLED_HOOK)], check=True)
        try:
            if not install_cron(python3, path):
                sys.exit("FATAL: neither systemd nor crontab could persist the PR monitor")
        except (OSError, subprocess.SubprocessError):
            sys.exit("FATAL: neither systemd nor crontab could persist the PR monitor")
        print("started monitor now; installed cron @reboot fallback")
        return 0
    print(f"enabled and restarted {UNIT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
