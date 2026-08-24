#!/usr/bin/env python3
"""Install and start ai-config's agent-independent PR monitor service.

The daemon must survive contexts with a minimal PATH (cron, systemd user
units), so `gh` and `python3` are resolved absolutely at install time and
the interactive PATH is persisted for the daemon: into the cron line and a
systemd drop-in. The checked-in unit stays machine-generic.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIT = "ai-config-pr-monitor.service"
SOURCE = ROOT / "systemd" / UNIT
TARGET = Path.home() / ".config" / "systemd" / "user" / UNIT
HOOK = ROOT / "hooks" / "monitor-open-prs.py"
INSTALLED_HOOK = Path.home() / ".local" / "share" / "ai-config" / "hooks" / HOOK.name
CRON_MARKER = "# ai-config-pr-monitor"


def resolve_dependencies():
    python3 = shutil.which("python3")
    gh = shutil.which("gh")
    missing = [name for name, path in (("python3", python3), ("gh", gh)) if not path]
    if missing:
        sys.exit("FATAL: cannot resolve " + ", ".join(missing) + " on PATH; "
                 "refusing to install a monitor that can only error every poll")
    return python3


def write_path_dropin():
    dropin_dir = TARGET.parent / (UNIT + ".d")
    dropin_dir.mkdir(parents=True, exist_ok=True)
    dropin = dropin_dir / "10-path.conf"
    dropin.write_text('[Service]\nEnvironment="PATH=' + os.environ.get("PATH", "") + '"\n',
                      encoding="utf-8")


def install_cron(python3):
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if existing.returncode not in (0, 1):
        return False
    existing_lines = [line for line in existing.stdout.splitlines()
                      if CRON_MARKER not in line]
    line = ('@reboot /usr/bin/env PATH="' + os.environ.get("PATH", "") + '" '
            + python3 + " " + str(INSTALLED_HOOK) + " --monitor " + CRON_MARKER + "\n")
    content = "\n".join(existing_lines).rstrip() + "\n" + line
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)
    return True


def main():
    python3 = resolve_dependencies()
    if not HOOK.is_file():
        sys.exit(f"FATAL: monitor source is missing at {HOOK}")
    INSTALLED_HOOK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HOOK, INSTALLED_HOOK)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, TARGET)
    write_path_dropin()
    try:
        for command in (("systemctl", "--user", "daemon-reload"),
                        ("systemctl", "--user", "enable", "--now", UNIT)):
            subprocess.run(command, check=True)
    except (OSError, subprocess.SubprocessError):
        subprocess.run([sys.executable, str(INSTALLED_HOOK)], check=True)
        try:
            if not install_cron(python3):
                sys.exit("FATAL: neither systemd nor crontab could persist the PR monitor")
        except (OSError, subprocess.SubprocessError):
            sys.exit("FATAL: neither systemd nor crontab could persist the PR monitor")
        print("started monitor now; installed cron @reboot fallback")
        return
    print(f"enabled and started {UNIT}")


if __name__ == "__main__":
    main()
