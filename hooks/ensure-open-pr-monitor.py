#!/usr/bin/env python3
"""UserPromptSubmit hook that ensures the all-open-PR/MR timer is running."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


IS_WINDOWS = os.name == "nt"


def resolve_interpreter():
    interpreter = sys.executable or "python3"
    if IS_WINDOWS:
        p = Path(interpreter)
        sibling = p.with_name("pythonw.exe")
        if sibling.is_file():
            return str(sibling)
        found = shutil.which("pythonw")
        if found:
            return found
    return interpreter


def main():
    script = os.path.join(os.path.dirname(os.path.realpath(__file__)), "monitor-open-prs.py")
    try:
        kwargs = {}
        if IS_WINDOWS:
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        interpreter = resolve_interpreter()
        subprocess.run([interpreter, script], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=10, check=True, **kwargs)
    except (OSError, subprocess.SubprocessError):
        return


if __name__ == "__main__":
    main()
