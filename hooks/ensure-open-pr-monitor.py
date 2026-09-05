#!/usr/bin/env python3
"""UserPromptSubmit hook that ensures the all-open-PR/MR timer is running."""
import os
import subprocess


def main():
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor-open-prs.py")
    try:
        subprocess.run(["python3", script], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        return


if __name__ == "__main__":
    main()
