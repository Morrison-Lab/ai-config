#!/usr/bin/env python3
"""Install and start ai-config's agent-independent PR monitor service."""
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


def install_cron():
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if existing.returncode not in (0, 1):
        return False
    existing_lines = [line for line in existing.stdout.splitlines()
                      if CRON_MARKER not in line]
    line = f"@reboot /usr/bin/env python3 {INSTALLED_HOOK} --monitor {CRON_MARKER}\n"
    content = "\n".join(existing_lines).rstrip() + "\n" + line
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)
    return True


def main():
    if not HOOK.is_file():
        sys.exit(f"FATAL: monitor source is missing at {HOOK}")
    INSTALLED_HOOK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HOOK, INSTALLED_HOOK)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, TARGET)
    try:
        for command in (("systemctl", "--user", "daemon-reload"),
                        ("systemctl", "--user", "enable", "--now", UNIT)):
            subprocess.run(command, check=True)
    except (OSError, subprocess.SubprocessError):
        subprocess.run([sys.executable, str(INSTALLED_HOOK)], check=True)
        try:
            if not install_cron():
                sys.exit("FATAL: neither systemd nor crontab could persist the PR monitor")
        except (OSError, subprocess.SubprocessError):
            sys.exit("FATAL: neither systemd nor crontab could persist the PR monitor")
        print("started monitor now; installed cron @reboot fallback")
        return
    print(f"enabled and started {UNIT}")


if __name__ == "__main__":
    main()
