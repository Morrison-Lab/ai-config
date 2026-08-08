"""Locate a bash that can actually run a given shell script.

Probed, never named. `shutil.which("bash")` finding *a* bash proves nothing on
Windows, where the first entry on PATH is often the WSL launcher: it runs, sees
the checkout as `/mnt/c/...`, and reports "not inside a git repository" -- so a
script that resolves its own registry through `git rev-parse` fails under it
while a Git Bash two entries later works fine. Invoking the `.sh` directly is
worse still: on Windows a shell script is not a valid executable image and
raises `OSError: [WinError 193]`, which is how the merge guard's MWC test
section came to abort before running a single one of its cases.

The probe IS the requirement: run the script's own cheapest read-only
subcommand and keep the first shell that exits 0.
"""
import os
import shutil
import subprocess

# Ordered by specificity: an explicit override, then PATH, then the usual
# Git-for-Windows locations, then the POSIX default.
CANDIDATES = (
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
    "/bin/bash",
)


def find_bash(script, probe_args=("list",), cwd=None, timeout=60):
    """Return a bash able to run `script` with `probe_args`, or None.

    `probe_args` must name a read-only subcommand: the probe really runs it.
    """
    tried = []
    for cand in (os.environ.get("AI_SESSION_BASH"), shutil.which("bash"), *CANDIDATES):
        if not cand or cand in tried:
            continue
        tried.append(cand)
        try:
            proc = subprocess.run(
                [cand, str(script), *probe_args],
                capture_output=True, cwd=cwd, timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0:
            return cand
    return None
