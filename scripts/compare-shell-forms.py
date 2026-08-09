#!/usr/bin/env python3
"""Compare two or more command spellings by running each through exactly ONE shell.

Why this exists
---------------
"Do these two spellings of a command behave the same?" is decidable, it recurred
three times in one session, and it is precisely the question human reasoning
about escaping layers gets wrong. Per `shared/principles/deterministic-tools.md`,
the third occurrence is a tool.

The failure it prevents is specific. A command typed into a tool that wraps it in
another shell is not the command a reader runs from a file: each extra layer
collapses one level of backslash quoting, so two spellings that differ by a
doubled pair arrive at the program IDENTICAL. A measurement taken that way
reports the two forms as equivalent, which is a true statement about the harness
and a false one about the command. Writing each form to its own file and running
`bash <file>` applies exactly one layer, which is what a reader gets.

Worked instance (verified 2026-08-08, this repo, Python 3.13):

    A: python -c "print(repr('...r\\"changes\\\\\\\\s+requested\\\\\\\\b\\":'))"
    B: python -c "print(repr('...r\\"changes\\\\s+requested\\\\b\\":'))"

Run from a file, A prints a literal backslash-b and no warning while B prints
\\x08 (a backspace) and a SyntaxWarning. Typed straight into a wrapping tool,
both print \\x08 and the difference vanishes. Same strings, opposite verdicts.

Three outcomes, not two
-----------------------
IDENTICAL / DIFFERING / HARNESS FAILURE. The third exists because a broken run
prints a plausible "these differ" or "these match" otherwise: while this script
was being written, two probe attempts returned a confident answer that was
actually a path-mangling failure and a missing interpreter. A harness failure
exits non-zero so a caller cannot read a broken run as a result.

Note on what counts as a harness failure: only the shell failing to RUN the
file (126/127, a missing bash, a not-found interpreter), never the command's own
non-zero exit. A command under comparison may legitimately exit non-zero --
`grep` returns 1 on no match, and comparing grep spellings is a core use here --
so treating any non-zero status as a harness failure would hide real differences
rather than surface broken runs.

Usage
-----
    python3 scripts/compare-shell-forms.py 'cmd one' 'cmd two' [...]
    python3 scripts/compare-shell-forms.py --file forms.txt   # one per line
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IDENTICAL = "IDENTICAL"
DIFFERING = "DIFFERING"
HARNESS_FAILURE = "HARNESS FAILURE"

# Exit statuses a POSIX shell uses to say it could not run the thing at all,
# as opposed to the thing running and failing on its own terms.
CANNOT_EXECUTE = 126
NOT_FOUND = 127


# Where Git for Windows puts bash when it is not already on PATH.
WINDOWS_BASH_FALLBACKS = (
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files\Git\usr\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
)


def find_bash():
    """Return a path to bash, or None. Reported loudly rather than assumed."""
    found = shutil.which("bash")
    if found:
        return found
    for candidate in WINDOWS_BASH_FALLBACKS:
        if Path(candidate).exists():
            return candidate
    return None


def interpreter_env():
    """PATH with this Python's own directory prepended.

    A bash started from a Python subprocess does not reliably inherit a PATH
    containing `python`, so a form that invokes `python` would fail as a harness
    failure for a reason that has nothing to do with the forms being compared.
    Resolving it from `sys.executable` fixes the common case; anything still
    missing is reported rather than swallowed.
    """
    env = dict(os.environ)
    exe_dir = str(Path(sys.executable).parent)
    env["PATH"] = exe_dir + os.pathsep + env.get("PATH", "")
    return env


def looks_like_harness_failure(returncode, stderr):
    """True when the shell could not RUN the form, not when the form failed.

    The exit status decides it alone. An earlier version also matched
    not-found strings anywhere in stderr, which reintroduced the exact thing
    narrowing the exit-code rule was for: `grep pat missing.txt` prints "No
    such file or directory" and exits 2, which is the command failing on its
    own terms and a perfectly good thing to compare between two spellings.
    Calling that a harness failure says "this is not a result about the forms"
    about the most ordinary command there is -- the fail-closed direction, and
    still wrong.

    The markers bought nothing in exchange. Measured on this bash: an unknown
    command exits 127, and a missing script exits 127, so every genuine case
    the markers were meant to catch already carries a code.
    """
    return returncode in (CANNOT_EXECUTE, NOT_FOUND)


def run_form(command, bash, env, workdir, index):
    """Write `command` verbatim to its own file and run it under one shell."""
    path = Path(workdir) / f"form_{index}.sh"
    # Written as bytes with an explicit newline so nothing re-interprets the
    # content on the way to disk. This is the whole point of the tool: the file
    # holds exactly the characters the caller supplied.
    path.write_text(command + "\n", encoding="utf-8", newline="\n")
    try:
        proc = subprocess.run(
            [bash, str(path)],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": "timed out after 60s",
            "harness_failure": True,
        }
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "harness_failure": looks_like_harness_failure(proc.returncode, proc.stderr),
    }


def classify(results):
    """IDENTICAL, DIFFERING, or HARNESS FAILURE over a list of run_form results."""
    if not results:
        return HARNESS_FAILURE
    if any(r["harness_failure"] for r in results):
        return HARNESS_FAILURE
    signatures = {
        (r["returncode"], r["stdout"], r["stderr"]) for r in results
    }
    return IDENTICAL if len(signatures) == 1 else DIFFERING


def render(results, verdict):
    """Human-readable report. Outputs are repr'd so invisible bytes show."""
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(f"--- form {i} ---")
        lines.append(f"  command : {r['command']}")
        lines.append(f"  exit    : {r['returncode']}")
        lines.append(f"  stdout  : {r['stdout']!r}")
        lines.append(f"  stderr  : {r['stderr']!r}")
        if r["harness_failure"]:
            lines.append("  NOTE    : this form did not run (harness failure)")
        lines.append("")
    lines.append(f"forms compared: {len(results)}")
    lines.append(f"VERDICT: {verdict}")
    if verdict == HARNESS_FAILURE:
        lines.append(
            "At least one form never ran, so this is NOT a result about the "
            "forms. Fix the harness and re-run."
        )
    elif verdict == IDENTICAL:
        lines.append("Every form produced the same exit status, stdout and stderr.")
    else:
        lines.append("The forms are not equivalent; see the repr'd output above.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run each command spelling through exactly one shell and "
                    "compare the results."
    )
    parser.add_argument("commands", nargs="*", help="command strings to compare")
    parser.add_argument(
        "--file",
        help="read one command per line from this file instead of argv",
    )
    args = parser.parse_args(argv)

    if args.file:
        commands = [
            line
            for line in Path(args.file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        commands = list(args.commands)

    if len(commands) < 2:
        print("Need at least two command spellings to compare.", file=sys.stderr)
        return 2

    bash = find_bash()
    if bash is None:
        print(
            render([], HARNESS_FAILURE)
            + "\nbash was not found on PATH or at a known Git for Windows path.",
            file=sys.stderr,
        )
        return 1

    env = interpreter_env()
    with tempfile.TemporaryDirectory(prefix="shellforms-") as workdir:
        results = [
            run_form(cmd, bash, env, workdir, i)
            for i, cmd in enumerate(commands, start=1)
        ]

    verdict = classify(results)
    print(render(results, verdict))
    return 1 if verdict == HARNESS_FAILURE else 0


if __name__ == "__main__":
    sys.exit(main())
